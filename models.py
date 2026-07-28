"""
KhaiScan — Data models (dataclasses) for the entire pipeline.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


# ──────────────────────────────────────────────────────────────────────
# Token Data — assembled from all API collectors
# ──────────────────────────────────────────────────────────────────────
@dataclass
class TokenData:
    address: str
    chain: str  # 'solana', 'ethereum', 'bsc', 'base', 'arbitrum', etc.

    # ── Identity ──────────────────────────────────────────────────────
    name: Optional[str] = None
    symbol: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None

    # Social links (fed into lore engine for richer narrative)
    website: Optional[str] = None
    twitter: Optional[str] = None
    telegram: Optional[str] = None

    # ── Market ────────────────────────────────────────────────────────
    price_usd: Optional[float] = None
    market_cap: Optional[float] = None
    fdv: Optional[float] = None
    volume_24h: Optional[float] = None
    liquidity_usd: Optional[float] = None
    age_days: Optional[int] = None
    created_at_ts: Optional[float] = None  # Unix timestamp (seconds) of pair creation
    total_supply: Optional[float] = None
    dex_name: Optional[str] = None        # e.g. "Raydium", "Uniswap"
    pair_address: Optional[str] = None

    # ── Status ────────────────────────────────────────────────────────
    is_pre_migration: bool = False
    bonding_curve_pct: Optional[float] = None  # % progress on Pump.fun

    # ── Security ──────────────────────────────────────────────────────
    is_honeypot: Optional[bool] = None
    mint_disabled: Optional[bool] = None
    freeze_disabled: Optional[bool] = None   # Solana freeze authority burned
    ownership_renounced: Optional[bool] = None
    has_blacklist: Optional[bool] = None
    is_proxy: Optional[bool] = None
    buy_tax: Optional[float] = None        # Percentage (0–100)
    sell_tax: Optional[float] = None

    # ── Holders ───────────────────────────────────────────────────────
    holder_count: Optional[int] = None
    top10_pct: Optional[float] = None       # % held by top 10 wallets
    largest_wallet_pct: Optional[float] = None
    lp_locked: Optional[bool] = None
    lp_lock_pct: Optional[float] = None     # % of LP that is locked

    # ── Launch ────────────────────────────────────────────────────────
    bundle_pct: Optional[float] = None      # % bought by bundlers at launch
    insider_wallet_count: Optional[int] = None

    # ── Developer ─────────────────────────────────────────────────────
    dev_wallet_pct: Optional[float] = None  # % supply held by dev
    dev_sold: Optional[bool] = None

    # ── Smart Money (Solana) ──────────────────────────────────────────
    smart_money_wallet_count: Optional[int] = None
    smart_money_net_bias: Optional[str] = None  # 'bullish', 'bearish', 'neutral'
    smart_money_avg_entry: Optional[float] = None

    # ── Risk Flags ────────────────────────────────────────────────────
    risk_flags: List[str] = field(default_factory=list)

    # ── Derived ───────────────────────────────────────────────────────
    volume_mc_ratio: Optional[float] = None
    liq_mc_ratio: Optional[float] = None

    # ── Fraud Detection ──────────────────────────────────────────────
    fake_volume_detected: bool = False
    fake_volume_reason: str = ""
    airdrop_detected: bool = False
    airdrop_reason: str = ""
    suspicious_buys_detected: bool = False
    suspicious_buys_reason: str = ""

    # ── Confidence tracking ───────────────────────────────────────────
    data_fields_total: int = 0
    data_fields_available: int = 0

    def compute_ratios(self):
        """Compute derived ratios after all collectors have run."""
        if self.volume_24h is not None and self.market_cap and self.market_cap > 0:
            self.volume_mc_ratio = self.volume_24h / self.market_cap
        if self.liquidity_usd is not None and self.market_cap and self.market_cap > 0:
            self.liq_mc_ratio = self.liquidity_usd / self.market_cap

    def update_confidence(self):
        """Calculate data completeness for confidence score."""
        key_fields = [
            self.name, self.symbol, self.price_usd, self.market_cap,
            self.volume_24h, self.liquidity_usd, self.age_days,
            self.is_honeypot, self.mint_disabled, self.ownership_renounced,
            self.top10_pct, self.largest_wallet_pct, self.bundle_pct,
            self.dev_wallet_pct, self.volume_mc_ratio, self.liq_mc_ratio,
        ]
        self.data_fields_total = len(key_fields)
        self.data_fields_available = sum(1 for f in key_fields if f is not None)


# ──────────────────────────────────────────────────────────────────────
# Rules Engine Output
# ──────────────────────────────────────────────────────────────────────
@dataclass
class MetricVerdict:
    metric: str
    display_name: str
    value: Any
    label: str
    emoji: str
    score: int      # 0–100 where 100 = ideal
    category: str


@dataclass
class RulesResult:
    verdicts: Dict[str, MetricVerdict] = field(default_factory=dict)
    security_score: float = 50.0
    holder_score: float = 50.0
    launch_score: float = 50.0
    dev_score: float = 50.0
    market_score: float = 50.0
    smart_money_score: float = 50.0


# ──────────────────────────────────────────────────────────────────────
# Lore AI Engine Output
# ──────────────────────────────────────────────────────────────────────
@dataclass
class LoreResult:
    one_line_summary: str = ""
    narrative_fit: int = 0       # 0–10
    originality: int = 0         # 0–10
    virality: int = 0            # 0–10
    comparable_tokens: List[str] = field(default_factory=list)
    lore_score: int = 0          # 0–100


# ──────────────────────────────────────────────────────────────────────
# Scoring Engine Output
# ──────────────────────────────────────────────────────────────────────
@dataclass
class ScoreResult:
    overall_score: int = 0
    confidence: float = 0.0          # 0.0–1.0
    category_scores: Dict[str, float] = field(default_factory=dict)
    strengths: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    verdict: str = "UNKNOWN"


# ──────────────────────────────────────────────────────────────────────
# Final Scan Result
# ──────────────────────────────────────────────────────────────────────
@dataclass
class ScanResult:
    token_data: Optional[TokenData] = None
    rules_result: Optional[RulesResult] = None
    lore_result: Optional[LoreResult] = None
    score_result: Optional[ScoreResult] = None
    error: Optional[str] = None
