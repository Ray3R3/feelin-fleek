"""Demo runner: build the synthetic market, shortlist, and summarise."""
from __future__ import annotations

from collections import Counter

from .core.config import CONFIG
from .data.generate import generate
from .matching.match import shortlist


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


if __name__ == "__main__":
    main()
