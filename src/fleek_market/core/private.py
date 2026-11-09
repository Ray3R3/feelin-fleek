"""Private limits. Held only by the agent that owns them.

These types are deliberately awkward to leak: the value is hidden from
repr/str, so a stray log line or f-string prints <private>, not the number.
Nothing in negotiation/protocol.py imports this module.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BuyerLimits:
    """Ralph's secret: the most the buyer will pay per piece."""
    max_price: float = field(repr=False)

    def __str__(self) -> str:
        return "BuyerLimits(<private>)"

    __repr__ = __str__


@dataclass(frozen=True)
class SellerLimits:
    """Tommy's secret: the least the seller will accept per piece."""
    floor_price: float = field(repr=False)

    def __str__(self) -> str:
        return "SellerLimits(<private>)"

    __repr__ = __str__
