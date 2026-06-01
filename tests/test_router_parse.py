"""Intent parsing must read the model's decision by whole word, and fall back
to the safe superset ("hybrid") when the reply is ambiguous or unrecognized."""
from app.rag.router import _parse_intent


def test_clean_one_word_replies():
    assert _parse_intent("quantitative") == "quantitative"
    assert _parse_intent("qualitative") == "qualitative"
    assert _parse_intent("hybrid") == "hybrid"


def test_case_and_punctuation_tolerated():
    assert _parse_intent("Quantitative.") == "quantitative"
    assert _parse_intent("  HYBRID\n") == "hybrid"


def test_chatty_reply_with_one_intent():
    assert _parse_intent("This is clearly a qualitative question") == "qualitative"


def test_substring_does_not_shadow_a_different_intent():
    # "qualitative" must not be mis-read as "quantitative" (loose substring bug).
    assert _parse_intent("qualitative") == "qualitative"


def test_ambiguous_reply_falls_back_to_hybrid():
    assert _parse_intent("could be quantitative or qualitative") == "hybrid"


def test_unrecognized_reply_falls_back_to_hybrid():
    assert _parse_intent("I'm not sure") == "hybrid"
    assert _parse_intent("") == "hybrid"
