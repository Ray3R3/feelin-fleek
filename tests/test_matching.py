import inspect

from fleek_market.core.config import CONFIG
from fleek_market.core.models import Grade, Lot, Segment, Tier, Want
from fleek_market.data.generate import generate
from fleek_market.matching import match
from fleek_market.matching.match import shortlist

TIERS = (Tier(100, 0.05), Tier(250, 0.10), Tier(500, 0.15))


def lot(lot_id, seller, category="denim", grade=Grade.B, pieces=250, price=5.0):
    return Lot(lot_id, seller, category, grade, pieces, price, TIERS)


def want(grades=(Grade.B,), quantity=200, min_quantity=100):
    return Want("B1", Segment.LEARNER, "denim", frozenset(grades), quantity, min_quantity)


def test_filters_category_grade_and_minimum_size():
    lots = [
        lot("ok", "S1"),
        lot("wrong-cat", "S2", category="tees"),
        lot("wrong-grade", "S3", grade=Grade.A),
        lot("too-small", "S4", pieces=50),
    ]
    [m] = shortlist([want()], lots)["B1"]
    assert m.lot.lot_id == "ok"


def test_cheaper_lot_ranks_first():
    lots = [lot("dear", "S1", price=6.0), lot("cheap", "S2", price=4.0)]
    assert [m.lot.lot_id for m in shortlist([want()], lots)["B1"]] == ["cheap", "dear"]


def test_preferred_grade_beats_fallback_grade_at_same_price():
    lots = [lot("c", "S1", grade=Grade.C, price=2.5), lot("b", "S2", grade=Grade.B, price=5.0)]
    ranked = shortlist([want(grades=(Grade.B, Grade.C))], lots)["B1"]
    assert ranked[0].lot.lot_id == "b"


def test_at_most_k_distinct_sellers():
    lots = [lot(f"S{s}-L{n}", f"S{s}") for s in range(6) for n in range(3)]
    picks = shortlist([want()], lots)["B1"]
    assert len(picks) == CONFIG.shortlist_k
    assert len({m.lot.seller_id for m in picks}) == CONFIG.shortlist_k


def test_quantity_is_capped_by_lot_size():
    [m] = shortlist([want(quantity=400)], [lot("x", "S1", pieces=250)])["B1"]
    assert m.quantity == 250


def test_index_matches_brute_force_on_generated_market():
    m = generate()
    index = match.index_lots(m.lots)
    for w in m.wants:
        brute = {l.lot_id for l in m.lots
                 if l.category == w.category and l.grade in w.grades and l.pieces >= w.min_quantity}
        assert {l.lot_id for l in match.candidates(w, index)} == brute


def test_matching_never_receives_private_limits():
    params = inspect.signature(shortlist).parameters
    assert list(params) == ["wants", "lots", "cfg"]
