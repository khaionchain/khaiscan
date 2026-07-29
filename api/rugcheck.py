"""
RugCheck API collector (Solana only).

Endpoint: GET https://api.rugcheck.xyz/v1/tokens/{address}/report

Returns: security flags, top holders, LP lock %, bundle %, dev wallet info,
         risk flags, freeze authority, metadata mutability.
"""
from __future__ import annotations
import logging
import re
from typing import Optional
import aiohttp
from api.base import safe_get

logger = logging.getLogger(__name__)

_BASE = "https://api.rugcheck.xyz/v1/tokens"


async def get_report(address: str, session: aiohttp.ClientSession) -> Optional[dict]:
    """
    Fetch the full RugCheck report for a Solana token.

    Returns a normalised dict or None on failure.
    """
    data = await safe_get(session, f"{_BASE}/{address}/report", label="RugCheck")
    if not data:
        return None

    token_meta = data.get("tokenMeta") or {}
    token_info = data.get("token") or {}

    # ── Top holders ────────────────────────────────────────────────────
    top_holders = data.get("topHolders") or []
    top10_pct: Optional[float] = None
    largest_wallet_pct: Optional[float] = None
    insider_count = 0

    if top_holders:
        top10_pct = sum(h.get("pct", 0) for h in top_holders[:10])
        largest_wallet_pct = top_holders[0].get("pct") if top_holders else None
        insider_count = sum(1 for h in top_holders if h.get("insider", False))

    if not insider_count:
        insider_count = int(data.get("graphInsidersDetected") or 0)

    # ── Dev wallet from creator field ──────────────────────────────────
    creator = data.get("creator") or data.get("deployer")
    dev_wallet_pct: Optional[float] = None
    dev_sold: Optional[bool] = None

    if creator and top_holders:
        # Check if creator appears in top holders
        creator_in_holders = False
        for holder in top_holders:
            if holder.get("address", "").lower() == creator.lower():
                dev_wallet_pct = holder.get("pct", 0.0)
                creator_in_holders = True
                break
        # If creator was identified but not in top holders, they likely sold/moved
        if not creator_in_holders:
            dev_wallet_pct = 0.0
            dev_sold = True
    elif creator:
        # Creator found but no top holder data — assume minimal
        dev_wallet_pct = 0.0

    # ── Bundle detection ───────────────────────────────────────────────
    bundle_pct: Optional[float] = None
    risks = data.get("risks") or []
    risk_names: list[str] = []

    for risk in risks:
        risk_name = risk.get("name") or ""
        risk_names.append(risk_name)

        if "bundle" in risk_name.lower():
            desc = risk.get("description") or ""
            # Try to parse percentage from description text, e.g. "2.00% of supply bundled"
            match = re.search(r'(\d+\.?\d*)%', desc)
            if match:
                bundle_pct = float(match.group(1))
            else:
                # Fall back: RugCheck score field (0-10000) scaled
                raw = risk.get("score") or 0
                bundle_pct = min(100.0, raw / 100) if raw else None

    # Fallback to insiderNetworks graph if bundle_pct not in risks
    if bundle_pct is None:
        insider_networks = data.get("insiderNetworks") or []
        supply = (token_info.get("supply") or 0)
        if supply > 0 and insider_networks:
            insider_tokens = sum(net.get("tokenAmount", 0) for net in insider_networks if isinstance(net, dict))
            if insider_tokens > 0:
                bundle_pct = round((insider_tokens / supply) * 100, 2)

    # ── Mint / Freeze / Update authority ──────────────────────────────
    mint_disabled   = token_info.get("mintAuthority") is None
    freeze_disabled = token_info.get("freezeAuthority") is None
    # If both mint AND freeze are revoked, treat as "renounced" on Solana
    ownership_renounced = mint_disabled and freeze_disabled

    # Metadata mutability
    metadata_mutable = token_meta.get("mutable", True)

    # -- LP lock --------------------------------------------------------
    # RugCheck stores LP lock inside markets[].lp, NOT at the top level
    locked_pct = (
        data.get("lockedPct")
        or data.get("totalLpLockedPct")
        or data.get("lpLockedPct")
        or data.get("lockPercentage")
    )
    # If not at top level, dig into markets array
    if locked_pct is None:
        for market in (data.get("markets") or []):
            lp = market.get("lp") or {}
            pct = lp.get("lpLockedPct")
            if pct is not None:
                try:
                    pct_float = float(pct)
                    if pct_float > 0:
                        locked_pct = pct_float
                        break
                except (TypeError, ValueError):
                    pass

    # Any LP locked at all = lp_locked True
    lp_locked = bool(locked_pct and float(locked_pct) > 0)

    return {
        "name":                 token_meta.get("name"),
        "symbol":               token_meta.get("symbol"),
        "top10_pct":            round(top10_pct, 2) if top10_pct is not None else None,
        "largest_wallet_pct":   round(largest_wallet_pct, 2) if largest_wallet_pct else None,
        "holder_count":         data.get("holderCount"),
        "insider_wallet_count": insider_count,
        "bundle_pct":           bundle_pct,
        "dev_wallet_pct":       dev_wallet_pct,
        "dev_sold":             dev_sold,
        "lp_locked":            lp_locked,
        "lp_lock_pct":          float(locked_pct) if locked_pct else None,
        "mint_disabled":        mint_disabled,
        "freeze_disabled":      freeze_disabled,
        "ownership_renounced":  ownership_renounced,
        "metadata_mutable":     metadata_mutable,
        "risk_flags":           [r for r in risk_names if r],
        "rugcheck_score":       data.get("score"),
    }
