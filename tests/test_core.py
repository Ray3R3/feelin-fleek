from fleek_market.core.config import CONFIG
from fleek_market.core.models import Grade, Lot, Tier
from fleek_market.core.private import BuyerLimits, SellerLimits


def test_limits_never_print_their_value():
    b, s = BuyerLimits(7.31), SellerLimits(4.27)
    for text in (str(b), repr(b), f"{b}", str(s), repr(s), f"{[b, s]}"):
        assert "7.31" not in text and "4.27" not in text


def test_sticker_price_uses_best_tier():
    lot = Lot("L1", "S1", "denim", Grade.B, 500, 10.0,
              (Tier(100, 0.05), Tier(250, 0.10), Tier(500, 0.15)))
    assert lot.sticker_price(50) == 10.0
    assert lot.sticker_price(250) == 9.0
    assert lot.sticker_price(500) == 8.5


def test_segment_mix_sums_to_one():
    assert abs(sum(CONFIG.segment_mix.values()) - 1) < 1e-9
