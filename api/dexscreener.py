"""
DexScreener API collector.

Endpoint: GET https://api.dexscreener.com/latest/dex/tokens/{address}

Returns the highest-liquidity pair for any token across all supported chains.
Used for: price, market cap, 24h volume, liquidity, pair age, DEX name, image URL.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional
import aiohttp
from api.base import safe_get

logger = logging.getLogger(__name__)

_BASE = "https://api.dexscreener.com/latest/dex/tokens"


async def get_token_data(address: str, session: aiohttp.ClientSession) -> Optional[dict]:
    """
    Fetch the best trading pair for a token from DexScreener.

    Returns a normalised dict or None if token not found / not migrated.
    """
    data = await safe_get(session, f"{_BASE}/{address}", label="DexScreener")
    if not data or not data.get("pairs"):
        # Fallback: try searching by pair address or query
        data = await safe_get(session, f"https://api.dexscreener.com/latest/dex/search?q={address}", label="DexScreener/Search")
        if not data or not data.get("pairs"):
            return None

    # Pick the pair with the highest USD liquidity
    pairs = [p for p in data["pairs"] if p.get("liquidity", {}).get("usd", 0) > 0]
    if not pairs:
        pairs = data["pairs"]

    best = max(pairs, key=lambda p: p.get("liquidity", {}).get("usd") or 0)

    # Age in days + raw timestamp for sub-day precision
    age_days: Optional[int] = None
    created_ts_out: Optional[float] = None
    created_at = best.get("pairCreatedAt")
    if created_at:
        try:
            created_ts = int(created_at) / 1000  # ms → s
            created_ts_out = created_ts
            age_days = (datetime.now(timezone.utc).timestamp() - created_ts) // 86400
            age_days = int(age_days)
        except (ValueError, TypeError):
            pass

    base_token = best.get("baseToken", {})
    liq = best.get("liquidity", {})
    vol = best.get("volume", {})
    info = best.get("info", {}) or {}

    # Image and social links from DexScreener info block
    image_url = info.get("imageUrl") or info.get("image")

    # Social links for lore engine
    socials = info.get("socials") or []
    website  = info.get("websites", [{}])[0].get("url") if info.get("websites") else None
    twitter  = None
    telegram = None
    for s in socials:
        stype = (s.get("type") or "").lower()
        url   = s.get("url") or ""
        if "twitter" in stype or "x.com" in url or "twitter.com" in url:
            twitter = url
        elif "telegram" in stype or "t.me" in url:
            telegram = url
        elif not website and "http" in url:
            website = url

    return {
        "name":          base_token.get("name"),
        "symbol":        base_token.get("symbol"),
        "price_usd":     _to_float(best.get("priceUsd")),
        "market_cap":    _to_float(best.get("marketCap")),
        "fdv":           _to_float(best.get("fdv")),
        "volume_24h":    _to_float(vol.get("h24")),
        "liquidity_usd": _to_float(liq.get("usd")),
        "age_days":      age_days,
        "created_at_ts": created_ts_out,
        "dex_name":      best.get("dexId", "").title(),
        "pair_address":  best.get("pairAddress"),
        "chain_id":      best.get("chainId"),
        "image_url":     image_url,
        "website":       website,
        "twitter":       twitter,
        "telegram":      telegram,
    }


def _to_float(val) -> Optional[float]:
    try:
        return float(val) if val is not None else None
    except (ValueError, TypeError):
        return None
