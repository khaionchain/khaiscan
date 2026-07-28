"""
GeckoTerminal API collector (EVM fallback).

Endpoint: GET https://api.geckoterminal.com/api/v2/networks/{network}/tokens/{address}

Used as a fallback when DexScreener doesn't return sufficient data for EVM tokens.
Free, no API key required.
"""
from __future__ import annotations
import logging
from typing import Optional
import aiohttp
from api.base import safe_get

logger = logging.getLogger(__name__)

_BASE = "https://api.geckoterminal.com/api/v2/networks"

# DexScreener chain slug → GeckoTerminal network ID
CHAIN_NETWORK_MAP: dict[str, str] = {
    "ethereum":  "eth",
    "bsc":       "bsc",
    "base":      "base",
    "polygon":   "polygon_pos",
    "arbitrum":  "arbitrum",
    "optimism":  "optimism",
    "avalanche": "avax",
    "fantom":    "fantom",
    "linea":     "linea",
    "zksync":    "zksync",
}


async def get_token_data(
    address: str,
    chain: str,
    session: aiohttp.ClientSession,
) -> Optional[dict]:
    """
    Fetch token market data from GeckoTerminal.

    Returns a normalised dict or None on failure.
    """
    network = CHAIN_NETWORK_MAP.get(chain)
    if not network:
        return None

    data = await safe_get(
        session,
        f"{_BASE}/{network}/tokens/{address}",
        headers={"Accept": "application/json;version=20230302"},
        label=f"GeckoTerminal/{chain}",
    )
    if not data or "data" not in data:
        return None

    attrs = data["data"].get("attributes", {})

    return {
        "name":          attrs.get("name"),
        "symbol":        attrs.get("symbol"),
        "price_usd":     _to_float(attrs.get("price_usd")),
        "market_cap":    _to_float(attrs.get("market_cap_usd")),
        "fdv":           _to_float(attrs.get("fdv_usd")),
        "volume_24h":    _to_float(attrs.get("volume_usd", {}).get("h24")),
    }


def _to_float(val) -> Optional[float]:
    try:
        return float(val) if val is not None else None
    except (ValueError, TypeError):
        return None
