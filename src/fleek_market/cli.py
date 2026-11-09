"""Demo runner: build the synthetic market and summarise it."""
from __future__ import annotations

from collections import Counter

from .core.config import CONFIG
from .data.generate import generate


def main() -> None:
    market = generate(CONFIG)
    segments = Counter(w.segment.value for w in market.wants)
    grades = Counter(lot.grade.value for lot in market.lots)
    print(f"Market (seed {CONFIG.seed})")
    print(f"  sellers {len(market.seller_ids)}, lots {len(market.lots)}, "
          f"grades {dict(sorted(grades.items()))}")
    print(f"  buyers  {len(market.wants)}, segments {dict(segments.most_common())}")


if __name__ == "__main__":
    main()
