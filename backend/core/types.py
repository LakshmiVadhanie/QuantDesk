from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class FilingType(str, Enum):
    FORM_10K = "10-K"
    FORM_10Q = "10-Q"
    FORM_8K = "8-K"


class ResearchDepth(str, Enum):
    QUICK = "quick"      # ratios + sentiment only
    FULL = "full"        # ratios + sentiment + peers + synthesis
    DEEP = "deep"        # full + historical trend analysis


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Financial domain types
# ---------------------------------------------------------------------------

class FinancialRatios(BaseModel):
    ticker: str
    period: str  # e.g. "FY2023", "Q3 2024"
    # Liquidity
    current_ratio: float | None = None
    quick_ratio: float | None = None
    cash_ratio: float | None = None
    # Leverage
    debt_to_equity: float | None = None
    interest_coverage: float | None = None
    debt_to_assets: float | None = None
    # Profitability
    gross_margin: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None
    roe: float | None = None
    roa: float | None = None
    roic: float | None = None
    # Valuation
    pe_ratio: float | None = None
    ev_ebitda: float | None = None
    price_to_book: float | None = None
    price_to_sales: float | None = None
    # Growth
    revenue_growth_yoy: float | None = None
    earnings_growth_yoy: float | None = None
    fcf_yield: float | None = None
    sources: list[str] = Field(default_factory=list)


class SentimentReport(BaseModel):
    ticker: str
    period: str
    overall_score: float  # -1.0 to 1.0
    management_confidence: float  # 0.0 to 1.0
    hedging_language_score: float  # 0.0 to 1.0; higher = more hedging
    forward_guidance_tone: str  # "positive" | "neutral" | "cautious" | "negative"
    key_themes: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    notable_quotes: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class PeerEntry(BaseModel):
    ticker: str
    name: str
    ratios: FinancialRatios
    sector: str
    market_cap_usd: float | None = None


class PeerComparison(BaseModel):
    subject_ticker: str
    sector: str
    peers: list[PeerEntry] = Field(default_factory=list)
    percentile_ranks: dict[str, float] = Field(default_factory=dict)
    summary: str = ""


class SourcePassage(BaseModel):
    text: str
    source: str  # filing type + date, e.g. "10-K 2023-12-31"
    relevance_score: float
    chunk_id: str


class ResearchReport(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    ticker: str
    company_name: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    depth: ResearchDepth = ResearchDepth.FULL
    ratios: FinancialRatios | None = None
    sentiment: SentimentReport | None = None
    peers: PeerComparison | None = None
    synthesis: str = ""
    key_risks: list[str] = Field(default_factory=list)
    key_opportunities: list[str] = Field(default_factory=list)
    grounding_passages: list[SourcePassage] = Field(default_factory=list)
    langsmith_trace_url: str = ""
    agent_steps: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------

class AgentState(BaseModel):
    """Shared state passed through the LangGraph graph."""

    run_id: str = Field(default_factory=lambda: str(uuid4()))
    ticker: str
    depth: ResearchDepth = ResearchDepth.FULL
    filing_types: list[FilingType] = Field(default_factory=lambda: [FilingType.FORM_10K, FilingType.FORM_10Q])
    include_peers: bool = True

    # Populated by retrieval agent
    retrieved_passages: list[SourcePassage] = Field(default_factory=list)

    # Populated by ratio agent
    ratios: FinancialRatios | None = None

    # Populated by sentiment agent
    sentiment: SentimentReport | None = None

    # Populated by peer comparison agent
    peers: PeerComparison | None = None

    # Final synthesis
    report: ResearchReport | None = None

    # Internal tracking
    errors: list[str] = Field(default_factory=list)
    messages: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API request/response models
# ---------------------------------------------------------------------------

class ResearchRequest(BaseModel):
    ticker: str
    depth: ResearchDepth = ResearchDepth.FULL
    include_peers: bool = True
    filing_types: list[FilingType] = Field(
        default_factory=lambda: [FilingType.FORM_10K, FilingType.FORM_10Q]
    )


class ResearchRunResponse(BaseModel):
    run_id: str
    status: RunStatus
    estimated_duration_seconds: int = 90


class ResearchResultResponse(BaseModel):
    run_id: str
    status: RunStatus
    report: ResearchReport | None = None
    error: str | None = None
    langsmith_trace_url: str = ""


class HealthResponse(BaseModel):
    status: str
    environment: str
    qdrant_connected: bool
