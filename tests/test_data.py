from dataclasses import replace

from fleek_market.core.config import CONFIG
from fleek_market.data.generate import generate


def test_same_seed_same_market():
    a, b = generate(seed=1), generate(seed=1)
    assert a.lots == b.lots and a.wants == b.wants
    assert generate(seed=2).lots != a.lots


def test_sizes_follow_config():
    m = generate()
    assert len(m.seller_ids) == CONFIG.n_sellers
    assert len(m.wants) == CONFIG.n_buyers
    assert set(m.floors) == {lot.lot_id for lot in m.lots}
    assert set(m.maxes) == {w.buyer_id for w in m.wants}


def test_floor_sits_below_list_price():
    m = generate()
    for lot in m.lots:
        assert m.floors[lot.lot_id].floor_price <= lot.list_price


def test_buyer_settings_dont_reshuffle_sellers():
    m = generate()
    assert generate(replace(CONFIG, n_buyers=10)).lots == m.lots


def test_floor_never_above_deepest_tier_price():
    for seed in range(10):
        m = generate(seed=seed)
        for lot in m.lots:
            deepest = lot.sticker_price(max(t.min_pieces for t in lot.tiers))
            assert m.floors[lot.lot_id].floor_price <= deepest
