"""
KhaiScan — Shared async HTTP helpers for all API collectors.
"""
from __future__ import annotations
import asyncio
import logging
from typing import Any, Optional
import aiohttp
import config

logger = logging.getLogger(__name__)

# Browser-like headers to avoid bot detection on some APIs
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}


async def safe_get(
    session: aiohttp.ClientSession,
    url: str,
    *,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    timeout: int = config.API_TIMEOUT,
    label: str = "",
) -> Optional[Any]:
    """
    Perform a GET request and return parsed JSON, or None on any failure.
    Never raises — all exceptions are caught and logged.
    """
    merged_headers = {**DEFAULT_HEADERS, **(headers or {})}
    try:
        async with session.get(
            url,
            params=params,
            headers=merged_headers,
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as resp:
            if resp.status == 200:
                return await resp.json(content_type=None)
            logger.warning(
                "API %s returned HTTP %s — %s", label or url, resp.status, url
            )
            return None
    except asyncio.TimeoutError:
        logger.warning("API timeout: %s", label or url)
        return None
    except Exception as exc:
        logger.warning("API error (%s): %s", label or url, exc)
        return None


async def safe_post(
    session: aiohttp.ClientSession,
    url: str,
    *,
    json_body: Any = None,
    headers: Optional[dict] = None,
    timeout: int = config.API_TIMEOUT,
    label: str = "",
) -> Optional[Any]:
    """
    Perform a POST request and return parsed JSON, or None on any failure.
    """
    merged_headers = {**DEFAULT_HEADERS, **(headers or {})}
    try:
        async with session.post(
            url,
            json=json_body,
            headers=merged_headers,
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as resp:
            if resp.status == 200:
                return await resp.json(content_type=None)
            logger.warning(
                "API %s POST returned HTTP %s", label or url, resp.status
            )
            return None
    except asyncio.TimeoutError:
        logger.warning("API POST timeout: %s", label or url)
        return None
    except Exception as exc:
        logger.warning("API POST error (%s): %s", label or url, exc)
        return None
