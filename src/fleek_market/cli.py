"""Demo runner: build the synthetic market, shortlist, negotiate, summarise.

This is the simulator, so it is the one place that holds every secret. It hands
each max to one Ralph and each floor to one Tommy, and nothing else sees them.
"""
from __future__ import annotations

from collections import Counter

from .agents.ralph import Outcome, Ralph, report
from .agents.tommy import Tommy
from .core.config import CONFIG, Config
from .core.models import Deal
from .data.generate import Market, generate
from .matching.match import shortlist
from .negotiation.protocol import Status, negotiate


def run_market(market: Market, cfg: Config = CONFIG) -> list[Outcome]:
    """Each buyer's Ralph works down its shortlist until a deal closes.

    Buyers go in turn and stock is shared, so an early buyer can take pieces a
    later one wanted. A real marketplace would run these concurrently; first
    come, first served keeps the demo deterministic.
    """
    lists = shortlist(market.wants, market.lots, cfg)
    stock = {lot.lot_id: lot.pieces for lot in market.lots}
    outcomes = []
    for want in market.wants:
        attempts, deal = [], None
        for m in lists[want.buyer_id]:
            qty = min(want.quantity, stock[m.lot.lot_id])
            if qty < want.min_quantity:
                continue  # someone earlier bought most of it
            ralph = Ralph(want, m.lot, qty, market.maxes[want.buyer_id], cfg)
            tommy = Tommy(m.lot, qty, market.floors[m.lot.lot_id], want.buyer_id, cfg)
            result = negotiate(ralph, tommy, cfg.max_rounds)
            attempts.append((m.lot, result))
            if result.status is Status.DEAL:
                stock[m.lot.lot_id] -= result.agreed.quantity
                deal = Deal(want.buyer_id, m.lot.seller_id, m.lot.lot_id,
                            result.agreed, result.rounds, result.transcript)
                break
        outcomes.append(Outcome(want, deal, tuple(attempts)))
    return outcomes


def main() -> None:
    market = generate(CONFIG)
    segments = Counter(w.segment.value for w in market.wants)
    grades = Counter(lot.grade.value for lot in market.lots)
    print(f"Market (seed {CONFIG.seed})")
    print(f"  sellers {len(market.seller_ids)}, lots {len(market.lots)}, "
          f"grades {dict(sorted(grades.items()))}")
    print(f"  buyers  {len(market.wants)}, segments {dict(segments.most_common())}")

    # matching sees public data only
    lists = shortlist(market.wants, market.lots, CONFIG)
    pairs = [m for ms in lists.values() for m in ms]
    matched = sum(1 for ms in lists.values() if ms)
    all_pairs = len(market.wants) * len(market.lots)
    print(f"\nMatching (top {CONFIG.shortlist_k} sellers per buyer)")
    print(f"  {len(pairs)} pairs to negotiate, out of {all_pairs} possible "
          f"({len(pairs) / all_pairs:.1%})")
    print(f"  buyers with at least one match: {matched}/{len(market.wants)}")

    # simulator-only diagnostic: the simulator holds every secret, matching does not
    viable = sum(1 for m in pairs
                 if market.maxes[m.buyer_id].max_price >= market.floors[m.lot.lot_id].floor_price)
    if pairs:
        print(f"  pairs where a deal is possible (max >= floor): {viable}/{len(pairs)} "
              f"({viable / len(pairs):.0%})")

    example = next(w for w in market.wants if lists[w.buyer_id])
    grades_wanted = "/".join(sorted(g.value for g in example.grades))
    print(f"\n  e.g. {example.buyer_id} ({example.segment.value}) wants {example.quantity} "
          f"{example.category}, grade {grades_wanted}")
    for m in lists[example.buyer_id]:
        print(f"    {m.lot.lot_id:<8} grade {m.lot.grade.value}  {m.quantity:>3} pcs  "
              f"sticker £{m.lot.sticker_price(m.quantity):.2f}  score {m.score:.2f}")

    outcomes = run_market(market, CONFIG)
    deals = [o for o in outcomes if o.deal]
    negotiations = sum(len(o.attempts) for o in outcomes)
    print("\nNegotiation")
    print(f"  {negotiations} negotiations, {len(deals)} buyers closed a deal, "
          f"{len(outcomes) - len(deals)} didn't")
    for o in outcomes[:3]:
        print(f"  {o.want.buyer_id}: {report(o)}")


if __name__ == "__main__":
    main()
