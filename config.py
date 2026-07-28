"""
KhaiScan — Central configuration loaded from environment variables.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ──────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
OWNER_ID: int = int(os.getenv("OWNER_ID", "0"))

# ── AI ────────────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = "gemini-1.5-flash"

# Groq (primary lore AI -- free, no credit card)
# Get key at: https://console.groq.com/keys
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

# ── Blockchain Data ---------------------------------------------------
HELIUS_API_KEY: str = os.getenv("HELIUS_API_KEY", "")
HELIUS_RPC_URL: str = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"

# GMGN API key -- create at gmgn.ai (top right) > API Management
# Unlocks: bundle ratio, rat trader ratio, dev wallet activity
GMGN_API_KEY: str = os.getenv("GMGN_API_KEY", "")

# InsightX API key (free) -- https://insightx.network
# Unlocks: bundle%, sniper%, insider%, cluster% from DEX Metrics API
INSIGHTX_API_KEY: str = os.getenv("INSIGHTX_API_KEY", "")

# ── Webhook ───────────────────────────────────────────────────────────
WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")
WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")
WEBHOOK_PATH: str = "/webhook"
PORT: int = int(os.getenv("PORT", "8080"))

# ── API Timeouts (seconds) ────────────────────────────────────────────
API_TIMEOUT: int = 8          # Per-API timeout
SCAN_TOTAL_TIMEOUT: int = 30  # Max scan duration

# ── Validation ────────────────────────────────────────────────────────
def validate():
    """Crash early if critical config is missing."""
    errors = []
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN is not set")
    if not OWNER_ID:
        errors.append("OWNER_ID is not set")
    # GROQ_API_KEY is optional — lore will be disabled if missing
    if not GROQ_API_KEY:
        import logging
        logging.getLogger(__name__).warning(
            "GROQ_API_KEY not set — /lore command will be unavailable. "
            "Get a free key at console.groq.com/keys"
        )
    if errors:
        raise EnvironmentError(
            "KhaiScan config errors:\n" + "\n".join(f"  * {e}" for e in errors)
        )
