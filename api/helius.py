"""
Helius API collector (Solana only).

Uses the DAS (Digital Asset Standard) JSON-RPC API to fetch rich token
metadata: name, symbol, description, image, supply info.

Endpoint: POST https://mainnet.helius-rpc.com/?api-key={key}
Method:   getAsset
Free tier: 1M credits/month.
"""
from __future__ import annotations
import logging
from typing import Optional
import aiohttp
import config
from api.base import safe_post

logger = logging.getLogger(__name__)


async def get_token_metadata(address: str, session: aiohttp.ClientSession) -> Optional[dict]:
    """
    Fetch rich Solana token metadata via Helius DAS API.

    Returns a normalised dict or None if unavailable.
    """
    if not config.HELIUS_API_KEY:
        logger.warning("HELIUS_API_KEY not set — skipping Helius metadata")
        return None

    payload = {
        "jsonrpc": "2.0",
        "id":      "khaiscan",
        "method":  "getAsset",
        "params":  {"id": address},
    }

    data = await safe_post(
        session,
        config.HELIUS_RPC_URL,
        json_body=payload,
        label="Helius/getAsset",
    )
    if not data or "result" not in data:
        return None

    result = data["result"]
    content = result.get("content", {})
    metadata = content.get("metadata", {})
    json_uri_data = content.get("json_uri_data") or {}
    links = content.get("links", {})

    name = metadata.get("name") or json_uri_data.get("name")
    symbol = metadata.get("symbol") or json_uri_data.get("symbol")
    description = json_uri_data.get("description") or metadata.get("description")
    image_url = links.get("image") or json_uri_data.get("image")

    return {
        "name":        name,
        "symbol":      symbol,
        "description": description,
        "image_url":   image_url,
    }


async def get_top_holders(
    address: str,
    session: aiohttp.ClientSession,
    total_supply: Optional[float] = None,
) -> Optional[dict]:
    """
    Fetch exact top 20 holder accounts via Helius RPC getTokenLargestAccounts.

    Returns:
      {
        "top10_pct": float,
        "largest_wallet_pct": float,
      }
    """
    if not config.HELIUS_API_KEY:
        return None

    payload = {
        "jsonrpc": "2.0",
        "id":      "khaiscan",
        "method":  "getTokenLargestAccounts",
        "params":  [address],
    }

    data = await safe_post(
        session,
        config.HELIUS_RPC_URL,
        json_body=payload,
        label="Helius/getTokenLargestAccounts",
    )
    if not data or "result" not in data:
        return None

    accounts = (data.get("result") or {}).get("value") or []
    if not accounts:
        return None

    amounts = []
    for acc in accounts:
        amt = acc.get("uiAmount")
        if amt is not None and amt > 0:
            amounts.append(amt)

    if not amounts:
        return None

    if not total_supply or total_supply <= 0:
        total_supply = sum(amounts) * 1.5  # estimate if total supply missing

    pcts = [round((amt / total_supply) * 100, 2) for amt in amounts]
    top10_pct = round(sum(pcts[:10]), 2)
    largest_wallet_pct = pcts[0] if pcts else None

    return {
        "top10_pct":          min(100.0, top10_pct),
        "largest_wallet_pct": min(100.0, largest_wallet_pct) if largest_wallet_pct is not None else None,
    }
