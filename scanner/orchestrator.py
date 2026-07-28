"""
KhaiScan — Scan Orchestrator.

Runs all API collectors in parallel, merges results into TokenData,
applies the rules engine, generates lore, and calculates the final score.
"""
from __future__ import annotations
import asyncio
import logging
from typing import Optional
import aiohttp

import config
from models import TokenData, ScanResult
from scanner.detector import detect_chain_with_api
from api import dexscreener, rugcheck, goplus, helius, pumpfun, gmgn, geckoterminal, insightx
from rules.engine import apply_rules
from scoring.engine import calculate_score
from ai.lore import generate_lore
from scanner.fake_detector import detect_fakes

logger = logging.getLogger(__name__)


async def scan_token(
    address: str,
    session: aiohttp.ClientSession,
) -> ScanResult:
    """
    Main entry point: run the full scan pipeline for a contract address.

    Returns a ScanResult with all data, rules, lore, and score populated.
    """
    try:
        # ── 1. Detect chain ───────────────────────────────────────────
        address, chain = await detect_chain_with_api(address, session)
        if not chain:
            return ScanResult(error="❓ Unrecognised address format. Please paste a valid Solana or EVM contract address.")

        token_data = TokenData(address=address, chain=chain)

        # ── 2. Collect data in parallel ───────────────────────────────
        if chain == "solana":
            await _collect_solana(token_data, session)
        else:
            await _collect_evm(token_data, chain, session)

        # ── 3. Compute derived fields & detect fakes ─────────────────
        token_data.compute_ratios()
        token_data.update_confidence()

        fake_res = detect_fakes(token_data)
        for k, v in fake_res.items():
            setattr(token_data, k, v)

        # ── 4. Validate we have enough to work with ───────────────────
        if not token_data.name and not token_data.symbol:
            return ScanResult(
                error=(
                    "⚠️ No data found for this address.\n\n"
                    "This could mean:\n"
                    "• The token hasn't launched yet\n"
                    "• It's on a chain we couldn't detect\n"
                    "• The address is incorrect"
                )
            )

        # ── 5. Apply rules engine ─────────────────────────────────────
        rules_result = apply_rules(token_data)

        # ── 6. Generate AI lore ───────────────────────────────────────
        lore_result = await generate_lore(token_data)

        # ── 7. Calculate final score ──────────────────────────────────
        score_result = calculate_score(rules_result, lore_result, token_data)

        return ScanResult(
            token_data=token_data,
            rules_result=rules_result,
            lore_result=lore_result,
            score_result=score_result,
        )

    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error during scan of %s", address)
        return ScanResult(error=f"💥 Internal error: {exc}")


# ──────────────────────────────────────────────────────────────────────
# Solana data collection
# ──────────────────────────────────────────────────────────────────────

async def _collect_solana(token_data: TokenData, session: aiohttp.ClientSession):
    """Run all Solana API collectors in parallel, merge into token_data."""
    results = await asyncio.gather(
        dexscreener.get_token_data(token_data.address, session),
        rugcheck.get_report(token_data.address, session),
        helius.get_token_metadata(token_data.address, session),
        gmgn.get_smart_money(token_data.address, session),
        gmgn.get_token_info(token_data.address, session),
        gmgn.get_top_holders(token_data.address, session),
        insightx.get_overview(token_data.address, "solana", session),
        pumpfun.get_coin_info(token_data.address, session),
        return_exceptions=True,
    )
    dex_data, rc_data, hel_data, sm_data, gm_info, gm_holders, ix_data, pump_data = [
        r if not isinstance(r, Exception) else None for r in results
    ]

    if pump_data and pump_data.get("is_pre_migration"):
        token_data.is_pre_migration = True
        token_data.bonding_curve_pct = pump_data.get("bonding_curve_pct")
        _apply(token_data, pump_data, [
            "name", "symbol", "description", "image_url",
            "market_cap_usd:market_cap", "total_supply",
        ])

    if dex_data:
        _apply(token_data, dex_data, [
            "name", "symbol", "price_usd", "market_cap", "fdv",
            "volume_24h", "liquidity_usd", "age_days", "created_at_ts", "dex_name",
            "pair_address", "image_url", "website", "twitter", "telegram",
        ])

    if pump_data:
        _apply_if_missing(token_data, pump_data, ["description", "image_url"])

    _merge_solana(token_data, rc_data, hel_data, sm_data, gm_info, gm_holders, ix_data)


def _merge_solana(token_data, rc_data, hel_data, sm_data, gm_info=None, gm_holders=None, ix_data=None):
    """Merge RugCheck, Helius, GMGN, and InsightX data."""

    if rc_data and not isinstance(rc_data, Exception):
        _apply(token_data, rc_data, [
            "top10_pct", "largest_wallet_pct", "holder_count",
            "insider_wallet_count", "bundle_pct",
            "dev_wallet_pct", "dev_sold",
            "lp_locked", "lp_lock_pct",
            "mint_disabled", "freeze_disabled", "ownership_renounced",
        ])
        _apply_if_missing(token_data, rc_data, ["name", "symbol"])
        if rc_data.get("risk_flags"):
            token_data.risk_flags.extend(rc_data["risk_flags"])

    if hel_data and not isinstance(hel_data, Exception):
        # Helius metadata is highest priority for identity fields
        _apply(token_data, hel_data, ["name", "symbol"])
        _apply_if_missing(token_data, hel_data, ["description", "image_url"])

    if sm_data and not isinstance(sm_data, Exception):
        _apply(token_data, sm_data, [
            "smart_money_wallet_count", "smart_money_net_bias",
        ])

    # GMGN OpenAPI enrichment (only when API key is set)
    if gm_info and not isinstance(gm_info, Exception):
        _apply_if_missing(token_data, gm_info, ["holder_count", "market_cap", "volume_24h", "image_url"])
        _apply_if_missing(token_data, gm_info, ["bundle_pct"])

    if gm_holders and not isinstance(gm_holders, Exception):
        _apply_if_missing(token_data, gm_holders, ["top10_pct", "largest_wallet_pct"])

    # InsightX enrichment -- highest priority for bundle/sniper/insider data
    if ix_data and not isinstance(ix_data, Exception):
        # InsightX bundle data overrides RugCheck (more accurate)
        _apply(token_data, ix_data, ["bundle_pct", "insider_wallet_count"])
        # Store extra InsightX fields in risk_flags for display
        sniper = ix_data.get("sniper_pct")
        cluster = ix_data.get("cluster_pct")
        if sniper and sniper > 5:
            token_data.risk_flags.append(f"Snipers: {sniper:.1f}% of supply")
        if cluster and cluster > 5:
            token_data.risk_flags.append(f"Clusters: {cluster:.1f}% of supply")
        # Store the InsightX URL on token_data for display
        if ix_data.get("insightx_url"):
            token_data.insightx_url = ix_data["insightx_url"]


# ──────────────────────────────────────────────────────────────────────
# EVM data collection
# ──────────────────────────────────────────────────────────────────────

async def _collect_evm(token_data: TokenData, chain: str, session: aiohttp.ClientSession):
    """Run all EVM API collectors in parallel, merge into token_data."""
    results = await asyncio.gather(
        dexscreener.get_token_data(token_data.address, session),
        goplus.get_security(token_data.address, chain, session),
        geckoterminal.get_token_data(token_data.address, chain, session),
        return_exceptions=True,
    )
    dex_data, gp_data, gecko_data = [
        r if not isinstance(r, Exception) else None for r in results
    ]

    if dex_data:
        _apply(token_data, dex_data, [
            "name", "symbol", "price_usd", "market_cap", "fdv",
            "volume_24h", "liquidity_usd", "age_days", "dex_name",
            "pair_address", "image_url",
        ])

    if gecko_data:
        _apply_if_missing(token_data, gecko_data, [
            "name", "symbol", "price_usd", "market_cap", "fdv", "volume_24h",
        ])

    if gp_data:
        _apply(token_data, gp_data, [
            "is_honeypot", "mint_disabled", "ownership_renounced",
            "has_blacklist", "is_proxy", "buy_tax", "sell_tax", "lp_locked",
        ])


# ──────────────────────────────────────────────────────────────────────
# Data merge helpers
# ──────────────────────────────────────────────────────────────────────

def _apply(target: TokenData, source: Optional[dict], fields: list[str]):
    """Copy fields from source dict → target dataclass (always overwrite)."""
    if not source:
        return
    for field_spec in fields:
        if ":" in field_spec:
            src_key, dst_key = field_spec.split(":", 1)
        else:
            src_key = dst_key = field_spec
        val = source.get(src_key)
        if val is not None:
            setattr(target, dst_key, val)


def _apply_if_missing(target: TokenData, source: Optional[dict], fields: list[str]):
    """Copy fields from source only if target field is currently None."""
    if not source:
        return
    for field_name in fields:
        if getattr(target, field_name, None) is None:
            val = source.get(field_name)
            if val is not None:
                setattr(target, field_name, val)
