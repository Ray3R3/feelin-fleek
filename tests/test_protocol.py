"""The offer loop, driven by scripted parties so these tests don't depend on strategy."""
import ast
from pathlib import Path

from fleek_market.core.models import Kind, Message, Offer, Side
from fleek_market.negotiation import protocol
from fleek_market.negotiation.protocol import Status, best_offer, negotiate


class Scripted:
    """Plays a fixed list of moves: a price to offer, "accept" or "walk"."""

    def __init__(self, side, moves, qty=100):
        self.side, self.moves, self.qty = side, list(moves), qty

    def move(self, rnd, last):
        step = self.moves.pop(0) if self.moves else "walk"
        if step == "accept":
            return Message(rnd, self.side, Kind.ACCEPT, last.offer if last else None)
        if step == "walk":
            return Message(rnd, self.side, Kind.WALK)
        return Message(rnd, self.side, Kind.OFFER, Offer(step, self.qty))


def test_deal_closes_at_the_accepted_offer():
    r = negotiate(Scripted(Side.BUYER, [4.0, 4.5]), Scripted(Side.SELLER, [6.0, "accept"]), 6)
    assert r.status is Status.DEAL
    assert r.agreed == Offer(4.5, 100)
    assert [m.sender for m in r.transcript] == [Side.BUYER, Side.SELLER, Side.BUYER, Side.SELLER]
    assert r.rounds == 2


def test_walk_ends_it_with_no_deal():
    r = negotiate(Scripted(Side.BUYER, [4.0, "walk"]), Scripted(Side.SELLER, [6.0]), 6)
    assert r.status is Status.WALK and r.agreed is None


def test_timeout_after_max_rounds():
    r = negotiate(Scripted(Side.BUYER, [4.0] * 9), Scripted(Side.SELLER, [6.0] * 9), 3)
    assert r.status is Status.TIMEOUT and r.rounds == 3 and len(r.transcript) == 6


def test_accepting_with_nothing_on_the_table_counts_as_a_walk():
    r = negotiate(Scripted(Side.BUYER, ["accept"]), Scripted(Side.SELLER, [6.0]), 6)
    assert r.status is Status.WALK and r.transcript[0].kind is Kind.WALK


class Cheat:
    """Tries to accept a better price than the one actually offered."""
    side = Side.SELLER

    def move(self, rnd, last):
        return Message(rnd, self.side, Kind.ACCEPT, Offer(9.99, 100))


def test_cannot_accept_an_offer_that_wasnt_made():
    r = negotiate(Scripted(Side.BUYER, [4.0]), Cheat(), 6)
    assert r.status is Status.WALK and r.agreed is None


class Impostor:
    side = Side.SELLER

    def move(self, rnd, last):
        return Message(rnd, Side.BUYER, Kind.OFFER, Offer(1.0, 100))


def test_cannot_speak_for_the_other_side():
    r = negotiate(Scripted(Side.BUYER, [4.0]), Impostor(), 6)
    assert r.status is Status.WALK and r.transcript[-1].sender is Side.SELLER


def test_best_offer_is_the_sellers_lowest_and_buyers_highest():
    r = negotiate(Scripted(Side.BUYER, [4.0, 4.4, 4.6]), Scripted(Side.SELLER, [6.0, 5.5, 5.2]), 3)
    assert best_offer(r.transcript, Side.SELLER) == Offer(5.2, 100)
    assert best_offer(r.transcript, Side.BUYER) == Offer(4.6, 100)
    assert best_offer((), Side.SELLER) is None


def test_protocol_never_imports_private_limits():
    tree = ast.parse(Path(protocol.__file__).read_text())
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any("private" in (name or "") for name in imported)
