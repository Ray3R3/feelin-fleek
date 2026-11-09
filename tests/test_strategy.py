import random
from dataclasses import replace

from fleek_market.core.config import CONFIG
from fleek_market.core.models import Grade, Lot, Segment, Side, Tier
from fleek_market.core.private import BuyerLimits, SellerLimits
from fleek_market.data.generate import generate
from fleek_market.matching.match import shortlist
from fleek_market.negotiation import strategy


def rng(seed=0):
    return random.Random(seed)


def buyer_plan(*args, **kw):
    return strategy.buyer_plan(*args, rng=kw.pop("rng", rng()), **kw)


def seller_plan(*args, **kw):
    return strategy.seller_plan(*args, rng=kw.pop("rng", rng()), **kw)


LOT = Lot("S1-L1", "S1", "denim", Grade.B, 500, 10.00,
          (Tier(100, 0.05), Tier(250, 0.10), Tier(500, 0.15)))
HOBBY, PRO = CONFIG.segments[Segment.HOBBYIST], CONFIG.segments[Segment.PRO]


def path(plan):
    return [plan.price_at(r) for r in range(1, plan.deadline + 1)]


def test_openings_follow_the_listing():
    # 100 pieces -> 5% tier -> sticker £9.50
    assert buyer_plan(LOT, 100, HOBBY, BuyerLimits(9.00)).price_at(1) == round(9.50 * 0.85, 2)
    assert seller_plan(LOT, 100, SellerLimits(7.00)).price_at(1) == 9.50


def test_seller_never_opens_below_floor_even_with_deep_tier():
    # 500 pieces -> 15% off -> sticker £8.50, but the floor is £8.80
    plan = seller_plan(LOT, 500, SellerLimits(8.80))
    assert all(p >= 8.80 for p in path(plan))


def test_concessions_move_one_way_and_stop_short_of_the_limit():
    buyer = buyer_plan(LOT, 250, PRO, BuyerLimits(8.00))
    seller = seller_plan(LOT, 250, SellerLimits(7.00))
    assert path(buyer) == sorted(path(buyer)) and max(path(buyer)) < 8.00
    assert path(seller) == sorted(path(seller), reverse=True) and min(path(seller)) > 7.00


def test_patient_pros_hold_firmer_early_than_hobbyists():
    pro = replace(PRO, opening_discount=0.2, patience=4)
    hob = replace(HOBBY, opening_discount=0.2, patience=4)
    # same start, same deadline, same limit: only the curve differs
    assert buyer_plan(LOT, 100, pro, BuyerLimits(9)).price_at(2) < \
        buyer_plan(LOT, 100, hob, BuyerLimits(9)).price_at(2)


def test_accept_when_their_offer_beats_our_next_counter():
    buyer = buyer_plan(LOT, 100, HOBBY, BuyerLimits(9.00))
    mine = buyer.price_at(2)
    assert buyer.should_accept(mine - 0.01, 2)
    assert not buyer.should_accept(mine + 0.01, 2)


def test_walk_after_deadline():
    buyer = buyer_plan(LOT, 100, HOBBY, BuyerLimits(9.00))
    assert not buyer.should_walk(HOBBY.patience)
    assert buyer.should_walk(HOBBY.patience + 1)


def test_no_planned_price_ever_equals_or_crosses_a_limit():
    for seed in range(20):
        m = generate(seed=seed)
        wants = {w.buyer_id: w for w in m.wants}
        for buyer_id, matches in shortlist(m.wants, m.lots).items():
            profile = CONFIG.segments[wants[buyer_id].segment]
            for x in matches:
                bmax = m.maxes[buyer_id].max_price
                floor = m.floors[x.lot.lot_id].floor_price
                assert all(p < bmax for p in path(buyer_plan(x.lot, x.quantity, profile, m.maxes[buyer_id])))
                assert all(p > floor for p in path(seller_plan(x.lot, x.quantity, m.floors[x.lot.lot_id])))


def test_plan_repr_hides_the_target():
    plan = buyer_plan(LOT, 100, HOBBY, BuyerLimits(9.00))
    assert "target" not in repr(plan) and str(plan.target) not in repr(plan)
    assert plan.side is Side.BUYER


def test_margin_is_private_per_agent_and_seeded():
    a = buyer_plan(LOT, 100, HOBBY, BuyerLimits(9.00), rng=rng(1))
    b = buyer_plan(LOT, 100, HOBBY, BuyerLimits(9.00), rng=rng(2))
    assert a.target != b.target  # same limit, different margins
    assert a == buyer_plan(LOT, 100, HOBBY, BuyerLimits(9.00), rng=rng(1))
    lo, hi = CONFIG.limit_margin
    assert 9.00 * (1 - hi) <= a.target <= 9.00 * (1 - lo)


def test_final_offer_doesnt_reveal_the_limit_by_a_fixed_ratio():
    # with a fixed margin, final_offer / (1 - margin) would be the same for everyone
    ratios = {round(buyer_plan(LOT, 100, HOBBY, BuyerLimits(9.00), rng=rng(s)).target / 9.00, 3)
              for s in range(50)}
    assert len(ratios) > 10
