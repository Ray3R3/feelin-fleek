"""Hard limit checks: the last thing every outgoing message passes through.

Strategy (or the optional LLM wording layer) proposes a move; the guardrail
decides whether it may leave the agent. A move that would cross the owner's
limit is replaced by a bare walk-away. Fail closed: a bug can lose a deal,
never break a limit. The walk-away carries no reason, because "that's above
my max" would itself hint at the max.

This runs inside the agent that owns the limit. The protocol never sees it.
"""
from __future__ import annotations

from ..core.models import Kind, Message, Offer, Side
from ..core.private import BuyerLimits, SellerLimits

Limits = BuyerLimits | SellerLimits


def owner(limits: Limits) -> Side:
    return Side.BUYER if isinstance(limits, BuyerLimits) else Side.SELLER


def price_ok(limits: Limits, price: float) -> bool:
    """Buyer never pays above max; seller never sells below floor."""
    if isinstance(limits, BuyerLimits):
        return price <= limits.max_price
    return price >= limits.floor_price


def allowed(limits: Limits, msg: Message, on_table: Offer | None) -> bool:
    """May this message leave the agent? `on_table` is the other side's latest offer."""
    if msg.sender is not owner(limits):
        return False
    if msg.kind is Kind.WALK:
        return True
    if msg.kind is Kind.OFFER:
        o = msg.offer
        return o is not None and o.price > 0 and o.quantity > 0 and price_ok(limits, o.price)
    # ACCEPT: only the offer actually on the table, and only if it's within our limit
    return (on_table is not None
            and msg.offer in (None, on_table)
            and price_ok(limits, on_table.price))


def enforce(limits: Limits, msg: Message, on_table: Offer | None) -> Message:
    """Pass the message through, or replace it with a bare walk-away."""
    if allowed(limits, msg, on_table):
        return msg
    return Message(round=msg.round, sender=owner(limits), kind=Kind.WALK)
