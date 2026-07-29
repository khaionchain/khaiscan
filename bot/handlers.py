"""
KhaiScan — Telegram bot handlers.

All handlers gated to OWNER_ID — non-owner messages are silently ignored.

Commands:
  /start           — welcome message
  /help            — usage guide
  /scan <address>  — full scan
  /lore <address>  — lore-only analysis (AI narrative)

Auto-detect:
  Any message containing a Solana or EVM contract address triggers a scan.
"""
from __future__ import annotations
import asyncio
import logging
from io import BytesIO

import aiohttp
from aiogram import Bot, Router
from aiogram.types import BufferedInputFile
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

import config
from bot.messages import (
    START_MSG,
    HELP_MSG,
    SCANNING_MSG,
    UNKNOWN_ADDRESS_MSG,
    ERROR_MSG_TEMPLATE,
)
from scanner.detector import extract_addresses, detect_chain_with_api
from scanner.orchestrator import scan_token
from report.formatter import build_report, build_lore_report, get_image_url
from report.image_renderer import render_report_image
from ai.lore import generate_lore
from models import TokenData
from api import dexscreener, helius, pumpfun

logger = logging.getLogger(__name__)
router = Router()


# ──────────────────────────────────────────────────────────────────────
# Rate Limiter & Access Control
# ──────────────────────────────────────────────────────────────────────
import time
from collections import defaultdict

_user_scans = defaultdict(list)
RATE_LIMIT_MAX = 5        # max 5 scans
RATE_LIMIT_WINDOW = 60    # per 60 seconds


def _check_rate_limit(user_id: int) -> bool:
    """Check if user is under the rate limit. Owner bypasses limit."""
    if config.OWNER_ID and user_id == config.OWNER_ID:
        return True

    now = time.time()
    _user_scans[user_id] = [t for t in _user_scans[user_id] if now - t < RATE_LIMIT_WINDOW]

    if len(_user_scans[user_id]) >= RATE_LIMIT_MAX:
        return False

    _user_scans[user_id].append(now)
    return True


# ──────────────────────────────────────────────────────────────────────
# Commands
# ──────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def handle_start(message: Message):
    await message.reply(START_MSG, parse_mode="HTML")


@router.message(Command("help"))
async def handle_help(message: Message):
    await message.reply(HELP_MSG, parse_mode="HTML")


@router.message(Command("scan"))
async def handle_scan_command(message: Message, bot: Bot):
    user_id = message.from_user.id if message.from_user else 0
    if not _check_rate_limit(user_id):
        await message.reply(
            "⏱ <b>Rate limit reached.</b>\n<i>Please wait a minute before scanning another token.</i>",
            parse_mode="HTML",
        )
        return

    text = message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.reply(UNKNOWN_ADDRESS_MSG, parse_mode="HTML")
        return

    await _run_scan(message, bot, parts[1].strip())


@router.message(Command("lore"))
async def handle_lore_command(message: Message, bot: Bot):
    """
    /lore <address> — AI narrative analysis only.
    Fetches token identity then runs AI lore generation.
    """
    user_id = message.from_user.id if message.from_user else 0
    if not _check_rate_limit(user_id):
        await message.reply(
            "⏱ <b>Rate limit reached.</b>\n<i>Please wait a minute before scanning another token.</i>",
            parse_mode="HTML",
        )
        return

    text = message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.reply(
            "Usage: <code>/lore &lt;address&gt;</code>\n\nExample:\n"
            "<code>/lore 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU</code>",
            parse_mode="HTML",
        )
        return

    address = parts[1].strip()
    status_msg = await message.reply(
        "✨ <b>Generating lore analysis…</b>\n<i>Analyzing narrative…</i>",
        parse_mode="HTML",
    )

    try:
        async with aiohttp.ClientSession() as session:
            address, chain = await detect_chain_with_api(address, session)
            if not chain:
                await status_msg.edit_text("❓ Unrecognised address format.", parse_mode="HTML")
                return

            td = TokenData(address=address, chain=chain or "unknown")

            # Fetch identity in parallel
            results = await asyncio.gather(
                dexscreener.get_token_data(address, session),
                helius.get_token_metadata(address, session) if chain == "solana" else asyncio.sleep(0, result=None),
                pumpfun.get_coin_info(address, session) if chain == "solana" else asyncio.sleep(0, result=None),
                return_exceptions=True,
            )
            dex_data = results[0] if not isinstance(results[0], Exception) else None
            hel_data = results[1] if not isinstance(results[1], Exception) else None
            pump_data = results[2] if not isinstance(results[2], Exception) else None

            if dex_data:
                td.name = dex_data.get("name")
                td.symbol = dex_data.get("symbol")
                td.image_url = dex_data.get("image_url")

            if hel_data:
                td.name = hel_data.get("name") or td.name
                td.symbol = hel_data.get("symbol") or td.symbol
                td.description = hel_data.get("description")
                td.image_url = td.image_url or hel_data.get("image_url")

            if pump_data:
                td.description = td.description or pump_data.get("description")
                td.image_url = td.image_url or pump_data.get("image_url")

            # Generate lore
            lore_result = await generate_lore(td)
            report = build_lore_report(td, lore_result)

        # Send image if available
        if td.image_url:
            await _try_send_photo(bot, message, td.image_url)

        await status_msg.edit_text(report, parse_mode="HTML")

    except asyncio.TimeoutError:
        await status_msg.edit_text("⏱ Lore timed out. Try again.", parse_mode="HTML")
    except Exception as exc:
        logger.exception("Lore command error for %s", address)
        await status_msg.edit_text(
            ERROR_MSG_TEMPLATE.format(error=str(exc)), parse_mode="HTML"
        )


# ──────────────────────────────────────────────────────────────────────
# Auto-detect — pasted addresses
# ──────────────────────────────────────────────────────────────────────

@router.message()
async def handle_auto_detect(message: Message, bot: Bot):
    text = message.text or message.caption or ""
    user_id = message.from_user.id if message.from_user else 0
    logger.info("Received Telegram message from user %s: %r", user_id, text)

    addresses = extract_addresses(text)
    if not addresses:
        logger.info("No valid Solana/EVM contract address found in message: %r", text)
        return  # Not a contract address — ignore silently

    if not _check_rate_limit(user_id):
        logger.warning("User %s hit rate limit", user_id)
        await message.reply(
            "⏱ <b>Rate limit reached.</b>\n<i>Please wait a minute before scanning another token.</i>",
            parse_mode="HTML",
        )
        return

    logger.info("Starting scan for address %s extracted from user %s", addresses[0], user_id)
    await _run_scan(message, bot, addresses[0])


# ──────────────────────────────────────────────────────────────────────
# Shared scan execution
# ──────────────────────────────────────────────────────────────────────

async def _run_scan(message: Message, bot: Bot, address: str):
    """
    Full scan pipeline (Optimized for instant sub-1.5s response):
    1. Send "Scanning…" immediately
    2. Run parallel API scan
    3. Update status message IMMEDIATELY with the full text report
    4. Asynchronously render and deliver the HD visual report image right after
    """
    status_msg = await message.reply(SCANNING_MSG, parse_mode="HTML")

    try:
        async with aiohttp.ClientSession() as session:
            result = await asyncio.wait_for(
                scan_token(address, session),
                timeout=config.SCAN_TOTAL_TIMEOUT,
            )

        if result.error:
            await status_msg.edit_text(
                ERROR_MSG_TEMPLATE.format(error=result.error),
                parse_mode="HTML",
            )
            return

        # 1. Build text report & edit status message IMMEDIATELY (<1.2s response time)
        pages = build_report(result)
        try:
            await status_msg.edit_text(pages[0], parse_mode="HTML", disable_web_page_preview=True)
        except Exception as edit_err:
            logger.warning("Failed to edit status message with HTML: %s", edit_err)
            try:
                await status_msg.edit_text(pages[0], parse_mode=None, disable_web_page_preview=True)
            except Exception:
                await message.reply(pages[0], parse_mode=None, disable_web_page_preview=True)

        # Send any additional text pages
        for page in pages[1:]:
            try:
                await message.reply(page, parse_mode="HTML")
            except Exception:
                await message.reply(page, parse_mode=None)

        # 2. Fire image rendering as a non-blocking background task
        asyncio.create_task(
            _send_image_card_bg(bot, message.chat.id, message.message_id, result)
        )

    except asyncio.TimeoutError:
        await status_msg.edit_text(
            "⏱ <b>Scan timed out.</b>\n\nAPIs responding slowly. Try again.",
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.exception("Scan error for %s", address)
        await status_msg.edit_text(
            ERROR_MSG_TEMPLATE.format(error=str(exc)),
            parse_mode="HTML",
        )


async def _send_image_card_bg(bot: Bot, chat_id: int, reply_to_id: int, result: ScanResult):
    """Background task: render HD PNG image and send as follow-up photo."""
    try:
        png_bytes = await render_report_image(result)
        if png_bytes:
            td = result.token_data
            symbol = td.symbol or "?"
            photo = BufferedInputFile(file=png_bytes, filename=f"KhaiScan_{symbol}.png")
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=f"🔍 <b>KhaiScan Card</b> — <b>${symbol}</b>",
                parse_mode="HTML",
                reply_to_message_id=reply_to_id,
            )
    except Exception as img_err:
        logger.warning("Background image render failed: %s", img_err)


async def _try_send_photo(bot: Bot, message: Message, photo_url: str):
    """Attempt to send a token profile picture. Silently fails if URL is invalid."""
    try:
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=photo_url,
            reply_to_message_id=message.message_id,
        )
    except Exception as exc:
        logger.debug("Photo send failed (non-critical): %s", exc)
