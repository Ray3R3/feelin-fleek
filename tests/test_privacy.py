"""No agent ever says its own limit, across many generated markets.

The check is per agent: what Ralph sends never contains Ralph's max, and what
Tommy sends never contains Tommy's floor. "This number never appears anywhere"
would be the wrong test: a seller can legitimately offer a price that happens to
equal some other buyer's max.

Covered: offer prices, the Message text field (the voice layer fills it later),
and Ralph's report() back to the buyer. The repr/str check on the limit types
themselves lives in test_core.py.
"""
import re

import pytest

import fleek_market.cli as cli
from fleek_market.agents.ralph import Ralph, report
from fleek_market.agents.tommy import Tommy
from fleek_market.core.models import Kind, Side
from fleek_market.core.private import BuyerLimits
from fleek_market.data.generate import generate

SEEDS = range(20)


def recording(base, log):
    """Same agent, but keeps a copy of everything it sends."""
    class Recorded(base):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.sent = []
            log.append(self)

        def move(self, rnd, last):
            msg = super().move(rnd, last)
            self.sent.append(msg)
            return msg
    return Recorded


@pytest.fixture(scope="module")
def runs():
    """Run every market with recording agents. Returns (agents, outcomes, market) per seed."""
    real = cli.Ralph, cli.Tommy
    out = []
    try:
        for seed in SEEDS:
            agents = []
            cli.Ralph, cli.Tommy = recording(Ralph, agents), recording(Tommy, agents)
            market = generate(seed=seed)
            out.append((agents, cli.run_market(market), market))
    finally:
        cli.Ralph, cli.Tommy = real
    return out


def limit_of(agent) -> float:
    lim = agent._limits
    return lim.max_price if isinstance(lim, BuyerLimits) else lim.floor_price


def numbers_in(text: str) -> set[float]:
    """Every number in free text, so 5, 5.0 and £5.00 all read as 5.0.

    Used for the Message text field, where the voice layer may write a price
    without a £. Digits inside IDs like S06 or B012 don't count.
    """
    found = re.findall(r"(?<![A-Za-z\d.,])\d[\d,]*(?:\.\d+)?", text)
    return {float(n.replace(",", "")) for n in found}


def test_enough_traffic_to_mean_something(runs):
    sent = sum(len(a.sent) for agents, _, _ in runs for a in agents)
    assert sent > 20_000


def test_no_agent_offers_its_own_limit(runs):
    for agents, _, _ in runs:
        for a in agents:
            for msg in a.sent:
                if msg.offer is not None:
                    assert msg.offer.price != limit_of(a)


def test_no_agent_concedes_past_its_own_target(runs):
    # Reaching the target is the design: it's where concessions stop, and only the
    # private margin links it back to the limit. Going past it would be the bug.
    for agents, _, _ in runs:
        for a in agents:
            target = a._plan.target
            for msg in a.sent:
                if msg.kind is Kind.OFFER:
                    p = msg.offer.price
                    assert p <= target if a.side is Side.BUYER else p >= target


def test_message_text_never_contains_own_limit_or_target(runs):
    for agents, _, _ in runs:
        for a in agents:
            secret = {limit_of(a), round(a._plan.target, 2)}
            for msg in a.sent:
                assert not secret & numbers_in(msg.text)


def test_reports_quote_only_offered_prices(runs):
    """Every £ amount in a report is a price or total that was actually offered.

    So the buyer's max or Ralph's target can only appear by coincidence with a
    public offer, never because Ralph looked it up.
    """
    checked = 0
    for agents, outcomes, market in runs:
        targets = {}
        for a in agents:
            if a.side is Side.BUYER:
                targets.setdefault(a.want.buyer_id, set()).add(round(a._plan.target, 2))
        for o in outcomes:
            text = report(o)
            offers = [m.offer for _, r in o.attempts for m in r.transcript if m.offer]
            offered = {n for x in offers for n in (x.price, x.total)}
            amounts = {float(a.replace(",", "")) for a in re.findall(r"£([\d,]+\.\d{2})", text)}
            assert amounts <= offered, text
            secrets = {market.maxes[o.want.buyer_id].max_price} | targets.get(o.want.buyer_id, set())
            assert not (secrets - offered) & amounts, text
            checked += 1
    assert checked == sum(len(m.wants) for _, _, m in runs)
