"""
GMGN OpenAPI client for KhaiScan.

Host:  https://openapi.gmgn.ai
Auth:  X-APIKEY header + timestamp + client_id query params (no signing for reads).

Endpoints used:
  /v1/token/info             -- holder count, market cap, bundle ratio
  /v1/token/security         -- mint/freeze authority, owner
  /v1/market/token_top_holders -- top holder concentration
  /v1/market/token_top_traders -- smart money activity (confirmed working)

How to get your API key (one-time, free):
  1. Run: npx gmgn-cli config        (already done)
  2. Open the printed URL in browser while logged into gmgn.ai
  3. Copy the API key (format: gmgn_xxxx...)
  4. Add to .env:  GMGN_API_KEY=gmgn_xxxx...
"""
from __future__ import annotations
import logging
import uuid
import time
from typing import Optional
import aiohttp
import config
from api.base import safe_get

logger = logging.getLogger(__name__)

_BASE = "https://openapi.gmgn.ai"
_USER_AGENT = "KhaiScan/1.0"

# Smart money wallet labels from GMGN
_SMART_LABELS = {"kol", "smart_degen", "fresh_wallet", "renowned", "sniper"}


def _headers() -> dict:
    return {
        "X-APIKEY":     config.GMGN_API_KEY,
        "Content-Type": "application/json",
        "User-Agent":   _USER_AGENT,
        "Accept":       "application/json",
    }


def _auth_params() -> dict:
    return {
        "timestamp": str(int(time.time())),
        "client_id": str(uuid.uuid4()),
    }


def _has_key() -> bool:
    return bool(config.GMGN_API_KEY)


async def _get(
    session: aiohttp.ClientSession,
    path: str,
    params: dict,
    label: str,
) -> Optional[dict]:
    if not _has_key():
        return None
    all_params = {**params, **_auth_params()}
    return await safe_get(
        session,
        f"{_BASE}{path}",
        headers=_headers(),
        params=all_params,
        label=label,
    )


async def get_smart_money(address: str, session: aiohttp.ClientSession) -> Optional[dict]:
    """
    Fetch smart money activity using /v1/market/token_top_traders.

    This endpoint returns the top traders for a token with wallet type labels.
    We use these labels to identify smart money wallets.
    Falls back to the legacy public endpoint if no API key.
    """
    if _has_key():
        result = await _get_smart_money_openapi(address, session)
        if result:
            return result

    # Fallback: legacy public endpoint (may rate-limit)
    return await _get_smart_money_fallback(address, session)


async def _get_smart_money_openapi(address: str, session: aiohttp.ClientSession) -> Optional[dict]:
    """Use GMGN OpenAPI token_top_traders to infer smart money activity."""
    data = await _get(
        session,
        "/v1/market/token_top_traders",
        {"chain": "sol", "address": address, "limit": "20", "orderby": "profit", "direction": "desc"},
        "GMGN/top_traders",
    )
    if not data:
        return None

    traders = data.get("data") or data.get("list") or []
    if not isinstance(traders, list):
        # Try nested data structure
        inner = data.get("data")
        if isinstance(inner, dict):
            traders = inner.get("list") or inner.get("traders") or []

    if not traders:
        return None

    buy_count  = 0
    sell_count = 0
    smart_count = 0

    for trader in traders:
        # Check if this is a smart money wallet by address type or tags
        addr_type = trader.get("addr_type", 0)
        tags = trader.get("tags") or []
        label = (trader.get("label") or "").lower()

        is_smart = (
            addr_type in (1, 2, 3)  # GMGN addr_type: 1=KOL, 2=smart degen, 3=renowned
            or any(t in _SMART_LABELS for t in tags)
            or any(k in label for k in _SMART_LABELS)
        )

        if is_smart:
            smart_count += 1

        # Buy/sell net position
        amount_cur = _to_float(trader.get("amount_cur", 0))  # current holding
        amount_sold = _to_float(trader.get("sell_amount_cur", 0))
        if amount_cur and amount_cur > 0:
            buy_count += 1
        if amount_sold and amount_sold > 0:
            sell_count += 1

    total = buy_count + sell_count
    if buy_count > sell_count * 1.5:
        bias = "bullish"
    elif sell_count > buy_count * 1.5:
        bias = "bearish"
    else:
        bias = "neutral"

    # Only report smart money if we found meaningful data
    if total == 0 and smart_count == 0:
        return None

    return {
        "smart_money_wallet_count": smart_count if smart_count > 0 else total,
        "smart_money_net_bias":     bias,
        "smart_money_buy_count":    buy_count,
        "smart_money_sell_count":   sell_count,
    }


async def get_token_info(address: str, session: aiohttp.ClientSession) -> Optional[dict]:
    """Fetch token info from GMGN OpenAPI /v1/token/info."""
    data = await _get(
        session,
        "/v1/token/info",
        {"chain": "sol", "address": address},
        "GMGN/token_info",
    )
    if not data:
        return None

    payload = data.get("data") or data
    result: dict = {}

    for src, dst in [("holder_count", "holder_count"), ("holders", "holder_count")]:
        v = payload.get(src)
        if v is not None:
            try:
                result["holder_count"] = int(v)
                break
            except (ValueError, TypeError):
                pass

    for src in ("market_cap", "usd_market_cap"):
        v = payload.get(src)
        if v is not None:
            result["market_cap"] = _to_float(v)
            break

    for src in ("volume_24h", "volume24h"):
        v = payload.get(src)
        if v is not None:
            result["volume_24h"] = _to_float(v)
            break

    result["image_url"] = payload.get("logo") or payload.get("image_uri") or payload.get("icon")

    # Bundle ratio (0.0-1.0 -> %)
    for src in ("bundle_ratio", "bundleRatio"):
        v = payload.get(src)
        if v is not None:
            f = _to_float(v, scale=100)
            if f:
                result["bundle_pct"] = f
            break

    return result or None


async def get_top_holders(address: str, session: aiohttp.ClientSession) -> Optional[dict]:
    """Fetch top holder concentration via /v1/market/token_top_holders."""
    data = await _get(
        session,
        "/v1/market/token_top_holders",
        {"chain": "sol", "address": address, "limit": "10"},
        "GMGN/top_holders",
    )
    if not data:
        return None

    holders = data.get("data") or []
    if not isinstance(holders, list) or not holders:
        return None

    pcts = []
    for h in holders:
        pct = h.get("percent") or h.get("pct") or h.get("ratio")
        if pct is not None:
            try:
                pcts.append(float(pct))
            except (ValueError, TypeError):
                pass

    if not pcts:
        return None

    return {
        "top10_pct":           sum(pcts),
        "largest_wallet_pct":  pcts[0],
    }


# -----------------------------------------------------------------------
# Fallback: legacy public endpoint
# -----------------------------------------------------------------------

_FALLBACK_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": "https://gmgn.ai/",
    "Accept":  "application/json",
}


async def _get_smart_money_fallback(
    address: str, session: aiohttp.ClientSession
) -> Optional[dict]:
    data = await safe_get(
        session,
        f"https://gmgn.ai/api/v1/smartmoney/sol/tokeninfo/{address}",
        headers=_FALLBACK_HEADERS,
        label="GMGN/SmartMoney(fallback)",
    )
    if not data or not data.get("data"):
        return None

    payload = data["data"]
    buy  = int(payload.get("smart_buy_count", 0) or 0)
    sell = int(payload.get("smart_sell_count", 0) or 0)
    total = buy + sell

    if buy > sell * 1.5:
        bias = "bullish"
    elif sell > buy * 1.5:
        bias = "bearish"
    else:
        bias = "neutral"

    return {
        "smart_money_wallet_count": total,
        "smart_money_net_bias":     bias,
        "smart_money_buy_count":    buy,
        "smart_money_sell_count":   sell,
    }


def _to_float(val, scale: float = 1) -> Optional[float]:
    try:
        return float(val) * scale if val is not None else None
    except (ValueError, TypeError):
        return None
