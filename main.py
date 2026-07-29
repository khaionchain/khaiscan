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

async def _keep_alive_loop():
    """Ping health check endpoint every 5 minutes to prevent Render Free Tier from spinning down."""
    ext_url = os.getenv("RENDER_EXTERNAL_URL")
    url = f"{ext_url.rstrip('/')}/health" if ext_url else f"http://127.0.0.1:{config.PORT}/health"

    await asyncio.sleep(10)  # Wait for web server startup
    logger.info("Keep-alive self-pinger active for %s", url)

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(url, timeout=10) as resp:
                    logger.debug("Keep-alive ping to %s status %s", url, resp.status)
            except Exception as err:
                logger.debug("Keep-alive ping failed: %s", err)
            await asyncio.sleep(300)  # Ping every 5 minutes (300s)


async def _run_polling(bot: Bot, dp: Dispatcher):
    logger.info("Starting in polling mode (with health server on port %s)…", config.PORT)
    await bot.delete_webhook(drop_pending_updates=True)

    # Start a dummy health-check web server so Render Free Web Service port scan passes
    try:
        from aiohttp import web
        app = web.Application()
        app.router.add_get("/", lambda r: web.Response(text="KhaiScan bot is live!"))
        app.router.add_get("/health", lambda r: web.Response(text="OK"))
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", config.PORT)
        await site.start()
        logger.info("Health check server active on port %s", config.PORT)

        # Launch background keep-alive task to prevent Render 15-minute inactivity sleep
        asyncio.create_task(_keep_alive_loop())
    except Exception as exc:
        logger.warning("Could not start health check server (port %s): %s", config.PORT, exc)

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
