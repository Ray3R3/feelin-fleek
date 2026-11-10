"""Optional wording layer: turns a move into one natural sentence with an LLM.

Off by default; `make demo-voice` turns it on for the featured transcript.

It runs after the guardrail, on a move that's already decided, and can only
fill in Message.text. The LLM sees the public Message and public lot details,
never a Plan, target, margin or limit (this module doesn't import them). Its
output is checked: every number must be a public one, or we use the template.
"""
from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Callable

from ..core.config import CONFIG, Config
from ..core.models import Kind, Lot, Message, Side

ENV_FILE = Path(__file__).resolve().parents[3] / ".env"  # repo root

INSTRUCTIONS = (
    "You write one short, friendly sentence for a wholesale clothing negotiation. "
    "Say exactly the move you're given. Use only the numbers provided, written the "
    "same way. Don't add prices, totals, percentages or promises."
)

LLM = Callable[[str, Config], str]


def call_llm(prompt: str, cfg: Config) -> str:
    """The only provider-specific code. Switching provider means changing this."""
    from openai import OpenAI

    client = OpenAI(timeout=cfg.voice_timeout, max_retries=0)
    resp = client.responses.create(model=cfg.voice_model, instructions=INSTRUCTIONS,
                                   input=prompt, max_output_tokens=80)
    return resp.output_text.strip()


def load_env(path: Path | None = None) -> None:
    """Read KEY=value lines from .env. Variables already set in the shell win."""
    path = path or ENV_FILE
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def template(msg: Message, lot: Lot) -> str:
    """Plain wording used when voice is off or the LLM's text fails the check."""
    o = msg.offer
    if msg.kind is Kind.WALK:
        return "We're too far apart, so I'll leave it there."
    if msg.kind is Kind.ACCEPT:
        return f"Deal at £{o.price:.2f} a piece." if o else "Deal."
    if msg.sender is Side.BUYER:
        return f"I can do £{o.price:.2f} a piece for {o.quantity} {lot.category}."
    return f"Best I can do is £{o.price:.2f} a piece for {o.quantity}."


def public_numbers(msg: Message, lot: Lot) -> set[float]:
    """Numbers the text is allowed to contain: this offer, and the public listing."""
    allowed = {lot.list_price}
    if msg.offer is not None:
        q = msg.offer.quantity
        allowed |= {msg.offer.price, float(q), lot.sticker_price(q)}
    return allowed


def numbers_in(text: str) -> set[float]:
    found = re.findall(r"(?<![A-Za-z\d.,])\d[\d,]*(?:\.\d+)?", text)
    return {float(n.replace(",", "")) for n in found}


def prompt_for(msg: Message, lot: Lot) -> str:
    who = "buyer" if msg.sender is Side.BUYER else "seller"
    o = msg.offer
    move = {Kind.OFFER: f"offer £{o.price:.2f} per piece for {o.quantity} pieces" if o else "",
            Kind.ACCEPT: f"accept £{o.price:.2f} per piece" if o else "accept",
            Kind.WALK: "walk away politely, no numbers"}[msg.kind]
    return (f"You are the {who}. Lot: {lot.category}, grade {lot.grade.value}, "
            f"list price £{lot.list_price:.2f} per piece. Your move: {move}.")


class Voice:
    def __init__(self, llm: LLM = call_llm, cfg: Config = CONFIG, on: bool = True):
        self.llm, self.cfg, self.on = llm, cfg, on

    def word(self, msg: Message, lot: Lot) -> Message:
        return self.word_all([msg], lot)[0]

    def word_all(self, msgs: list[Message], lot: Lot) -> list[Message]:
        """Word a whole transcript. Calls run concurrently; results keep their order."""
        if not self.on or not msgs:
            return [replace(m, text=template(m, lot)) for m in msgs]
        with ThreadPoolExecutor(max_workers=len(msgs)) as pool:
            replies = list(pool.map(lambda m: self._ask(m, lot), msgs))
        failed = next((r for r in replies if isinstance(r, Exception)), None)
        if failed is not None:  # timeout, auth, network: none of it should stop the demo
            self.on = False
            print(f"(voice off: {type(failed).__name__}, using plain wording)")
        return [replace(m, text=self._checked(r, m, lot)) for m, r in zip(msgs, replies)]

    def _ask(self, msg: Message, lot: Lot) -> str | Exception:
        try:
            return self.llm(prompt_for(msg, lot), self.cfg)
        except Exception as exc:
            return exc

    @staticmethod
    def _checked(reply: str | Exception, msg: Message, lot: Lot) -> str:
        """The LLM's text if every number in it is public for this move, else the template."""
        ok = (isinstance(reply, str) and reply and len(reply) <= 200
              and numbers_in(reply) <= public_numbers(msg, lot))
        return reply if ok else template(msg, lot)


def make_voice(requested: bool, cfg: Config = CONFIG, llm: LLM = call_llm) -> Voice | None:
    """A Voice if asked for and possible; otherwise None, with one line saying why."""
    if not requested:
        return None
    load_env()
    if not os.environ.get("OPENAI_API_KEY"):
        print("(voice off: no OPENAI_API_KEY in .env, using plain wording)")
        return Voice(llm, cfg, on=False)
    if llm is call_llm:
        try:
            import openai  # noqa: F401
        except ImportError:
            print("(voice off: openai package not installed, using plain wording)")
            return Voice(llm, cfg, on=False)
    return Voice(llm, cfg)
