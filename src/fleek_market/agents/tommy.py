"""Tommy: the seller's agent for one negotiation over one lot.

Holds the lot's private floor. Strategy picks each move; the guardrail checks
it on the way out. Only Messages leave this object.
"""
from __future__ import annotations

import random

from ..core.config import CONFIG, Config
from ..core.models import Kind, Lot, Message, Side
from ..core.private import SellerLimits
from ..negotiation.guardrails import enforce
from ..negotiation.strategy import seller_plan


class Tommy:
    side = Side.SELLER

    def __init__(self, lot: Lot, quantity: int, limits: SellerLimits,
                 buyer_id: str, cfg: Config = CONFIG):
        self.lot, self.quantity = lot, quantity
        self._limits = limits
        rng = random.Random(f"{cfg.seed}-tommy-{lot.lot_id}-{buyer_id}")  # private to this agent
        self._plan = seller_plan(lot, quantity, limits, rng, cfg)

    def move(self, rnd: int, last: Message | None) -> Message:
        on_table = last.offer if last is not None and last.kind is Kind.OFFER else None
        proposed = self._plan.next_move(rnd, on_table, self.quantity)
        return enforce(self._limits, proposed, on_table)
