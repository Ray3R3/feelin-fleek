"""Ralph: the buyer's agent. Haggles for one lot at a time, then reports back.

Holds the buyer's private max. Strategy picks each move; the guardrail checks
it on the way out. Only Messages leave this object.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, replace

from ..core.config import CONFIG, Config
from ..core.models import Deal, Kind, Lot, Message, Offer, Side, Want
from ..core.private import BuyerLimits
from ..negotiation.guardrails import enforce
from ..negotiation.protocol import Result, best_offer
from ..negotiation.strategy import buyer_plan


class Ralph:
    side = Side.BUYER

    def __init__(self, want: Want, lot: Lot, quantity: int, limits: BuyerLimits,
                 cfg: Config = CONFIG):
        self.want, self.lot, self.quantity = want, lot, quantity
        self._limits = limits
        # seeded so demo runs are reproducible
        rng = random.Random(f"{cfg.seed}-ralph-{want.buyer_id}-{lot.lot_id}")
        self._plan = buyer_plan(lot, quantity, cfg.segments[want.segment], limits, rng, cfg)

    def move(self, rnd: int, last: Message | None) -> Message:
        on_table = last.offer if last is not None and last.kind is Kind.OFFER else None
        proposed = self._plan.next_move(rnd, on_table, self.quantity)
        return enforce(self._limits, proposed, on_table)


@dataclass(frozen=True)
class Outcome:
    """What Ralph tells the buyer after working through the shortlist."""
    want: Want
    deal: Deal | None
    attempts: tuple[tuple[Lot, Result], ...]
    near_miss: bool = False  # no deal, but the best counter was close to the max

    @property
    def best_counter(self) -> tuple[Lot, Offer] | None:
        """The cheapest price any Tommy actually offered. Public, so safe to report."""
        offers = [(lot, o) for lot, r in self.attempts
                  if (o := best_offer(r.transcript, Side.SELLER)) is not None]
        return min(offers, key=lambda lo: lo[1].price, default=None)


def debrief(want: Want, deal: Deal | None, attempts: list[tuple[Lot, Result]],
            limits: BuyerLimits, cfg: Config = CONFIG) -> Outcome:
    """Ralph's wrap-up for his own buyer. Uses the max, so it stays on Ralph's
    side: the label goes to the buyer (and their account manager), never to a seller."""
    outcome = Outcome(want, deal, tuple(attempts))
    best = outcome.best_counter
    if deal is None and best is not None:
        gap = best[1].price / limits.max_price - 1
        outcome = replace(outcome, near_miss=gap <= cfg.near_miss_pct)
    return outcome


def report(outcome: Outcome) -> str:
    """Ralph's one-line message back to the buyer."""
    w = outcome.want
    if outcome.deal is not None:
        d = outcome.deal
        return (f"Done: {d.offer.quantity} {w.category} from {d.seller_id} "
                f"at £{d.offer.price:.2f}/pc (£{d.offer.total:,.2f}).")
    if not outcome.attempts:
        return f"Nothing suitable listed for {w.quantity} {w.category} right now."
    best = outcome.best_counter
    if best is None:
        return "No deal: no seller made an offer."
    lot, offer = best
    quote = f"Best we could get: £{offer.price:.2f}/pc for {offer.quantity} from {lot.seller_id}"
    if outcome.near_miss:
        return f"Near miss. {quote}, close to your max. Flagged for an account-manager intro."
    return f"No fit. {quote}."
