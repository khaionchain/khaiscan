"""
InsightX DEX Metrics API collector.

Base URL: https://api.insightx.network
Docs:     https://docs.insightx.network/reference/dex-metrics-api-overview

Endpoints used (free tier):
  GET /v1/{network}/{address}           - Overview: bundler%, sniper%, insider%, cluster%
  GET /v1/{network}/{address}/bundlers  - Bundler wallet breakdown
  GET /v1/{network}/{address}/insiders  - Insider wallet breakdown

Network name for Solana: "solana"
Auth: API key in X-API-Key header (get free key at insightx.network)

Returns: bundle_pct, sniper_pct, insider_wallet_count, cluster_pct,
         and an embedded link to the full InsightX report.
"""
from __future__ import annotations
import logging
from typing import Optional
import aiohttp
import config
from api.base import safe_get

logger = logging.getLogger(__name__)

_BASE = "https://api.insightx.network"

# Map our chain names to InsightX network identifiers
_CHAIN_MAP = {
    "solana":    "solana",
    "ethereum":  "ethereum",
    "bsc":       "bsc",
    "base":      "base",
    "arbitrum":  "arbitrum",
    "polygon":   "polygon",
}


def _headers() -> dict:
    h = {
        "Accept": "application/json",
        "User-Agent": "KhaiScan/1.0",
    }
    if config.INSIGHTX_API_KEY:
        h["X-API-Key"] = config.INSIGHTX_API_KEY
    return h


def _network(chain: str) -> Optional[str]:
    return _CHAIN_MAP.get(chain)


def insightx_link(address: str, chain: str) -> str:
    """Build the public InsightX link for embedded display."""
    return f"https://insightx.network/token/{address}"


async def get_overview(
    address: str,
    chain: str,
    session: aiohttp.ClientSession,
) -> Optional[dict]:
    """
    Fetch DEX metrics overview from InsightX.

    Returns normalised dict with bundle_pct, sniper_pct,
    insider_wallet_count, cluster_pct, insightx_url.
    """
    network = _network(chain)
    if not network:
        return None

    data = await safe_get(
        session,
        f"{_BASE}/v1/{network}/{address}",
        headers=_headers(),
        label="InsightX/overview",
    )
    if not data:
        return None

    # InsightX response shape (based on docs):
    # {
    #   "bundler_percentage": 12.4,
    #   "sniper_percentage": 5.1,
    #   "insider_percentage": 8.3,
    #   "cluster_percentage": 3.2,
    #   "bundler_count": 4,
    #   "insider_count": 7,
    #   "sniper_count": 2,
    # }
    result = {
        "insightx_url": insightx_link(address, chain),
    }

    bundle = _pct(data, "bundler_percentage", "bundle_percentage", "bundler_pct")
    if bundle is not None:
        result["bundle_pct"] = bundle

    sniper = _pct(data, "sniper_percentage", "sniper_pct")
    if sniper is not None:
        result["sniper_pct"] = sniper

    insider = _pct(data, "insider_percentage", "insider_pct")
    if insider is not None:
        result["insider_pct"] = insider

    cluster = _pct(data, "cluster_percentage", "cluster_pct")
    if cluster is not None:
        result["cluster_pct"] = cluster

    # Wallet counts
    for src, dst in [
        ("bundler_count", "bundle_wallet_count"),
        ("insider_count", "insider_wallet_count"),
        ("sniper_count",  "sniper_wallet_count"),
    ]:
        val = data.get(src)
        if val is not None:
            try:
                result[dst] = int(val)
            except (TypeError, ValueError):
                pass

    return result if len(result) > 1 else None


async def get_bundlers(
    address: str,
    chain: str,
    session: aiohttp.ClientSession,
) -> Optional[dict]:
    """
    Fetch detailed bundler breakdown from InsightX.
    Returns bundler wallet list and total percentage.
    """
    network = _network(chain)
    if not network:
        return None

    data = await safe_get(
        session,
        f"{_BASE}/v1/{network}/{address}/bundlers",
        headers=_headers(),
        label="InsightX/bundlers",
    )
    if not data:
        return None

    result = {}
    bundle = _pct(data, "total_percentage", "bundler_percentage", "bundle_pct")
    if bundle is not None:
        result["bundle_pct"] = bundle

    wallets = data.get("wallets") or data.get("bundlers") or []
    if wallets and isinstance(wallets, list):
        result["bundle_wallet_count"] = len(wallets)

    return result or None


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

def _pct(data: dict, *keys: str) -> Optional[float]:
    """Try multiple field names and return the first float found."""
    for key in keys:
        val = data.get(key)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                continue
    return None
