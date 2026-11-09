"""No message that leaves an agent can cross its owner's limit.

Hand-written cases pin the rules; the property test throws thousands of random
proposed moves at the guardrail, using limits from many generated markets.
Once negotiation exists, this file also checks every closed deal.
"""
import random

from fleek_market.core.models import Kind, Message, Offer, Side
from fleek_market.core.private import BuyerLimits, SellerLimits
from fleek_market.data.generate import generate
from fleek_market.negotiation.guardrails import enforce, price_ok

BUYER, SELLER = BuyerLimits(5.00), SellerLimits(4.00)


def offer(side, price, qty=100):
    return Message(1, side, Kind.OFFER, Offer(price, qty))


def accept(side, on_table=None):
    return Message(1, side, Kind.ACCEPT, on_table)


def blocked(msg):
    return msg.kind is Kind.WALK and msg.offer is None and msg.text == ""


def test_offers_up_to_the_limit_pass():
    assert enforce(BUYER, offer(Side.BUYER, 5.00), None).kind is Kind.OFFER
    assert enforce(SELLER, offer(Side.SELLER, 4.00), None).kind is Kind.OFFER


def test_offers_past_the_limit_become_a_bare_walk():
    assert blocked(enforce(BUYER, offer(Side.BUYER, 5.01), None))
    assert blocked(enforce(SELLER, offer(Side.SELLER, 3.99), None))


def test_accept_checks_the_price_on_the_table():
    assert enforce(BUYER, accept(Side.BUYER), Offer(4.80, 100)).kind is Kind.ACCEPT
    assert blocked(enforce(BUYER, accept(Side.BUYER), Offer(5.20, 100)))
    assert enforce(SELLER, accept(Side.SELLER), Offer(4.10, 100)).kind is Kind.ACCEPT
    assert blocked(enforce(SELLER, accept(Side.SELLER), Offer(3.90, 100)))


def test_cannot_accept_nothing_or_a_different_offer():
    assert blocked(enforce(BUYER, accept(Side.BUYER), None))
    on_table = Offer(4.00, 100)
    assert blocked(enforce(BUYER, accept(Side.BUYER, Offer(3.00, 100)), on_table))


def test_cannot_speak_for_the_other_side():
    assert blocked(enforce(BUYER, offer(Side.SELLER, 4.50), None))


def test_nonsense_offers_are_blocked():
    assert blocked(enforce(BUYER, offer(Side.BUYER, 0.0), None))
    assert blocked(enforce(BUYER, offer(Side.BUYER, 4.0, qty=0), None))


def test_walk_always_passes():
    walk = Message(3, Side.SELLER, Kind.WALK)
    assert enforce(SELLER, walk, Offer(1.0, 10)) == walk


def random_move(rng, side, around):
    """Any move a buggy strategy or a misbehaving LLM might propose."""
    price = round(around * rng.uniform(0.3, 1.7), 2)
    on_table = Offer(round(around * rng.uniform(0.3, 1.7), 2), 100) if rng.random() < 0.8 else None
    kind = rng.choice(list(Kind))
    sender = side if rng.random() < 0.95 else rng.choice(list(Side))
    proposed = Offer(price, rng.choice([0, 50, 100])) if kind is not Kind.WALK else None
    if kind is Kind.ACCEPT and rng.random() < 0.7:
        proposed = on_table
    return Message(1, sender, kind, proposed), on_table


def test_property_no_outgoing_message_crosses_a_limit():
    rng = random.Random(0)
    checked = 0
    for seed in range(30):
        m = generate(seed=seed)
        limits = [(Side.BUYER, b, b.max_price) for b in m.maxes.values()]
        limits += [(Side.SELLER, s, s.floor_price) for s in m.floors.values()]
        for side, lim, value in limits:
            for _ in range(10):
                msg, on_table = random_move(rng, side, value)
                out = enforce(lim, msg, on_table)
                assert out.sender is side
                if out.kind is Kind.OFFER:
                    assert price_ok(lim, out.offer.price)
                elif out.kind is Kind.ACCEPT:
                    assert on_table is not None and price_ok(lim, on_table.price)
                checked += 1
    assert checked > 50_000
