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
