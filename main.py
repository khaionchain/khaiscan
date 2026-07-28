"""
KhaiScan — Bot entry point.

Starts an aiogram 3 bot with aiohttp webhook server.
For local development, set WEBHOOK_URL="" to fall back to polling.
"""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import config
from bot.handlers import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("khaiscan")


from report.image_renderer import close_browser


def _build_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    bot = Bot(
        token=config.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)
    dp.shutdown.register(close_browser)
    return bot, dp


# ──────────────────────────────────────────────────────────────────────
# Webhook mode (production)
# ──────────────────────────────────────────────────────────────────────

def _run_webhook(bot: Bot, dp: Dispatcher):
    from aiohttp import web
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    async def on_startup(bot: Bot):
        webhook_url = f"{config.WEBHOOK_URL}{config.WEBHOOK_PATH}"
        await bot.set_webhook(
            url=webhook_url,
            secret_token=config.WEBHOOK_SECRET or None,
            drop_pending_updates=True,
        )
        logger.info("Webhook set → %s", webhook_url)

    async def on_shutdown(bot: Bot):
        await bot.delete_webhook()
        logger.info("Webhook deleted")

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()
    handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=config.WEBHOOK_SECRET or None,
    )
    handler.register(app, path=config.WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    logger.info("Starting webhook server on port %s", config.PORT)
    web.run_app(app, host="0.0.0.0", port=config.PORT)


# ──────────────────────────────────────────────────────────────────────
# Polling mode (local development)
# ──────────────────────────────────────────────────────────────────────

async def _run_polling(bot: Bot, dp: Dispatcher):
    logger.info("Starting in polling mode (local dev)…")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


# ──────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────

def main():
    config.validate()

    bot, dp = _build_bot_and_dispatcher()

    if config.WEBHOOK_URL:
        _run_webhook(bot, dp)
    else:
        logger.info("WEBHOOK_URL not set — using long polling")
        asyncio.run(_run_polling(bot, dp))


if __name__ == "__main__":
    main()
