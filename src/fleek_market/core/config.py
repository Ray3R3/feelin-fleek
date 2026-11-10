"""Every tunable in one place. Change a number here, rerun `make demo`.

Values are starting assumptions about how Fleek buyers and sellers behave;
see NOTES.md > Assumptions.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import Segment


@dataclass(frozen=True)
class SegmentProfile:
    """How a buyer segment behaves."""
    quantity_range: tuple[int, int]  # pieces wanted
    max_vs_list: tuple[float, float]  # private max as a fraction of typical list price
    opening_discount: float  # Ralph opens this far below sticker (0.25 == 25%)
    patience: int  # rounds before walking away
    concession_curve: float  # >1 holds firm then caves late; <1 concedes early


@dataclass(frozen=True)
class Config:
    seed: int = 7

    # --- synthetic market size (real Fleek: ~1,000 sellers, ~50,000 buyers)
    n_sellers: int = 20
    n_buyers: int = 100
    lots_per_seller: tuple[int, int] = (3, 8)

    # --- what a lot is
    categories: tuple[str, ...] = (
        "tees", "denim", "jackets", "knitwear", "sportswear", "dresses",
    )
    lot_pieces: tuple[int, ...] = (50, 100, 250, 500)
    # typical list price per piece by grade, GBP
    base_price: dict[str, float] = field(
        default_factory=lambda: {"A": 9.0, "B": 5.0, "C": 2.5}
    )
    price_noise: float = 0.20  # sellers' list prices vary +/- this much

    # --- seller pricing: published bulk tiers (min pieces, discount)
    tiers: tuple[tuple[int, float], ...] = ((100, 0.05), (250, 0.10), (500, 0.15))
    # private floor as a fraction of list price
    floor_vs_list: tuple[float, float] = (0.75, 0.85)
    seller_opening_markup: float = 0.0  # Tommy anchors at sticker + this
    seller_patience: int = 6
    seller_concession_curve: float = 1.5

    # --- buyer segments
    segment_mix: dict[Segment, float] = field(
        default_factory=lambda: {
            Segment.HOBBYIST: 0.70, Segment.PRO: 0.30,
        }
    )
    segments: dict[Segment, SegmentProfile] = field(
        default_factory=lambda: {
            Segment.HOBBYIST: SegmentProfile((50, 100), (0.70, 0.95), 0.15, 4, 0.8),
            Segment.PRO: SegmentProfile((250, 500), (0.72, 0.92), 0.25, 6, 1.6),
        }
    )

    # --- matching
    shortlist_k: int = 3  # sellers each Ralph actually negotiates with
    w_price: float = 0.5
    w_grade: float = 0.3
    w_quantity: float = 0.2

    # --- negotiation
    max_rounds: int = 6  # hard cap regardless of patience
    price_tick: float = 0.01  # prices rounded to the penny
    # agents stop conceding this far short of their limit. Each agent draws its
    # own margin privately; a fixed one would let anyone back out the limit
    # from a final offer
    limit_margin: tuple[float, float] = (0.02, 0.06)

    # --- marketplace
    commission_rate: float = 0.15  # Fleek's take on GMV
    # a no-deal whose best counter is within this of the buyer's own max is a
    # near miss, flagged for an account-manager intro rather than written off
    near_miss_pct: float = 0.05

    # --- optional voice layer (make demo-voice)
    voice_model: str = "gpt-4.1-mini"  # small and fast; it only words one sentence
    voice_timeout: float = 5.0  # seconds per call before falling back to the template


CONFIG = Config()
