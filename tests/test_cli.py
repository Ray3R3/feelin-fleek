from dataclasses import replace

from fleek_market.cli import main, run_market, summarise
from fleek_market.core.config import CONFIG
from fleek_market.data.generate import generate


def test_summary_adds_up():
    m = generate()
    outcomes = run_market(m)
    s = summarise(m, outcomes)
    deals = [o.deal for o in outcomes if o.deal]
    assert s.closed == len(deals) == s.negotiations["deal"]
    assert s.gmv == round(sum(d.offer.total for d in deals), 2)
    assert s.fleek_take == round(s.gmv * CONFIG.commission_rate, 2)
    assert sum(c for c, _ in s.closed_by_segment.values()) == s.closed
    assert s.near_misses == sum(o.near_miss for o in outcomes)
    # every deal sits inside both limits, so neither side can lose surplus
    assert s.buyer_surplus >= 0 and s.seller_surplus >= 0


def test_commission_rate_is_a_config_lever():
    m = generate()
    outcomes = run_market(m)
    s = summarise(m, outcomes, replace(CONFIG, commission_rate=0.10))
    assert s.fleek_take == round(s.gmv * 0.10, 2)


def test_demo_prints_each_section(capsys):
    main([])
    out = capsys.readouterr().out
    for section in ("Market", "Matching", "One negotiation", "Checkout", "No deal", "Summary"):
        assert section in out
    assert "Fleek take at 15%" in out


def test_seed_flag_changes_the_market(capsys):
    main(["--seed", "3"])
    assert "Market (seed 3)" in capsys.readouterr().out
