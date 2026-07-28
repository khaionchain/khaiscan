"""
Pump.fun API collector (Solana pre-migration tokens).

Endpoint: GET https://frontend-api.pump.fun/coins/{address}

Used to detect pre-migration tokens (still on the bonding curve) and
pull their market cap, description, and image before DEX migration.
"""
from __future__ import annotations
import logging
from typing import Optional
import aiohttp
from api.base import safe_get

logger = logging.getLogger(__name__)

_BASE = "https://frontend-api.pump.fun/coins"


async def get_coin_info(address: str, session: aiohttp.ClientSession) -> Optional[dict]:
    """
    Fetch Pump.fun bonding curve info for a Solana token.

    Returns a normalised dict or None if not a Pump.fun token / not found.
    """
    data = await safe_get(session, f"{_BASE}/{address}", label="Pump.fun")
    if not data or "error" in data:
        return None

    complete = data.get("complete", True)     # True = migrated to Raydium
    bonding_progress = None

    if not complete:
        # Calculate bonding curve progress
        virtual_sol = data.get("virtual_sol_reserves", 0)
        # Pump.fun's bonding curve completes at 85 SOL
        if virtual_sol:
            bonding_progress = min(100.0, (virtual_sol / 85_000_000_000) * 100)

    return {
        "name":               data.get("name"),
        "symbol":             data.get("symbol"),
        "description":        data.get("description"),
        "image_url":          data.get("image_uri"),
        "is_pre_migration":   not complete,
        "bonding_curve_pct":  round(bonding_progress, 1) if bonding_progress is not None else None,
        "market_cap_usd":     data.get("usd_market_cap"),
        "total_supply":       data.get("total_supply"),
        "created_timestamp":  data.get("created_timestamp"),
        "migrated_to":        data.get("raydium_pool"),
    }
