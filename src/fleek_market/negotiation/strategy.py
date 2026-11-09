"""How an agent haggles: where it opens, how fast it concedes, when it accepts.

Each agent makes a `Plan` once, at the start of a negotiation, from public
listing data, its own private limit and its own private RNG. After that every
move is a lookup:

    price at round t = opening + (target - opening) * progress ** curve

where progress runs 0 -> 1 from the first round to the agent's deadline.
curve > 1 holds firm and caves late; curve < 1 gives ground early.

Strategy proposes; guardrails.py still checks every message on the way out.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from ..core.config import CONFIG, Config, SegmentProfile
from ..core.models import Lot, Side
from ..core.private import BuyerLimits, SellerLimits


@dataclass(frozen=True)
class Plan:
    """An agent's price path. Private: `target` sits just inside the limit."""
    side: Side
    opening: float
    target: float = field(repr=False)  # where concessions stop
    deadline: int  # last round this agent will make an offer in
    curve: float

    def price_at(self, rnd: int, tick: float = CONFIG.price_tick) -> float:
        """What this agent offers in round `rnd` (1-based)."""
        progress = 1.0 if self.deadline <= 1 else min(1.0, (rnd - 1) / (self.deadline - 1))
        raw = self.opening + (self.target - self.opening) * progress ** self.curve
        # Rounding the wrong way lets a penny slip past the limit.
        # Buyers round down, sellers round up, always.
        steps = raw / tick
        steps = math.floor(steps + 1e-9) if self.side is Side.BUYER else math.ceil(steps - 1e-9)
        return round(steps * tick, 2)

    def should_accept(self, their_price: float, rnd: int) -> bool:
        """Take their offer if it's at least as good as what we'd counter with anyway."""
        mine = self.price_at(rnd)
        return their_price <= mine if self.side is Side.BUYER else their_price >= mine

    def should_walk(self, rnd: int) -> bool:
        return rnd > self.deadline


def draw_margin(rng: random.Random, cfg: Config = CONFIG) -> float:
    """How far short of its limit this agent stops. Drawn per agent, never sent."""
    return rng.uniform(*cfg.limit_margin)


def buyer_plan(lot: Lot, quantity: int, profile: SegmentProfile, limits: BuyerLimits,
               rng: random.Random, cfg: Config = CONFIG) -> Plan:
    """Ralph opens a segment-specific discount below the sticker price."""
    target = limits.max_price * (1 - draw_margin(rng, cfg))
    opening = lot.sticker_price(quantity) * (1 - profile.opening_discount)
    return Plan(
        side=Side.BUYER,
        opening=min(opening, target),  # if the sticker's already a bargain, start at the target
        target=target,
        deadline=min(profile.patience, cfg.max_rounds),
        curve=profile.concession_curve,
    )


def seller_plan(lot: Lot, quantity: int, limits: SellerLimits,
                rng: random.Random, cfg: Config = CONFIG) -> Plan:
    """Tommy anchors at his own published price for this quantity."""
    target = limits.floor_price * (1 + draw_margin(rng, cfg))
    opening = lot.sticker_price(quantity) * (1 + cfg.seller_opening_markup)
    return Plan(
        side=Side.SELLER,
        # The floor never exceeds the deepest-tier sticker, but floor + margin
        # can. Then he opens at his target and just doesn't move. Stubborn, but legal.
        opening=max(opening, target),
        target=target,
        deadline=min(cfg.seller_patience, cfg.max_rounds),
        curve=cfg.seller_concession_curve,
    )
