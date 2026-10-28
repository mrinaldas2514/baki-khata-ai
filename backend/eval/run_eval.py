"""Measure how well a parser reads shopkeeper sentences. Run from backend/:

    python -m eval.run_eval --parser rules      # the rule-based parser (no key, no network)
    python -m eval.run_eval --parser llm        # the AI model (needs GROQ_API_KEY in .env)
    python -m eval.run_eval --parser both       # both, plus a side-by-side comparison

Each sentence goes through the same steps as POST /parse (number normalization, the parser,
validation with one retry); customer matching is left out because it needs a shop's
customers. Results are written to eval/results/ as Markdown and JSON, named with the date,
the parser and the model. See eval/README.md.
"""

import argparse
import json
import logging
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import groq

from app.config import get_settings
from app.llm import ChatMessage, LLMClient, LLMProviderError
from app.llm.rule_based import RuleBasedLLMClient
from app.services.parsing import LLMOutputError, NotATransactionError, parse_entries_with_llm
from eval import report
from eval.dataset import DATA_FILE, EVAL_DIR, MY_SENTENCES_FILE, DatasetError, Sentence, load_all
from eval.scoring import FIELDS, Got, percentile, score_sentence

RESULTS_DIR = EVAL_DIR / "results"
# How often (and how long at most) to wait out a rate limit before giving up on a sentence.
MAX_RATE_LIMIT_WAITS = 8
MAX_WAIT_SECONDS = 120.0

logger = logging.getLogger("eval")


class TimedLLM:
    """Wraps a parser to time its calls, and to wait out Groq's rate limits.

    The time spent waiting for a rate limit to pass is not counted, so latency is what a
    shopkeeper would see on an unthrottled account.
    """

    def __init__(self, inner: LLMClient, sleep=time.sleep) -> None:
        self.inner = inner
        self.parser = inner.parser
        self.model = inner.model
        self.elapsed = 0.0
        self._sleep = sleep

    def complete_json(self, messages: list[ChatMessage]) -> str:
        for attempt in range(MAX_RATE_LIMIT_WAITS + 1):
            start = time.perf_counter()
            try:
                answer = self.inner.complete_json(messages)
            except LLMProviderError as exc:
                wait = _rate_limit_wait(exc)
                if wait is None or attempt == MAX_RATE_LIMIT_WAITS:
                    self.elapsed += time.perf_counter() - start
                    raise
                logger.warning("Rate limited; waiting %.0f s", wait)
                self._sleep(wait)
                continue
            self.elapsed += time.perf_counter() - start
            return answer
        raise AssertionError("unreachable")


def _rate_limit_wait(exc: LLMProviderError) -> float | None:
    """Seconds to wait when `exc` is a 429 from Groq, else None."""
    cause = exc.__cause__
    if not isinstance(cause, groq.RateLimitError):
        return None
    try:
        wait = float(cause.response.headers.get("retry-after", "5"))
    except ValueError:
        wait = 5.0
    return min(max(wait, 1.0), MAX_WAIT_SECONDS)


@dataclass
class SentenceResult:
    sentence: Sentence
    got: list[Got]
    # "parsed", or why there are no entries: "refused" (the parser said it isn't a
    # transaction), "invalid_output" (bad answer twice), "provider_error" (the API failed).
    outcome: str
    detail: str | None
    latency_ms: float
    score: object = field(init=False)

    def __post_init__(self) -> None:
        self.score = score_sentence(self.sentence, self.got)


def evaluate(llm: LLMClient, sentences: list[Sentence], delay: float = 0.0, progress=None):
    """Parse every sentence and score it. Returns a list of SentenceResult."""
    timed = TimedLLM(llm)
    results = []
    for n, sentence in enumerate(sentences, start=1):
        timed.elapsed = 0.0
        detail = None
        try:
            parsed = parse_entries_with_llm(timed, sentence.text)
            got = [Got(p.customer_name, p.amount, p.type.value, p.item) for p in parsed]
            outcome = "parsed"
        except NotATransactionError as exc:
            got, outcome, detail = [], "refused", str(exc).split(": ", 1)[-1]
        except LLMOutputError:
            got, outcome = [], "invalid_output"
        except LLMProviderError as exc:
            got, outcome, detail = [], "provider_error", type(exc.__cause__ or exc).__name__
        results.append(SentenceResult(sentence, got, outcome, detail, timed.elapsed * 1000))
        if progress:
            progress(n, len(sentences), results[-1])
        if delay and n < len(sentences):
            time.sleep(delay)
    return results


def _rate(correct: int, total: int) -> dict:
    return {"correct": correct, "total": total, "rate": correct / total if total else None}


def summarize(results: list[SentenceResult]) -> dict:
    fields = {f: [0, 0] for f in FIELDS}
    by_category: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    by_language: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    refused = [0, 0]
    outcomes: dict[str, int] = defaultdict(int)
    for r in results:
        outcomes[r.outcome] += 1
        for entry in r.score.fields:
            for f in FIELDS:
                fields[f][0] += entry[f]
                fields[f][1] += 1
        for bucket in (by_category[r.sentence.category], by_language[r.sentence.language]):
            bucket[0] += r.score.all_correct
            bucket[1] += 1
        if not r.sentence.expected:
            refused[0] += r.score.all_correct
            refused[1] += 1
    latencies = [r.latency_ms for r in results]
    return {
        "sentences": len(results),
        "entries": sum(len(r.sentence.expected) for r in results),
        "all_correct": _rate(sum(r.score.all_correct for r in results), len(results)),
        "fields": {f: _rate(*fields[f]) for f in FIELDS},
        "non_transactions_refused": _rate(*refused),
        "outcomes": dict(outcomes),
        "latency_ms": {
            "mean": sum(latencies) / len(latencies) if latencies else 0.0,
            "p50": percentile(latencies, 50),
            "p95": percentile(latencies, 95),
            "max": max(latencies, default=0.0),
        },
        "categories": {c: _rate(*v) for c, v in sorted(by_category.items())},
        "languages": {c: _rate(*v) for c, v in sorted(by_language.items())},
    }


@dataclass
class Run:
    parser: str
    model: str
    day: date
    results: list[SentenceResult]
    summary: dict

    @property
    def stem(self) -> str:
        return f"{self.day.isoformat()}_{self.parser}_{slug(self.model)}"

    def to_json(self) -> dict:
        return {
            "date": self.day.isoformat(),
            "parser": self.parser,
            "model": self.model,
            "summary": self.summary,
            "results": [
                {
                    "id": r.sentence.id,
                    "category": r.sentence.category,
                    "language": r.sentence.language,
                    "source": r.sentence.source,
                    "text": r.sentence.text,
                    "expected": [e.as_dict() for e in r.sentence.expected],
                    "got": [g.as_dict() for g in r.got],
                    "outcome": r.outcome,
                    "detail": r.detail,
                    "all_correct": r.score.all_correct,
                    "fields": r.score.fields,
                    "extra_entries": r.score.extra_entries,
                    "latency_ms": round(r.latency_ms, 3),
                }
                for r in self.results
            ],
        }


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "-", text.lower()).strip("-")


class ConfigError(Exception):
    pass


def build_parser(kind: str, model: str | None = None) -> LLMClient:
    if kind == "rules":
        return RuleBasedLLMClient()
    settings = get_settings()
    if settings.groq_api_key is None:
        raise ConfigError(
            "--parser llm needs GROQ_API_KEY (in backend/.env or the environment). "
            "Get a key at https://console.groq.com/keys, or run --parser rules."
        )
    from app.llm.groq_client import GroqLLMClient

    # No SDK retries: TimedLLM waits out rate limits itself, outside the timed part.
    return GroqLLMClient(
        api_key=settings.groq_api_key.get_secret_value(),
        model=model or settings.groq_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=0,
    )


def run(llm: LLMClient, sentences: list[Sentence], day: date, delay: float = 0.0, progress=None):
    results = evaluate(llm, sentences, delay=delay, progress=progress)
    return Run(llm.parser, llm.model, day, results, summarize(results))


def save(run_: Run, out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    md, js = out / f"{run_.stem}.md", out / f"{run_.stem}.json"
    md.write_text(report.run_markdown(run_), encoding="utf-8")
    js.write_text(json.dumps(run_.to_json(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return [md, js]


def save_comparison(rules: Run, llm: Run, out: Path) -> list[Path]:
    stem = f"{llm.day.isoformat()}_both_{slug(rules.model)}_vs_{slug(llm.model)}"
    md, js = out / f"{stem}.md", out / f"{stem}.json"
    md.write_text(report.comparison_markdown(rules, llm), encoding="utf-8")
    data = {
        "date": llm.day.isoformat(),
        "runs": {r.parser: {"model": r.model, "summary": r.summary} for r in (rules, llm)},
        "results": [f"{rules.stem}.json", f"{llm.stem}.json"],
    }
    js.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return [md, js]


def _print_progress(n: int, total: int, result: SentenceResult) -> None:
    mark = "ok" if result.score.all_correct else "WRONG"
    print(
        f"  [{n}/{total}] {mark:5} {result.latency_ms:7.0f} ms  {result.sentence.id}",
        file=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    args = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    args.add_argument("--parser", choices=("rules", "llm", "both"), default="rules")
    args.add_argument("--model", help="Groq model for the LLM (default: GROQ_MODEL)")
    args.add_argument("--data", type=Path, default=DATA_FILE, help="the labelled sentences")
    args.add_argument(
        "--my-sentences",
        type=Path,
        default=MY_SENTENCES_FILE,
        help="extra sentences as CSV, read if the file exists (default: eval/my_sentences.csv)",
    )
    args.add_argument("--category", action="append", help="only these categories (repeatable)")
    args.add_argument("--limit", type=int, help="only the first N sentences")
    args.add_argument("--delay", type=float, default=0.0, help="seconds between LLM calls")
    args.add_argument("--out", type=Path, default=RESULTS_DIR, help="where to write results")
    args.add_argument("--no-save", action="store_true", help="print the summary only")
    opts = args.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    try:
        sentences = load_all(opts.data, opts.my_sentences)
    except DatasetError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if opts.category:
        sentences = [s for s in sentences if s.category in opts.category]
    if opts.limit:
        sentences = sentences[: opts.limit]
    if not sentences:
        print("Error: no sentences to evaluate.", file=sys.stderr)
        return 2

    kinds = ["rules", "llm"] if opts.parser == "both" else [opts.parser]
    try:
        parsers = [build_parser(kind, opts.model) for kind in kinds]
    except ConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    day = date.today()
    runs = []
    for llm in parsers:
        print(
            f"Evaluating {llm.parser} ({llm.model}) on {len(sentences)} sentences...",
            file=sys.stderr,
        )
        progress = _print_progress if llm.parser == "llm" else None
        delay = opts.delay if llm.parser == "llm" else 0.0
        runs.append(run(llm, sentences, day, delay=delay, progress=progress))

    for run_ in runs:
        print(report.summary_text(run_))
    if not opts.no_save:
        written = [path for run_ in runs for path in save(run_, opts.out)]
        if len(runs) == 2:
            written += save_comparison(runs[0], runs[1], opts.out)
            print(report.comparison_text(runs[0], runs[1]))
        print("Wrote:\n" + "\n".join(f"  {p}" for p in written))
    return 0


if __name__ == "__main__":
    sys.exit(main())
