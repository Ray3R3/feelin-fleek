"""Demo runner: build the market, shortlist, negotiate, then print one
transcript, the checkout, and a market summary.

This is the simulator, so it is the one place that holds every secret. It hands
each max to one Ralph and each floor to one Tommy, and nothing else sees them.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, replace

from .agents.ralph import Outcome, Ralph, debrief, report
from .agents.tommy import Tommy
from .agents.voice import Voice, make_voice
from .core.config import CONFIG, Config
from .core.models import Deal, Kind, Lot, Side
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
        outcomes.append(debrief(want, deal, attempts, market.maxes[want.buyer_id], cfg))
    return outcomes


@dataclass(frozen=True)
class Summary:
    buyers: int
    closed: int
    closed_by_segment: dict[str, tuple[int, int]]  # segment -> (closed, buyers)
    negotiations: dict[str, int]  # deal / walk / timeout
    near_misses: int  # no deal, but close enough to be worth an intro
    price_vs_list: float  # average deal price as a share of list
    gmv: float
    fleek_take: float
    buyer_surplus: float  # sum of (max - price) * qty
    seller_surplus: float  # sum of (price - floor) * qty


def summarise(market: Market, outcomes: list[Outcome], cfg: Config = CONFIG) -> Summary:
    """Market-level numbers. Surplus needs the private limits, so only the
    simulator can compute it; no agent or Fleek service ever could."""
    lots = {lot.lot_id: lot for lot in market.lots}
    deals = [o.deal for o in outcomes if o.deal]
    by_segment: dict[str, list[int]] = {}
    for o in outcomes:
        tally = by_segment.setdefault(o.want.segment.value, [0, 0])
        tally[0] += o.deal is not None
        tally[1] += 1
    statuses = Counter(r.status.value for o in outcomes for _, r in o.attempts)
    gmv = sum(d.offer.total for d in deals)
    return Summary(
        buyers=len(outcomes),
        closed=len(deals),
        closed_by_segment={k: (v[0], v[1]) for k, v in by_segment.items()},
        negotiations={s.value: statuses.get(s.value, 0) for s in Status},
        near_misses=sum(o.near_miss for o in outcomes),
        price_vs_list=(sum(d.offer.price / lots[d.lot_id].list_price for d in deals) / len(deals)
                       if deals else 0.0),
        gmv=round(gmv, 2),
        fleek_take=round(gmv * cfg.commission_rate, 2),
        buyer_surplus=round(sum((market.maxes[d.buyer_id].max_price - d.offer.price)
                                * d.offer.quantity for d in deals), 2),
        seller_surplus=round(sum((d.offer.price - market.floors[d.lot_id].floor_price)
                                 * d.offer.quantity for d in deals), 2),
    )


def print_transcript(outcome: Outcome, lot: Lot, voice: Voice | None = None) -> None:
    d, w = outcome.deal, outcome.want
    print(f"\nOne negotiation: {d.buyer_id} ({w.segment.value}) and {d.seller_id}, "
          f"{d.offer.quantity} {lot.category} grade {lot.grade.value}, "
          f"list £{lot.list_price:.2f}/pc")
    msgs = list(d.transcript)
    if voice is not None:
        msgs = voice.word_all(msgs, lot)  # wording only; the moves are already decided
    for m in msgs:
        who = "Ralph" if m.sender is Side.BUYER else "Tommy"
        if m.kind is Kind.OFFER:
            line = f"offers £{m.offer.price:.2f}/pc"
        elif m.kind is Kind.ACCEPT:
            line = f"accepts £{d.offer.price:.2f}/pc"
        else:
            line = "walks away"
        said = f'  "{m.text}"' if m.text else ""
        print(f"  R{m.round}  {who:<5}  {line}{said}")


def print_checkout(deals: list[Deal], lots: dict[str, Lot], limit: int | None) -> None:
    print(f"\nCheckout ({len(deals)} orders)")
    for d in deals[:limit]:
        lot = lots[d.lot_id]
        price, total = f"£{d.offer.price:.2f}", f"£{d.offer.total:,.2f}"
        print(f"  {d.buyer_id}  {lot.category:<10} grade {lot.grade.value}  "
              f"{d.offer.quantity:>3} pcs  @ {price:>6}/pc  = {total:>10}   "
              f"supplier {d.seller_id} (lot {d.lot_id})")
    if limit is not None and len(deals) > limit:
        print(f"  ... and {len(deals) - limit} more (--all to list them)")


def print_misses(misses: list[Outcome], limit: int | None) -> None:
    print(f"\nNo deal ({len(misses)} buyers)")
    for o in misses[:limit]:
        print(f"  {o.want.buyer_id}: {report(o)}")
    if limit is not None and len(misses) > limit:
        print(f"  ... and {len(misses) - limit} more")


def print_summary(s: Summary, cfg: Config) -> None:
    seg = ", ".join(f"{k} {c}/{n}" for k, (c, n) in s.closed_by_segment.items())
    total = s.buyer_surplus + s.seller_surplus
    n = s.negotiations
    print("\nSummary")
    print(f"  buyers who closed      {s.closed}/{s.buyers} ({seg})")
    print(f"  negotiations           {sum(n.values())}: {n['deal']} deals, "
          f"{n['walk']} walk-aways, {n['timeout']} timeouts")
    print(f"  near misses            {s.near_misses} buyers flagged for an account-manager intro")
    print(f"  avg price vs list      {s.price_vs_list:.0%}")
    print(f"  GMV                    £{s.gmv:,.2f}")
    print(f"  Fleek take at {cfg.commission_rate:.0%}      £{s.fleek_take:,.2f}")
    if total > 0:
        print(f"  surplus split          buyers £{s.buyer_surplus:,.2f} "
              f"({s.buyer_surplus / total:.0%}), sellers £{s.seller_surplus:,.2f} "
              f"({s.seller_surplus / total:.0%})")
        print("                         (simulator view: needs the private limits)")


def main(argv: list[str] | None = None) -> None:
    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument("--seed", type=int, help="market seed (default from config)")
    args.add_argument("--all", action="store_true", help="list every order and miss")
    args.add_argument("--voice", action="store_true",
                      help="word the featured transcript with an LLM (needs OPENAI_API_KEY)")
    opts = args.parse_args(argv)
    cfg = CONFIG if opts.seed is None else replace(CONFIG, seed=opts.seed)
    limit = None if opts.all else 10

    market = generate(cfg)
    segments = Counter(w.segment.value for w in market.wants)
    grades = Counter(lot.grade.value for lot in market.lots)
    print(f"Market (seed {cfg.seed})")
    print(f"  sellers {len(market.seller_ids)}, lots {len(market.lots)}: "
          + " · ".join(f"{g} {n}" for g, n in sorted(grades.items())))
    print(f"  buyers  {len(market.wants)}: "
          + " · ".join(f"{seg} {n}" for seg, n in segments.most_common()))

    # matching sees public data only
    lists = shortlist(market.wants, market.lots, cfg)
    pairs = [m for ms in lists.values() for m in ms]
    all_pairs = len(market.wants) * len(market.lots)
    viable = sum(1 for m in pairs
                 if market.maxes[m.buyer_id].max_price >= market.floors[m.lot.lot_id].floor_price)
    print(f"\nMatching (top {cfg.shortlist_k} sellers per buyer)")
    print(f"  {len(pairs)} pairs to negotiate, out of {all_pairs} possible "
          f"({len(pairs) / all_pairs:.1%})")
    if pairs:  # simulator-only: needs both secrets
        print(f"  pairs where a deal is possible (max >= floor): {viable}/{len(pairs)} "
              f"({viable / len(pairs):.0%})")

    outcomes = run_market(market, cfg)
    lots = {lot.lot_id: lot for lot in market.lots}
    closed = [o for o in outcomes if o.deal]
    if closed:
        # the longest haggle makes the most readable example
        longest = max(closed, key=lambda o: o.deal.rounds)
        print_transcript(longest, lots[longest.deal.lot_id], make_voice(opts.voice, cfg))
    print_checkout([o.deal for o in closed], lots, limit)
    print_misses([o for o in outcomes if not o.deal], limit and 5)
    print_summary(summarise(market, outcomes, cfg), cfg)


if __name__ == "__main__":
    main()
