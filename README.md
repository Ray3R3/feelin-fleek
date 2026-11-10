# Ralph & Tommy

Buyer agents (Ralph) and seller agents (Tommy) negotiate bulk lots of secondhand clothing. Neither agent can ever reveal or cross its owner's private price.

A buyer tells Ralph what they want and the most they'll pay. Ralph haggles with the Tommys of the three best-matched sellers and comes back with a checkout, the best price he could get, or a near miss flagged for an account manager.

Scaled down from ~50,000 buyers and ~1,000 sellers to 100 and 20. The design is the same at full size (see [NOTES](NOTES.md#scale)).

## Quick start

You need Python 3.11 or newer. On a Mac: `brew install python@3.12`, then use `python3.12` in place of `python3` below.

```bash
git clone https://github.com/Ray3R3/feelin-fleek.git && cd feelin-fleek
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
make demo
```

No need to activate the environment: `make` uses `.venv` when it exists.

| Command | What it does |
|---|---|
| `make demo` | Runs the market and prints the demo |
| `make demo SEED=3` | Same, on a different random market |
| `make demo-voice` | Same, with an LLM wording the featured negotiation (optional, see below) |
| `make test` | Runs the test suite (a few seconds) |

## What you'll see

- Market: 20 sellers, 100 buyers, lot grades and buyer segments.
- Matching: how many buyer-seller pairs are worth negotiating, out of all possible.
- One negotiation: the longest haggle that closed, round by round.
- Checkout: each closed deal with lot, grade, quantity, price per piece, total and supplier.
- No-deal reports: Ralph's best counter for each buyer, marked near miss (close to their max, flagged for an account manager) or no fit.
- Summary: deals by segment, walk-aways and timeouts, near misses, GMV, Fleek's 15% take, and the buyer/seller surplus split.

## How it works

The core: private limits are enforced in code, rather than by the LLM.

- Matching: filters and ranks lots on public data only, then keeps each buyer's top 3 sellers.
- Ralph and Tommy: each holds one private limit (a buyer's max, a seller's floor) and only ever sends public messages.
- Strategy: opens near the listed price, concedes over the rounds on a privately randomised path, and stops a private margin short of the limit.
- Guardrails: check every outgoing message; any move that would cross the limit becomes a walk-away.
- Protocol: runs the turns and public rules. It never holds a limit, so it has nothing to leak.
- Voice (optional): an LLM rewords a move that is already decided, and its text is rejected if it contains any number that isn't public.

## Changing a fact

Every tunable lives in `src/fleek_market/core/config.py`. For example, set `seller_concession_curve = 1.0` and rerun `make demo`: Tommy concedes sooner and more hobbyists close.

## Optional: LLM wording

```bash
.venv/bin/pip install -e '.[voice]'
echo "OPENAI_API_KEY=sk-..." > .env
make demo-voice
```

The demo works the same without it: with no key, voice prints one line and falls back to plain wording.

## Tests

`make test` runs the suite. The key tests prove three things across many random markets:

- No deal ever closes outside the buyer's max or the seller's floor.
- No agent ever sends its own limit, in any offer, message text or report.
- A seller who has read the strategy code can't work out Ralph's max from his first three offers: the test attacks Ralph and fails if the guess gets too close.

## Layout

```
src/fleek_market/
  core/          public types, private limit types, config
  data/          seeded synthetic market
  matching/      shortlist sellers per buyer
  negotiation/   strategy, guardrails, protocol
  agents/        Ralph, Tommy, optional voice
  cli.py         runs the market and prints the demo
tests/           one file per moving part, plus privacy and inference
```

For assumptions, design, trade-offs, scale, rollout and how it was built, see [NOTES.md](NOTES.md).
