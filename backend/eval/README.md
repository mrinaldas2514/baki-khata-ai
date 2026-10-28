# Parser accuracy evaluation

How well does the app read a shopkeeper's sentence? This folder measures it, for the
rule-based parser (AI off) and for the AI model, on the same labelled sentences.

## Run it

From `backend/`, with the virtual environment on (`source .venv/bin/activate`):

```bash
python -m eval.run_eval --parser rules   # the rule-based parser: no key, no network, < 1 second
python -m eval.run_eval --parser llm     # the AI model: needs GROQ_API_KEY in backend/.env
python -m eval.run_eval --parser both    # both, plus a side-by-side comparison
```

`--parser llm` uses `GROQ_API_KEY` and `GROQ_MODEL` from `backend/.env` (or the environment);
`--model openai/gpt-oss-20b` tries another model. It sends each of the ~190 sentences to Groq
(one request each, two if the first answer is invalid). On Groq's free tier this can hit the
rate limits; the script then waits as long as Groq says (`Retry-After`) and carries on, so a
full run may take several minutes. The waiting is not counted in the latency numbers.
`--delay 2` adds a pause between sentences if you'd rather not hit the limit at all.

Other options: `--category typos` (repeatable) or `--limit 20` for a quick run, `--no-save` to
only print the summary, `--out DIR` for another results folder. `python -m eval.run_eval -h`
lists them all.

The normal test suite (`pytest`) never calls the real API: it runs the evaluation with the
rule-based parser and with scripted fakes.

## What it measures

Each sentence goes through the same steps as `POST /parse`: number normalization, the parser,
and validation with one retry. Customer matching is left out, since it needs a shop's customer
list; names are compared the way matching compares them instead.

| Metric | Meaning |
|---|---|
| **All fields correct** | Per sentence: every entry has the right name, amount, type and item, and nothing extra. A non-transaction is right only when the parser refuses it. |
| Customer name, Amount, Type, Item | Per expected entry. An entry the parser left out counts as wrong in every field. |
| Non-transactions refused | Of the sentences with no transaction (or no amount), how many the parser refused instead of making something up. A parser answer that fails validation (e.g. a phone number read as a 1.7 billion taka amount) also counts as refused: the app shows the manual form and nothing wrong is saved. |
| By category / language | "All fields correct" per category and per language. |
| Latency, average and p95 | Time spent in the parser per sentence, retries included, rate-limit waits excluded. |

How answers are compared:

- **Name**: the same to customer matching, so case, honorifics (bhai, apa...), Bangla or
  English letters and Banglish spelling don't matter: "Rahim bhai" = "rohim" = "রহিম".
  "Rahima" is a different name.
- **Amount** and **type** (credit/payment): exactly.
- **Item**: the same words in any order, ignoring commas and "r"/"ar"/"and"
  ("dal r tel" = "dal, tel"), with Bangla digits read as digits. No item must be no item.
- **Several entries**: compared in order (the first answer with the first expected entry).

## Results

Each run writes `results/<date>_<parser>_<model>.md` (summary, categories, every failure with
text, expected and got) and `.json` (the same, plus every sentence's result). `--parser both`
also writes `results/<date>_both_<rules model>_vs_<llm model>.md` with the side-by-side table
and the sentences only one of them gets right.

## The sentences

`data/sentences.json`, one sentence per line, ~190 of them in 14 categories: Banglish credit and
payment, Bangla script, English, code-mixed, number words (pach sho, dedh hajar, arai sho, sowa
sho...), Bangla digits, honorifics, items, typos and missing spaces, past-tense payments
(shodh korlo, joma dilo, ferot dilo...), several entries in one sentence, no amount, and not a
transaction. `expected` lists the entries in order (empty: the parser should refuse);
`name_also` / `item_also` list other acceptable answers.

The prompt's few-shot examples (`app/services/parse_prompt.py`) are deliberately different
sentences, so the evaluation measures generalization, not memory.

### Adding real sentences from shopkeepers

Copy `my_sentences.template.csv` to `my_sentences.csv` and add rows; every run reads it when it
exists (category `my_sentences`).

```csv
text,customer_name,amount,type,item
rahim bhai 2 kg chal 120 taka baki,rahim,120,credit,2 kg chal
"karim 500 dilo, salma 200 baki",karim,500,payment,
"karim 500 dilo, salma 200 baki",salma,200,credit,
```

- `type`: `credit` (or `baki`) or `payment` (or `joma`); `amount`: whole taka.
- A sentence about several customers: one row per entry, with the same `text`, one after another.
- A sentence that isn't a transaction (or has no amount): leave `customer_name` and `amount` empty.
- Put the text in quotes when it has a comma.

`my_sentences.csv` is git-ignored: real sentences carry real customers' names. The results files
include the sentences too, so replace the names (or don't commit those results) before sharing.
