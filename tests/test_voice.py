"""The voice layer, with fake LLMs only. No real API calls."""
import ast
from pathlib import Path

from fleek_market.agents import voice as voice_mod
from fleek_market.agents.ralph import Ralph
from fleek_market.agents.tommy import Tommy
from fleek_market.agents.voice import (Voice, load_env, make_voice, numbers_in,
                                       public_numbers, template)
from fleek_market.core.config import CONFIG
from fleek_market.core.models import Grade, Kind, Lot, Message, Offer, Segment, Side, Tier, Want
from fleek_market.core.private import BuyerLimits, SellerLimits
from fleek_market.negotiation.protocol import negotiate

LOT = Lot("S1-L1", "S1", "denim", Grade.B, 250, 5.00, (Tier(100, 0.05), Tier(250, 0.10)))
OFFER = Message(2, Side.SELLER, Kind.OFFER, Offer(4.35, 250))


def fake(reply):
    return lambda prompt, cfg: reply


def test_llm_text_with_the_right_numbers_is_used():
    out = Voice(fake("For 250 pieces I can do £4.35 each.")).word(OFFER, LOT)
    assert out.text == "For 250 pieces I can do £4.35 each."
    assert out.offer == OFFER.offer  # wording never changes the move


def test_wrong_price_falls_back_to_template():
    out = Voice(fake("Tell you what, £3.99 each and it's yours.")).word(OFFER, LOT)
    assert out.text == template(OFFER, LOT)


def test_invented_extra_number_falls_back_to_template():
    out = Voice(fake("£4.35 each, that's 13% off.")).word(OFFER, LOT)
    assert out.text == template(OFFER, LOT)


def test_failed_call_turns_voice_off_with_one_line(capsys):
    def broken(prompt, cfg):
        raise TimeoutError

    v = Voice(broken)
    first, second = v.word(OFFER, LOT), v.word(OFFER, LOT)
    assert first.text == second.text == template(OFFER, LOT)
    assert not v.on
    assert capsys.readouterr().out.count("voice off") == 1


def test_prompts_carry_only_public_numbers():
    # An agent's final offer can sit on its target by design, so the check is
    # that every number in a prompt is public for that move, and no limit appears.
    prompts = []

    def recorder(prompt, cfg):
        prompts.append(prompt)
        return ""

    want = Want("B1", Segment.PRO, "denim", frozenset({Grade.B}), 250, 250)
    ralph = Ralph(want, LOT, 250, BuyerLimits(4.44))
    tommy = Tommy(LOT, 250, SellerLimits(3.77), "B1")
    v = Voice(recorder)
    transcript = negotiate(ralph, tommy, CONFIG.max_rounds).transcript
    for msg in transcript:
        v.word(msg, LOT)
    assert len(prompts) == len(transcript)
    for msg, prompt in zip(transcript, prompts):
        assert numbers_in(prompt) <= public_numbers(msg, LOT) | {float(LOT.list_price)}
        own_limit = 4.44 if msg.sender is Side.BUYER else 3.77
        assert own_limit not in numbers_in(prompt)


def test_voice_module_never_imports_private_limits_or_strategy():
    tree = ast.parse(Path(voice_mod.__file__).read_text())
    imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not any("private" in m or "strategy" in m for m in imported)


def test_off_by_default_and_off_without_key(monkeypatch, capsys):
    assert make_voice(False) is None
    monkeypatch.setenv("OPENAI_API_KEY", "placeholder")
    monkeypatch.delenv("OPENAI_API_KEY")
    monkeypatch.setattr(voice_mod, "ENV_FILE", Path("/nonexistent/.env"))
    v = make_voice(True, llm=fake("unused"))
    assert v is not None and not v.on
    assert "voice off" in capsys.readouterr().out


def test_env_file_is_read_without_overriding_the_shell(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# comment\nFLEEK_A='from-file'\nFLEEK_B=from-file\n")
    monkeypatch.delenv("FLEEK_A", raising=False)
    monkeypatch.setenv("FLEEK_B", "from-shell")
    load_env(env)
    import os
    assert os.environ["FLEEK_A"] == "from-file" and os.environ["FLEEK_B"] == "from-shell"
    monkeypatch.delenv("FLEEK_A")
