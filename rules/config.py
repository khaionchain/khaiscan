"""
KhaiScan Rules Engine — Threshold configuration.

Each rule defines:
  - display:    Human-readable metric name
  - category:   Which scoring category it belongs to
  - type:       'range' or 'boolean'
  - thresholds: (min, max_exclusive, label, emoji, score_0_to_100)
  - values:     For boolean rules: {True: (...), False: (...), None: (...)}

Score meanings:
  100 = perfect / no risk
   75 = good
   50 = neutral / unknown
   30 = elevated concern
    0 = critical risk / rug signal
"""

from math import inf

RULES: dict = {

    # ──────────────────────────────────────────────────────────────────
    # SECURITY
    # ──────────────────────────────────────────────────────────────────
    "is_honeypot": {
        "display": "Honeypot Risk",
        "category": "security",
        "type": "boolean",
        "values": {
            False: ("None detected", "🟢", 100),
            True:  ("⚠️ HONEYPOT DETECTED", "🔴", 0),
            None:  ("Unable to verify", "⚪", 40),
        },
    },
    "mint_disabled": {
        "display": "Mint Authority",
        "category": "security",
        "type": "boolean",
        "values": {
            True:  ("Disabled", "🟢", 100),
            False: ("Still active", "🔴", 15),
            None:  ("Unknown", "⚪", 45),
        },
    },
    "ownership_renounced": {
        "display": "Ownership",
        "category": "security",
        "type": "boolean",
        "values": {
            True:  ("Renounced", "🟢", 100),
            False: ("Not renounced", "🟡", 40),
            None:  ("Unknown", "⚪", 50),
        },
    },
    "has_blacklist": {
        "display": "Blacklist Function",
        "category": "security",
        "type": "boolean",
        # No blacklist = good. Having one is a warning, not necessarily fatal.
        "values": {
            False: ("No function", "🟢", 100),
            True:  ("Present — caution", "🟡", 40),
            None:  ("Unknown", "⚪", 60),
        },
    },
    "buy_tax": {
        "display": "Buy Tax",
        "category": "security",
        "type": "range",
        "thresholds": [
            (0,    0.001, "0%",                  "🟢", 100),
            (0,    5,     "<5% — acceptable",     "🟢",  80),
            (5,    10,    "Moderate tax",         "🟡",  50),
            (10,   100,   "High tax — avoid",     "🔴",  10),
        ],
    },
    "sell_tax": {
        "display": "Sell Tax",
        "category": "security",
        "type": "range",
        "thresholds": [
            (0,    0.001, "0%",                  "🟢", 100),
            (0,    5,     "<5% — acceptable",     "🟢",  80),
            (5,    10,    "Moderate tax",         "🟡",  50),
            (10,   100,   "High tax — avoid",     "🔴",  10),
        ],
    },

    # ──────────────────────────────────────────────────────────────────
    # HOLDER HEALTH
    # ──────────────────────────────────────────────────────────────────
    "top10_pct": {
        "display": "Top 10 Holdings",
        "category": "holders",
        "type": "range",
        "thresholds": [
            (0,   30,  "Healthy",          "🟢", 100),
            (30,  40,  "Moderate",         "🟡",  65),
            (40,  60,  "Concentrated",     "🟠",  35),
            (60,  100, "High Risk",        "🔴",  10),
        ],
    },
    "largest_wallet_pct": {
        "display": "Largest Wallet",
        "category": "holders",
        "type": "range",
        "thresholds": [
            (0,   3.5,  "Excellent",       "🟢", 100),
            (3.5, 5,    "Good",            "🟢",  80),
            (5,   10,   "Watch",           "🟡",  50),
            (10,  100,  "Whale alert",     "🔴",  15),
        ],
    },
    "lp_locked": {
        "display": "LP Lock",
        "category": "holders",
        "type": "boolean",
        "values": {
            True:  ("Locked", "🟢", 100),
            False: ("Not locked", "🔴", 10),
            None:  ("Unknown", "⚪", 40),
        },
    },

    # ──────────────────────────────────────────────────────────────────
    # LAUNCH ANALYSIS
    # ──────────────────────────────────────────────────────────────────
    "bundle_pct": {
        "display": "Bundle Activity",
        "category": "launch",
        "type": "range",
        "thresholds": [
            (0,   5,   "Excellent — clean launch",      "🟢", 100),
            (5,   10,  "Acceptable",                    "🟢",  75),
            (10,  15,  "Elevated",                      "🟡",  50),
            (15,  100, "High Risk — manipulated launch", "🔴",  10),
        ],
    },
    "insider_wallet_count": {
        "display": "Insider Wallets",
        "category": "launch",
        "type": "range",
        "thresholds": [
            (0,   5,   "Very low",               "🟢", 100),
            (5,   15,  "Moderate",               "🟡",  60),
            (15,  30,  "High",                   "🟠",  30),
            (30,  inf, "Very high — caution",    "🔴",  10),
        ],
    },

    # ──────────────────────────────────────────────────────────────────
    # DEVELOPER ANALYSIS
    # ──────────────────────────────────────────────────────────────────
    "dev_wallet_pct": {
        "display": "Dev Holdings",
        "category": "developer",
        "type": "range",
        "thresholds": [
            (0,   0.5,  "Minimal",           "🟢", 100),
            (0.5, 2,    "Low",               "🟢",  80),
            (2,   5,    "Moderate",          "🟡",  50),
            (5,   100,  "High — watch dev",  "🔴",  15),
        ],
    },
    "dev_sold": {
        "display": "Dev Sold",
        "category": "developer",
        "type": "boolean",
        "values": {
            False: ("No sell detected", "🟢", 100),
            True:  ("Dev sold — bearish", "🔴", 10),
            None:  ("Unknown", "⚪", 50),
        },
    },

    # ──────────────────────────────────────────────────────────────────
    # MARKET ACTIVITY
    # ──────────────────────────────────────────────────────────────────
    "volume_mc_ratio": {
        "display": "Volume / MC",
        "category": "market",
        "type": "range",
        "thresholds": [
            (0,   0.1,  "Very weak",      "🔴",  10),
            (0.1, 0.5,  "Weak",           "🟡",  40),
            (0.5, 1,    "Healthy",        "🟢",  65),
            (1,   3,    "Strong",         "🟢",  85),
            (3,   inf,  "Very Strong",    "🟢", 100),
        ],
    },
    "liq_mc_ratio": {
        "display": "Liquidity / MC",
        "category": "market",
        "type": "range",
        "thresholds": [
            (0,    0.05, "Thin — high slippage", "🔴",  10),
            (0.05, 0.10, "Fair",                 "🟡",  50),
            (0.10, 0.20, "Healthy",              "🟢",  75),
            (0.20, inf,  "Very Healthy",         "🟢", 100),
        ],
    },

    # ──────────────────────────────────────────────────────────────────
    # SMART MONEY (Solana only)
    # ──────────────────────────────────────────────────────────────────
    "smart_money_wallet_count": {
        "display": "Smart Wallets",
        "category": "smart_money",
        "type": "range",
        "thresholds": [
            (0,   1,   "None",              "⚪",  40),
            (1,   5,   "Low interest",     "🟡",  60),
            (5,   15,  "Notable interest", "🟢",  80),
            (15,  inf, "High interest",    "🟢", 100),
        ],
    },
}

# Category weight in final score (must sum to 1.0)
CATEGORY_WEIGHTS: dict = {
    "security":    0.25,
    "holders":     0.20,
    "launch":      0.15,
    "market":      0.15,
    "lore":        0.10,
    "developer":   0.10,
    "smart_money": 0.05,
}

# Verdict label thresholds
VERDICT_MAP: list = [
    (0,  20,  "RUG"),
    (21, 40,  "AVOID"),
    (41, 55,  "RISKY"),
    (56, 70,  "DEGEN"),
    (71, 85,  "SOLID"),
    (86, 100, "GEM"),
]

VERDICT_EMOJI: dict = {
    "RUG":    "💀",
    "AVOID":  "🚫",
    "RISKY":  "⚠️",
    "DEGEN":  "🎲",
    "SOLID":  "✅",
    "GEM":    "💎",
    "UNKNOWN": "❓",
}
