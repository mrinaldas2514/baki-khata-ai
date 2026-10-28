"""The browser's copy of the rule-based parser is checked against frontend/src/offline/rulesParity.json;
this keeps that file up to date with the Python rules."""

import json

from eval import rules_parity


def test_the_parity_file_matches_the_python_rules():
    # The data, not the text: a formatter re-indenting the file is fine.
    committed = json.loads(rules_parity.OUT.read_text(encoding="utf-8"))
    assert committed == json.loads(rules_parity.render()), (
        "The rule-based parser changed: run `python -m eval.rules_parity` in backend/ and port "
        "the change to frontend/src/offline/rules.ts."
    )
