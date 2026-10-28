"""The browser's copy of the rule-based parser is checked against frontend/src/offline/rulesParity.json;
this keeps that file up to date with the Python rules."""

from eval import rules_parity


def test_the_parity_file_matches_the_python_rules():
    assert rules_parity.OUT.read_text(encoding="utf-8") == rules_parity.render(), (
        "The rule-based parser changed: run `python -m eval.rules_parity` in backend/ and port "
        "the change to frontend/src/offline/rules.ts."
    )
