"""The offer loop. Two parties take turns; only public Messages cross between them.

The protocol is the referee, not a player. It knows whose turn it is, which
offer is on the table and when time runs out. It never holds a max or a floor
(this module doesn't import core/private.py), so it has nothing to leak.

Each round the buyer moves first, then the seller. A party can make an offer,
accept the offer on the table, or walk. A malformed move counts as a walk.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from ..core.models import Kind, Message, Offer, Side


class Party(Protocol):
    """Anything that can negotiate: Ralph, Tommy, or a scripted stand-in in tests."""
    side: Side

    def move(self, rnd: int, last: Message | None) -> Message:
        """Reply to the other side's last message (None on the opening move)."""
        ...


class Status(str, Enum):
    DEAL = "deal"
    WALK = "walk"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class Result:
    status: Status
    transcript: tuple[Message, ...]
    agreed: Offer | None = None  # the accepted offer, if there's a deal

    @property
    def rounds(self) -> int:
        return self.transcript[-1].round if self.transcript else 0


def valid(msg: Message, side: Side, rnd: int, last: Message | None) -> bool:
    """Public rules only. Whether a price is acceptable is each agent's own business."""
    if msg.sender is not side or msg.round != rnd:
        return False
    if msg.kind is Kind.OFFER:
        return msg.offer is not None
    if msg.kind is Kind.ACCEPT:
        on_table = last.offer if last is not None and last.kind is Kind.OFFER else None
        return on_table is not None and msg.offer in (None, on_table)
    return True  # WALK


def negotiate(buyer: Party, seller: Party, max_rounds: int) -> Result:
    transcript: list[Message] = []
    last: Message | None = None
    for rnd in range(1, max_rounds + 1):
        for party in (buyer, seller):
            msg = party.move(rnd, last)
            if not valid(msg, party.side, rnd, last):
                msg = Message(rnd, party.side, Kind.WALK)
            transcript.append(msg)
            if msg.kind is Kind.ACCEPT:
                return Result(Status.DEAL, tuple(transcript), agreed=last.offer)
            if msg.kind is Kind.WALK:
                return Result(Status.WALK, tuple(transcript))
            last = msg
    return Result(Status.TIMEOUT, tuple(transcript))


def best_offer(transcript: tuple[Message, ...], side: Side) -> Offer | None:
    """Best price `side` put on the table: lowest from a seller, highest from a buyer.

    This is what Ralph reports back when there's no deal ("best we could get:
    £5.50"). It's built only from offers both sides already saw, so it leaks nothing.
    """
    offers = [m.offer for m in transcript if m.sender is side and m.kind is Kind.OFFER]
    if not offers:
        return None
    pick = min if side is Side.SELLER else max
    return pick(offers, key=lambda o: o.price)
