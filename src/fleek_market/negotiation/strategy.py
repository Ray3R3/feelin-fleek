"""How an agent haggles: where it opens, how fast it concedes, when it accepts.

Each agent makes a `Plan` once, at the start of a negotiation, from public
listing data, its own private limit and its own private RNG. After that every
move is a lookup:

    price at round t = opening + (target - opening) * progress ** curve

where progress runs 0 -> 1 from the first round to the round the agent
privately plans to reach its target, at most its deadline. curve > 1 holds
firm and caves late; curve < 1 gives ground early. Each step is nudged by
private noise, so the other side can't solve the formula from a few offers.

Strategy proposes; guardrails.py still checks every message on the way out.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from ..core.config import CONFIG, Config, SegmentProfile
from ..core.models import Kind, Lot, Message, Offer, Side
from ..core.private import BuyerLimits, SellerLimits


@dataclass(frozen=True)
class Plan:
    """An agent's price path. Private: `target` sits just inside the limit."""
    side: Side
    opening: float
    target: float = field(repr=False)  # where concessions stop
    deadline: int  # last round this agent will make an offer in
    curve: float
    path: tuple[float, ...] = field(default=(), repr=False)  # share of the way to target, per round

    def price_at(self, rnd: int, tick: float = CONFIG.price_tick) -> float:
        """What this agent offers in round `rnd` (1-based)."""
        path = self.path or smooth_path(self.deadline, self.curve)
        raw = self.opening + (self.target - self.opening) * path[min(rnd, len(path)) - 1]
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

    def next_move(self, rnd: int, on_table: Offer | None, quantity: int) -> Message:
        """Walk if out of time, accept if their offer is good enough, else counter."""
        if self.should_walk(rnd):
            return Message(rnd, self.side, Kind.WALK)
        if on_table is not None and self.should_accept(on_table.price, rnd):
            return Message(rnd, self.side, Kind.ACCEPT, on_table)
        return Message(rnd, self.side, Kind.OFFER, Offer(self.price_at(rnd), quantity))


def smooth_path(deadline: int, curve: float, reach: float | None = None) -> tuple[float, ...]:
    """progress ** curve for each round: 0 on the opening, 1 from round `reach`
    (default: the deadline) onwards."""
    reach = deadline if reach is None else reach
    return tuple(1.0 if t >= reach else ((t - 1) / (reach - 1)) ** curve
                 for t in range(1, deadline + 1))


def draw_path(deadline: int, curve: float, rng: random.Random,
              cfg: Config = CONFIG) -> tuple[float, ...]:
    """The smooth path with private noise: a private round to reach the target
    by, and a nudge on each step. Never moves backwards, never passes the
    target, and is on it by the deadline."""
    reach = (rng.uniform(max(1.0, deadline - cfg.horizon_spread), deadline)
             if cfg.horizon_spread > 0 else deadline)
    path, prev = [], 0.0
    for t, base in enumerate(smooth_path(deadline, curve, reach), start=1):
        nudged = base * rng.uniform(1 - cfg.concession_jitter, 1 + cfg.concession_jitter)
        step = 1.0 if t == deadline or base >= 1.0 else min(1.0, max(prev, nudged))
        path.append(step)
        prev = step
    return tuple(path)


def draw_margin(rng: random.Random, cfg: Config = CONFIG) -> float:
    """How far short of its limit this agent stops. Drawn per agent, never sent."""
    return rng.uniform(*cfg.limit_margin)


def buyer_plan(lot: Lot, quantity: int, profile: SegmentProfile, limits: BuyerLimits,
               rng: random.Random, cfg: Config = CONFIG) -> Plan:
    """Ralph opens a segment-specific discount below the sticker price."""
    target = limits.max_price * (1 - draw_margin(rng, cfg))
    opening = lot.sticker_price(quantity) * (1 - profile.opening_discount)
    deadline = min(profile.patience, cfg.max_rounds)
    return Plan(
        side=Side.BUYER,
        opening=min(opening, target),  # if the sticker's already a bargain, start at the target
        target=target,
        deadline=deadline,
        curve=profile.concession_curve,
        path=draw_path(deadline, profile.concession_curve, rng, cfg),
    )


def seller_plan(lot: Lot, quantity: int, limits: SellerLimits,
                rng: random.Random, cfg: Config = CONFIG) -> Plan:
    """Tommy anchors at his own published price for this quantity."""
    target = limits.floor_price * (1 + draw_margin(rng, cfg))
    opening = lot.sticker_price(quantity) * (1 + cfg.seller_opening_markup)
    deadline = min(cfg.seller_patience, cfg.max_rounds)
    return Plan(
        side=Side.SELLER,
        # The floor never exceeds the deepest-tier sticker, but floor + margin
        # can. Then he opens at his target and just doesn't move. Stubborn, but legal.
        opening=max(opening, target),
        target=target,
        deadline=deadline,
        curve=cfg.seller_concession_curve,
        path=draw_path(deadline, cfg.seller_concession_curve, rng, cfg),
    )
