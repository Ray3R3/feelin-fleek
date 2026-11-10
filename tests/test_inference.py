"""Attack our own buyer agent: can a seller work out Ralph's max from his offers?

The privacy tests check what is sent. This checks what can be inferred. The
attacker is a Tommy who has read strategy.py and config.py, holds firm, and
sees Ralph's first three counters. He knows the formula and every public
setting, but not Ralph's private draws.
"""
import statistics
from dataclasses import replace

from fleek_market.agents.ralph import Ralph
from fleek_market.core.config import CONFIG
from fleek_market.core.models import Kind, Message, Offer, Side
from fleek_market.data.generate import generate
from fleek_market.matching.match import shortlist

SEEDS = range(1, 21)


def estimate_max(offers, profile, cfg):
    """Fit the concession formula through the opening and the third offer, then
    undo the average margin. The curve and deadline are public segment settings."""
    p1, _, p3 = offers
    deadline = min(profile.patience, cfg.max_rounds)
    progress = (2 / (deadline - 1)) ** profile.concession_curve
    target = p1 + (p3 - p1) / progress
    return target / (1 - sum(cfg.limit_margin) / 2)


def first_three_offers(ralph, quantity, hold):
    offers, last = [], None
    for rnd in (1, 2, 3):
        msg = ralph.move(rnd, last)
        if msg.kind is not Kind.OFFER:
            return None  # he accepted or walked, so the attacker sees fewer offers
        offers.append(msg.offer.price)
        last = Message(rnd, Side.SELLER, Kind.OFFER, Offer(hold, quantity))
    return offers


def attack_errors(cfg0):
    """Relative error of the attacker's estimate for every shortlisted pair."""
    errors = []
    for seed in SEEDS:
        cfg = replace(cfg0, seed=seed)
        market = generate(cfg)
        wants = {w.buyer_id: w for w in market.wants}
        for buyer_id, matches in shortlist(market.wants, market.lots, cfg).items():
            want, true_max = wants[buyer_id], market.maxes[buyer_id].max_price
            for m in matches:
                hold = m.lot.sticker_price(m.quantity) * 2  # never close enough to accept
                ralph = Ralph(want, m.lot, m.quantity, market.maxes[buyer_id], cfg)
                offers = first_three_offers(ralph, m.quantity, hold)
                if offers is not None:
                    est = estimate_max(offers, cfg.segments[want.segment], cfg)
                    errors.append(abs(est / true_max - 1))
    return errors


def test_without_noise_the_attacker_nearly_recovers_the_max():
    # Shows the attacker is competent: only the private margin stands in its way.
    errors = attack_errors(replace(CONFIG, concession_jitter=0.0, horizon_spread=0.0))
    assert statistics.median(errors) < 0.012  # measured 1.02%


def test_with_noise_the_estimate_is_much_rougher():
    errors = attack_errors(CONFIG)
    assert statistics.median(errors) > 0.016  # measured 1.79%, vs 1.02% without noise
    assert statistics.quantiles(errors, n=10)[8] > 0.07  # p90: measured 9.20%, vs 1.92%
