"""
KhaiScan — Static message templates for the Telegram bot.
"""

START_MSG = """
👋 <b>Welcome to KhaiScan</b>

I'm your personal meme coin intelligence bot.

<b>How to use:</b>
• Send me a contract address directly
• Paste one in any group I'm added to
• Use /scan &lt;address&gt;

I'll scan it across multiple on-chain sources and return a full report with:
  🛡 Security · 🚀 Launch · 👥 Holders
  💰 Market · 🧠 Dev · ✨ Lore · 💎 Smart Money
  ⚡ Decision Engine · 📝 Summary

<i>Supports Solana + all major EVM chains.</i>
""".strip()

HELP_MSG = """
📖 <b>KhaiScan — Help</b>

<b>Commands:</b>
/scan &lt;address&gt; — Scan a contract address
/start — Show welcome message
/help — Show this message

<b>Auto-scan:</b>
Just paste any contract address in the chat — no command needed.

<b>Supported chains:</b>
Solana · Ethereum · BSC · Base · Arbitrum
Polygon · Optimism · Avalanche · and more

<b>Pre-migration:</b>
Pump.fun tokens (still on bonding curve) are supported.
They'll show an ⚡ PRE-MIGRATION badge.

<b>Score guide:</b>
💎 GEM (86-100) — High conviction
✅ SOLID (71-85) — Good fundamentals
🎲 DEGEN (56-70) — Tradeable, watch risk
⚠️ RISKY (41-55) — Significant concerns
🚫 AVOID (21-40) — Multiple red flags
💀 RUG (0-20) — Do not enter

<i>All data sourced from free public APIs.
This is not financial advice.</i>
""".strip()

SCANNING_MSG = "🔍 <b>Scanning…</b>\n\n<i>Fetching on-chain data, running analysis…</i>"

UNKNOWN_ADDRESS_MSG = (
    "❓ <b>No contract address detected.</b>\n\n"
    "Usage: <code>/scan &lt;address&gt;</code>\n"
    "Or just paste the address directly."
)

RATE_LIMITED_MSG = (
    "⏳ Already scanning. Please wait for the current scan to complete."
)

ERROR_MSG_TEMPLATE = "⚠️ <b>Scan failed</b>\n\n{error}"
