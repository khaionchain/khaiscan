"""
GoPlus Security API collector.

Solana: GET https://api.gopluslabs.io/api/v1/solana/token_security?contract_addresses={address}
EVM:    GET https://api.gopluslabs.io/api/v1/token_security/{chain_id}?contract_addresses={address}

Used for: honeypot detection, mint authority, ownership, blacklist, buy/sell tax.
Free, no API key required.
"""
from __future__ import annotations
import logging
from typing import Optional
import aiohttp
from api.base import safe_get

logger = logging.getLogger(__name__)

_BASE = "https://api.gopluslabs.io/api/v1"

# DexScreener chain slug → GoPlus chain ID
EVM_CHAIN_IDS: dict[str, str] = {
    "ethereum":  "1",
    "bsc":       "56",
    "base":      "8453",
    "polygon":   "137",
    "arbitrum":  "42161",
    "optimism":  "10",
    "avalanche": "43114",
    "fantom":    "250",
    "cronos":    "25",
    "linea":     "59144",
    "zksync":    "324",
}


async def get_security(
    address: str,
    chain: str,
    session: aiohttp.ClientSession,
) -> Optional[dict]:
    """
    Fetch security data for a token from GoPlus.

    chain: 'solana' or a DexScreener EVM chain slug.
    Returns a normalised dict or None on failure.
    """
    if chain == "solana":
        return await _solana_security(address, session)
    else:
        return await _evm_security(address, chain, session)


async def _solana_security(address: str, session: aiohttp.ClientSession) -> Optional[dict]:
    data = await safe_get(
        session,
        f"{_BASE}/solana/token_security",
        params={"contract_addresses": address},
        label="GoPlus/Solana",
    )
    if not data:
        return None

    result = (data.get("result") or {}).get(address.lower()) or \
             (data.get("result") or {}).get(address)
    if not result:
        return None

    return {
        "is_honeypot":         None,   # GoPlus Solana doesn't have honeypot field
        "mint_disabled":       _flag(result.get("mintable")) is False,
        "ownership_renounced": None,   # N/A for Solana in same way
        "has_blacklist":       None,
        "buy_tax":             None,
        "sell_tax":            None,
    }


async def _evm_security(address: str, chain: str, session: aiohttp.ClientSession) -> Optional[dict]:
    chain_id = EVM_CHAIN_IDS.get(chain)
    if not chain_id:
        logger.warning("Unknown EVM chain for GoPlus: %s", chain)
        return None

    data = await safe_get(
        session,
        f"{_BASE}/token_security/{chain_id}",
        params={"contract_addresses": address},
        label=f"GoPlus/{chain}",
    )
    if not data:
        return None

    result = (data.get("result") or {}).get(address.lower()) or \
             (data.get("result") or {}).get(address)
    if not result:
        return None

    holders = result.get("holders") or []
    top10_pct = None
    largest_wallet_pct = None
    if holders:
        try:
            pcts = [float(h.get("percent", 0)) * 100 for h in holders if h.get("percent")]
            if pcts:
                top10_pct = round(sum(pcts[:10]), 2)
                largest_wallet_pct = round(pcts[0], 2)
        except (ValueError, TypeError):
            pass

    holder_count = None
    if result.get("holder_count"):
        try:
            holder_count = int(result.get("holder_count"))
        except (ValueError, TypeError):
            pass

    return {
        "is_honeypot":         _flag(result.get("is_honeypot")),
        "mint_disabled":       _flag(result.get("is_mintable")) is False,
        "ownership_renounced": _renounced(result),
        "has_blacklist":       _flag(result.get("is_blacklisted")),
        "is_proxy":            _flag(result.get("is_proxy")),
        "buy_tax":             _tax(result.get("buy_tax")),
        "sell_tax":            _tax(result.get("sell_tax")),
        "lp_locked":           _lp_locked(result.get("lp_holders", [])),
        "top10_pct":           top10_pct,
        "largest_wallet_pct":  largest_wallet_pct,
        "holder_count":        holder_count,
    }


# ── Helpers ───────────────────────────────────────────────────────────

def _flag(val) -> Optional[bool]:
    """Convert GoPlus "0"/"1" string flags to bool."""
    if val is None:
        return None
    return str(val) == "1"


def _tax(val) -> Optional[float]:
    """Parse tax string like '0.05' → 5.0 (percentage)."""
    if val is None:
        return None
    try:
        return float(val) * 100
    except (ValueError, TypeError):
        return None


def _renounced(result: dict) -> Optional[bool]:
    """Owner is renounced when owner_address is zero-address or missing."""
    owner = result.get("owner_address", "")
    if not owner:
        return True
    zero = "0x0000000000000000000000000000000000000000"
    return owner.lower() in (zero, "")


def _lp_locked(lp_holders: list) -> Optional[bool]:
    """Return True if any LP holder is a lock contract."""
    for lp in lp_holders:
        if lp.get("is_locked") == 1 or str(lp.get("is_locked")) == "1":
            return True
    return False if lp_holders else None
