"""Seeded synthetic market: sellers' lots, buyers' wants, and their private limits.

`Market` is the simulator's view of the world, so it holds both public and
private data. Public parts (lots, wants) go to matching; each secret is handed
only to the one agent that owns it.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from ..core.config import CONFIG, Config
from ..core.models import GRADE_ORDER, Grade, Lot, Segment, Tier, Want
from ..core.private import BuyerLimits, SellerLimits


@dataclass
class Market:
    lots: list[Lot]
    wants: list[Want]
    floors: dict[str, SellerLimits]  # lot_id -> secret, only for that lot's Tommy
    maxes: dict[str, BuyerLimits]  # buyer_id -> secret, only for that buyer's Ralph

    @property
    def seller_ids(self) -> list[str]:
        return sorted({lot.seller_id for lot in self.lots})


def _tick(price: float, cfg: Config) -> float:
    return round(round(price / cfg.price_tick) * cfg.price_tick, 2)


def _make_lots(rng: random.Random, cfg: Config) -> tuple[list[Lot], dict[str, SellerLimits]]:
    tiers = tuple(Tier(m, d) for m, d in cfg.tiers)
    lots, floors = [], {}
    for s in range(1, cfg.n_sellers + 1):
        seller_id = f"S{s:02d}"
        for n in range(1, rng.randint(*cfg.lots_per_seller) + 1):
            grade = rng.choice(GRADE_ORDER)
            noise = rng.uniform(-cfg.price_noise, cfg.price_noise)
            list_price = _tick(cfg.base_price[grade.value] * (1 + noise), cfg)
            lot = Lot(
                lot_id=f"{seller_id}-L{n}",
                seller_id=seller_id,
                category=rng.choice(cfg.categories),
                grade=grade,
                pieces=rng.choice(cfg.lot_pieces),
                list_price=list_price,
                tiers=tiers,
            )
            lots.append(lot)
            floors[lot.lot_id] = SellerLimits(_tick(list_price * rng.uniform(*cfg.floor_vs_list), cfg))
    return lots, floors


def _accepted_grades(rng: random.Random) -> frozenset[Grade]:
    """A best acceptable grade, sometimes also the grade below it."""
    i = rng.randrange(len(GRADE_ORDER))
    grades = {GRADE_ORDER[i]}
    if i + 1 < len(GRADE_ORDER) and rng.random() < 0.5:
        grades.add(GRADE_ORDER[i + 1])
    return frozenset(grades)


def best_grade(grades: frozenset[Grade]) -> Grade:
    return min(grades, key=GRADE_ORDER.index)


def _make_wants(rng: random.Random, cfg: Config) -> tuple[list[Want], dict[str, BuyerLimits]]:
    segments = list(cfg.segment_mix)
    weights = [cfg.segment_mix[s] for s in segments]
    wants, maxes = [], {}
    for b in range(1, cfg.n_buyers + 1):
        buyer_id = f"B{b:03d}"
        segment: Segment = rng.choices(segments, weights)[0]
        profile = cfg.segments[segment]
        lo, hi = profile.quantity_range
        grades = _accepted_grades(rng)
        wants.append(Want(
            buyer_id=buyer_id,
            segment=segment,
            category=rng.choice(cfg.categories),
            grades=grades,
            quantity=rng.randrange(lo, hi + 1, 10),
            min_quantity=lo,  # below the segment's usual size isn't worth the shipping
        ))
        # max is set against the typical price of the best grade they'd take
        typical = cfg.base_price[best_grade(grades).value]
        maxes[buyer_id] = BuyerLimits(_tick(typical * rng.uniform(*profile.max_vs_list), cfg))
    return wants, maxes


def generate(cfg: Config = CONFIG, seed: int | None = None) -> Market:
    """Same seed, same market. Lots and wants use separate streams so changing
    buyer settings doesn't reshuffle the sellers."""
    seed = cfg.seed if seed is None else seed
    lots, floors = _make_lots(random.Random(f"{seed}-sellers"), cfg)
    wants, maxes = _make_wants(random.Random(f"{seed}-buyers"), cfg)
    return Market(lots, wants, floors, maxes)
