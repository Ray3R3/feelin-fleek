"""Shortlist which lots each buyer's Ralph should bother negotiating for.

Matching sees only public data (wants and lots). It never receives a max or a
floor, so it cannot leak one and nobody can game the ranking with one.

1. Filter: index lots by (category, grade), so a buyer only ever looks at lots
   it could accept. No 50M-pair cross product.
2. Rank: weighted score of price vs market, grade fit and quantity fit.
3. Keep the best lot per seller, then the top `shortlist_k` sellers.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ..core.config import CONFIG, Config
from ..core.models import GRADE_ORDER, Grade, Lot, Want


@dataclass(frozen=True)
class Match:
    buyer_id: str
    lot: Lot
    quantity: int  # pieces Ralph would ask for from this lot
    score: float


def index_lots(lots: list[Lot]) -> dict[tuple[str, Grade], list[Lot]]:
    index: dict[tuple[str, Grade], list[Lot]] = defaultdict(list)
    for lot in lots:
        index[(lot.category, lot.grade)].append(lot)
    return index


def candidates(want: Want, index: dict[tuple[str, Grade], list[Lot]]) -> list[Lot]:
    """Lots in the right category and grade with enough pieces to be worth it."""
    found = [lot for g in want.grades for lot in index.get((want.category, g), [])]
    return [lot for lot in found if lot.pieces >= want.min_quantity]


def score(want: Want, lots: list[Lot], cfg: Config = CONFIG) -> list[Match]:
    """Score each candidate lot 0..1 for this buyer."""
    if not lots:
        return []
    best = min(want.grades, key=GRADE_ORDER.index)
    qty = {lot.lot_id: min(want.quantity, lot.pieces) for lot in lots}
    # price vs market: sticker at this quantity relative to the grade's typical price,
    # rescaled so the cheapest option scores 1 and the dearest 0
    ratio = {lot.lot_id: lot.sticker_price(qty[lot.lot_id]) / cfg.base_price[lot.grade.value]
             for lot in lots}
    lo, hi = min(ratio.values()), max(ratio.values())
    matches = []
    for lot in lots:
        price = 1.0 if hi == lo else (hi - ratio[lot.lot_id]) / (hi - lo)
        grade = 1.0 if lot.grade == best else 0.5
        quantity = qty[lot.lot_id] / want.quantity
        total = cfg.w_price * price + cfg.w_grade * grade + cfg.w_quantity * quantity
        matches.append(Match(want.buyer_id, lot, qty[lot.lot_id], round(total, 4)))
    return matches


def top_sellers(matches: list[Match], k: int) -> list[Match]:
    """Best lot per seller, then the k best sellers. Ties break on lot id."""
    best: dict[str, Match] = {}
    for m in sorted(matches, key=lambda m: (-m.score, m.lot.lot_id)):
        best.setdefault(m.lot.seller_id, m)
    return list(best.values())[:k]


def shortlist(wants: list[Want], lots: list[Lot], cfg: Config = CONFIG) -> dict[str, list[Match]]:
    """buyer_id -> up to k matches, best first. Buyers with no match get []."""
    index = index_lots(lots)
    return {w.buyer_id: top_sellers(score(w, candidates(w, index), cfg), cfg.shortlist_k)
            for w in wants}
