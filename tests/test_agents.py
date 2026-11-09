from fleek_market.core.config import CONFIG
from fleek_market.core.models import Grade, Kind, Lot, Segment, Side, Tier, Want
from fleek_market.core.private import BuyerLimits, SellerLimits
from fleek_market.agents.ralph import Ralph, report
from fleek_market.agents.tommy import Tommy
from fleek_market.cli import run_market
from fleek_market.data.generate import generate
from fleek_market.negotiation.protocol import Status, negotiate

LOT = Lot("S1-L1", "S1", "denim", Grade.B, 250, 5.00, (Tier(100, 0.05), Tier(250, 0.10)))
WANT = Want("B1", Segment.PRO, "denim", frozenset({Grade.B}), 250, 250)


def haggle(bmax, floor):
    ralph = Ralph(WANT, LOT, 250, BuyerLimits(bmax))
    tommy = Tommy(LOT, 250, SellerLimits(floor), WANT.buyer_id)
    return negotiate(ralph, tommy, CONFIG.max_rounds)


def test_overlapping_limits_close_between_them():
    r = haggle(bmax=4.50, floor=3.60)
    assert r.status is Status.DEAL and 3.60 <= r.agreed.price <= 4.50


def test_no_overlap_means_no_deal():
    r = haggle(bmax=3.50, floor=3.80)
    assert r.status is not Status.DEAL


def test_ralph_opens_and_tommy_anchors_at_sticker():
    r = haggle(bmax=4.50, floor=3.60)
    first, second = r.transcript[:2]
    assert first.sender is Side.BUYER and first.kind is Kind.OFFER
    assert second.offer.price == LOT.sticker_price(250)


def test_no_deal_report_quotes_tommys_best_counter():
    m = generate()
    misses = [o for o in run_market(m) if o.deal is None and o.best_counter]
    o = misses[0]
    lot, offer = o.best_counter
    assert f"£{offer.price:.2f}" in report(o) and lot.seller_id in report(o)
    seller_prices = [msg.offer.price for _, r in o.attempts for msg in r.transcript
                     if msg.sender is Side.SELLER and msg.kind is Kind.OFFER]
    assert offer.price == min(seller_prices)


def test_market_run_is_deterministic():
    m = generate()
    assert [o.deal for o in run_market(m)] == [o.deal for o in run_market(generate())]


def test_stock_is_never_oversold():
    m = generate()
    sold = {}
    for o in run_market(m):
        if o.deal:
            sold[o.deal.lot_id] = sold.get(o.deal.lot_id, 0) + o.deal.offer.quantity
    pieces = {lot.lot_id: lot.pieces for lot in m.lots}
    assert all(sold[k] <= pieces[k] for k in sold)
