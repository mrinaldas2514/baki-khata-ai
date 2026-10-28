"""Markdown and terminal reports for eval runs (see run_eval.py)."""

from eval.scoring import FIELDS

FIELD_LABELS = {"name": "Customer name", "amount": "Amount", "type": "Type", "item": "Item"}
CATEGORY_LABELS = {
    "banglish_credit": "Banglish, baki",
    "banglish_payment": "Banglish, joma",
    "bangla_script": "Bangla script",
    "english": "English",
    "code_mixed": "Code-mixed",
    "number_words": "Number words (pach sho, dedh hajar...)",
    "bangla_digits": "Bangla digits",
    "honorifics": "Honorifics (bhai, apa, da...)",
    "items": "Items",
    "typos": "Typos and missing spaces",
    "past_payment": "Past-tense payments (shodh korlo...)",
    "multi_entry": "Several entries in one sentence",
    "no_amount": "No amount (should be refused)",
    "non_transaction": "Not a transaction (should be refused)",
    "my_sentences": "my_sentences.csv",
}
TYPE_WORDS = {"credit": "baki", "payment": "joma"}
_ORDER = {c: i for i, c in enumerate(CATEGORY_LABELS)}


def in_order(categories: dict) -> list[str]:
    """Categories in the order of CATEGORY_LABELS (unknown ones last)."""
    return sorted(categories, key=lambda c: (_ORDER.get(c, len(_ORDER)), c))


def pct(rate: dict) -> str:
    if rate["rate"] is None:
        return "–"
    return f"{rate['rate'] * 100:.1f}% ({rate['correct']}/{rate['total']})"


def ms(value: float) -> str:
    return f"{value:.1f} ms" if value < 100 else f"{value:.0f} ms"


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ⏎ ")


def describe_entries(entries: list[dict]) -> str:
    """'rahim · ৳120 · baki · 2 kg chal + karim · ৳500 · joma'."""
    parts = []
    for e in entries:
        words = [e["customer_name"], f"৳{e['amount']}", TYPE_WORDS.get(e["type"], e["type"])]
        if e.get("item"):
            words.append(e["item"])
        parts.append(" · ".join(words))
    return " + ".join(parts)


def _expected_cell(row: dict) -> str:
    return describe_entries(row["expected"]) or "(refuse: not a transaction)"


def _got_cell(row: dict) -> str:
    if row["got"]:
        return describe_entries(row["got"])
    if row["outcome"] == "refused":
        return f"(refused: {row['detail']})"
    return f"({row['outcome'].replace('_', ' ')}{': ' + row['detail'] if row['detail'] else ''})"


def _wrong_fields(row: dict) -> str:
    if row["expected"] and not row["got"]:
        return "no entry"
    if not row["expected"]:
        return "should refuse"
    wrong = [f for entry in row["fields"] for f in FIELDS if not entry[f]]
    if len(row["got"]) != len(row["expected"]):
        wrong.append(f"{len(row['got'])} entries, not {len(row['expected'])}")
    return ", ".join(dict.fromkeys(wrong))


def _summary_rows(summary: dict) -> list[tuple[str, str]]:
    latency = summary["latency_ms"]
    rows = [("**All fields correct** (per sentence)", f"**{pct(summary['all_correct'])}**")]
    rows += [(f"{FIELD_LABELS[f]} (per entry)", pct(summary["fields"][f])) for f in FIELDS]
    rows.append(("Non-transactions refused", pct(summary["non_transactions_refused"])))
    rows.append(("Latency per sentence, average", ms(latency["mean"])))
    rows.append(("Latency per sentence, p95", ms(latency["p95"])))
    return rows


def run_markdown(run) -> str:
    data = run.to_json()
    summary = run.summary
    sources = {}
    for r in data["results"]:
        sources[r["source"]] = sources.get(r["source"], 0) + 1
    source_text = ", ".join(f"{n} from {s}" for s, n in sources.items())
    failures = [r for r in data["results"] if not r["all_correct"]]
    errors = [r for r in data["results"] if r["outcome"] in ("invalid_output", "provider_error")]

    lines = [
        f"# Parser evaluation: {run.parser} ({run.model})",
        "",
        f"- **Date:** {run.day.isoformat()}",
        f"- **Parser:** `{run.parser}`, model `{run.model}`",
        f"- **Sentences:** {summary['sentences']} ({source_text}), "
        f"{summary['entries']} expected entries",
        f"- **Command:** `python -m eval.run_eval --parser {run.parser}` (in `backend/`)",
        "",
        "Each sentence goes through the same steps as `POST /parse` (number normalization, the "
        "parser, validation with one retry). A sentence is right only if every entry has the "
        "right customer name, amount, type and item, and nothing extra; a non-transaction is "
        "right only if the parser refuses it.",
        "",
    ]
    if errors:
        refusals = sum(not r["expected"] for r in errors)
        lines += [
            f"> **Errors:** {len(errors)} sentence(s) got no usable answer ("
            + ", ".join(f"`{r['id']}` {r['outcome'].replace('_', ' ')}" for r in errors)
            + f"). Counted as wrong, except {refusals} that should be refused anyway (the app "
            "then shows the manual form, so nothing wrong is saved).",
            "",
        ]
    lines += ["## Summary", "", "| Metric | Result |", "|---|---|"]
    lines += [f"| {a} | {b} |" for a, b in _summary_rows(summary)]
    lines += ["", "## By category", "", "| Category | All fields correct |", "|---|---|"]
    lines += [
        f"| {CATEGORY_LABELS.get(c, c)} | {pct(summary['categories'][c])} |"
        for c in in_order(summary["categories"])
    ]
    lines += ["", "## By language", "", "| Language | All fields correct |", "|---|---|"]
    lines += [f"| {lang} | {pct(rate)} |" for lang, rate in summary["languages"].items()]
    lines += ["", f"## Failures ({len(failures)})", ""]
    if failures:
        lines += ["| Id | Text | Expected | Got | Wrong |", "|---|---|---|---|---|"]
        lines += [
            f"| {r['id']} | {_cell(r['text'])} | {_cell(_expected_cell(r))} | "
            f"{_cell(_got_cell(r))} | {_wrong_fields(r)} |"
            for r in failures
        ]
    else:
        lines.append("None.")
    return "\n".join(lines) + "\n"


def comparison_markdown(rules, llm) -> str:
    a, b = rules.summary, llm.summary
    lines = [
        f"# Parser comparison: {rules.parser} vs {llm.parser}",
        "",
        f"- **Date:** {llm.day.isoformat()}",
        f"- **Sentences:** {a['sentences']}, {a['entries']} expected entries",
        "- **Command:** `python -m eval.run_eval --parser both` (in `backend/`)",
        f"- **Details:** `{rules.stem}.md`, `{llm.stem}.md`",
        "",
        "## Summary",
        "",
        f"| Metric | {rules.parser} (`{rules.model}`) | {llm.parser} (`{llm.model}`) |",
        "|---|---|---|",
    ]
    lines += [
        f"| {label} | {x} | {y} |"
        for (label, x), (_, y) in zip(_summary_rows(a), _summary_rows(b), strict=True)
    ]
    lines += [
        "",
        "## By category (all fields correct)",
        "",
        f"| Category | {rules.parser} | {llm.parser} |",
        "|---|---|---|",
    ]
    for c in in_order(a["categories"]):
        lines.append(
            f"| {CATEGORY_LABELS.get(c, c)} | {pct(a['categories'][c])} | "
            f"{pct(b['categories'].get(c, {'rate': None}))} |"
        )
    fixed, broken = differences(rules, llm)
    lines += ["", f"## Right only with {llm.parser} ({len(fixed)})", ""]
    lines += [f"- `{r.sentence.id}` {_cell(r.sentence.text)}" for r in fixed] or ["None."]
    lines += ["", f"## Right only with {rules.parser} ({len(broken)})", ""]
    lines += [f"- `{r.sentence.id}` {_cell(r.sentence.text)}" for r in broken] or ["None."]
    return "\n".join(lines) + "\n"


def differences(first, second):
    """(sentences only `second` got right, sentences only `first` got right)."""
    pairs = list(zip(first.results, second.results, strict=True))
    only_second = [y for x, y in pairs if y.score.all_correct and not x.score.all_correct]
    only_first = [x for x, y in pairs if x.score.all_correct and not y.score.all_correct]
    return only_second, only_first


def summary_text(run) -> str:
    s = run.summary
    fields = "  ".join(f"{f} {s['fields'][f]['rate'] * 100:.1f}%" for f in FIELDS)
    return (
        f"{run.parser} ({run.model}): all fields correct {pct(s['all_correct'])}\n"
        f"  {fields}\n"
        f"  non-transactions refused {pct(s['non_transactions_refused'])}\n"
        f"  latency avg {ms(s['latency_ms']['mean'])}, p95 {ms(s['latency_ms']['p95'])}"
    )


def comparison_text(rules, llm) -> str:
    fixed, broken = differences(rules, llm)
    return f"{llm.parser} gets {len(fixed)} sentences right that {rules.parser} misses; {len(broken)} the other way."
