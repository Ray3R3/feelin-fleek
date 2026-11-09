"""Public types. Everything here may be seen by the other side or the market.

Nothing in this module holds a buyer's max or a seller's floor; those live
in core/private.py and never appear in a Message.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Grade(str, Enum):
    A = "A"  # near-new, premium brands
    B = "B"  # good condition, minor wear
    C = "C"  # visible wear, repair/upcycle stock


GRADE_ORDER = (Grade.A, Grade.B, Grade.C)  # best first


class Segment(str, Enum):
    """Fleek's buyer bands by monthly spend. Learners (<£200/mo) are out of scope."""
    HOBBYIST = "hobbyist"  # £200-2K/mo
    PRO = "pro"  # £2K+/mo


@dataclass(frozen=True)
class Tier:
    """Published bulk discount: buy at least `min_pieces`, get `discount` off list."""
    min_pieces: int
    discount: float  # 0.10 == 10% off


@dataclass(frozen=True)
class Lot:
    """A bale a seller has listed. List price and tiers are public, like a price sheet."""
    lot_id: str
    seller_id: str
    category: str
    grade: Grade
    pieces: int
    list_price: float  # per piece
    tiers: tuple[Tier, ...] = ()

    def tier_discount(self, quantity: int) -> float:
        """Best published discount that applies at this quantity."""
        eligible = [t.discount for t in self.tiers if quantity >= t.min_pieces]
        return max(eligible, default=0.0)

    def sticker_price(self, quantity: int) -> float:
        """Per-piece price anyone would see on the listing for this quantity."""
        return round(self.list_price * (1 - self.tier_discount(quantity)), 2)


@dataclass(frozen=True)
class Want:
    """What a buyer told Ralph they want. Public to matching, minus the max."""
    buyer_id: str
    segment: Segment
    category: str
    grades: frozenset[Grade]
    quantity: int  # pieces wanted
    min_quantity: int  # smallest lot worth buying


@dataclass(frozen=True)
class Offer:
    price: float  # per piece
    quantity: int

    @property
    def total(self) -> float:
        return round(self.price * self.quantity, 2)


class Kind(str, Enum):
    OFFER = "offer"
    ACCEPT = "accept"
    WALK = "walk"


class Side(str, Enum):
    BUYER = "buyer"
    SELLER = "seller"


@dataclass(frozen=True)
class Message:
    """The only thing that crosses the wire between Ralph and Tommy."""
    round: int
    sender: Side
    kind: Kind
    offer: Offer | None = None
    text: str = ""


@dataclass(frozen=True)
class Deal:
    buyer_id: str
    seller_id: str
    lot_id: str
    offer: Offer
    rounds: int
    transcript: tuple[Message, ...] = field(default=(), repr=False)
