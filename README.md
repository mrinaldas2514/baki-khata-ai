# Baki Khata AI

A mobile-first app for small shopkeepers in Bangladesh and India to track customer
credit (*baki*) by typing or speaking Banglish instead of writing in a paper ledger.

This repository currently contains the **backend**: a REST API built with FastAPI,
SQLAlchemy and Pydantic, plus an **AI parsing layer** that turns one free-form sentence
("rahim bhai 2 kg chal 120 taka baki") into a transaction preview. There's no frontend yet.

## Project structure

```
backend/
├── app/
│   ├── main.py          # FastAPI app factory, routers, error handlers
│   ├── config.py        # Settings from environment variables / .env
│   ├── database.py      # Engine + per-request session
│   ├── time_utils.py    # UTC / shop-local-time helpers
│   ├── llm/             # LLM interface + Groq implementation (swap providers here)
│   ├── models/          # SQLAlchemy tables: Shop, Customer, Transaction
│   ├── schemas/         # Pydantic request/response models and validation
│   ├── routers/         # HTTP endpoints (thin, just call services)
│   └── services/        # Business logic (balance, customers, transactions, dashboard,
│                        #   parsing, parse_prompt, number_words, name_matching)
├── tests/               # pytest suite (the LLM is always faked)
│   └── fixtures/eval_sentences.json   # example sentences + expected output
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml       # pytest config
└── .env.example
```

## Data model

```
shops 1 ──── * customers 1 ──── * transactions
  └──────────────────────────────────┘ (transactions also carry shop_id)
```

| Table | Columns |
|---|---|
| **shops** | `id`, `name`, `owner_name`, `created_at` |
| **customers** | `id`, `shop_id`, `name`, `phone` (optional), `note` (optional area/note), `created_at` |
| **transactions** | `id`, `shop_id`, `customer_id`, `type` (`credit` \| `payment`), `amount`, `item` (optional), `raw_text` (optional), `created_at` |

- **`type`**: `credit` means the customer took goods on baki. `payment` means the customer paid money.
- **`amount`**: a whole number of taka, always greater than 0 (also enforced by a database
  CHECK constraint). The `type` says which direction the money moved, so amounts are never negative.
- **`note`**: tells apart two customers with the same name, e.g. "Rahim (Bazar road)" and
  "Rahim (Tea stall)". Within a shop, two customers may only share a name if their notes differ.
- **`raw_text`**: the original sentence the shopkeeper typed or spoke, e.g.
  *"Rahim 2 kg chal nilo 250 taka baki"*. It's kept so the AI layer can be checked and improved later.
- **`created_at`**: when the transaction happened. It defaults to now and can be backdated
  (for "gotokal nilo"/"took it yesterday") but can't be in the future.
- **Balance is never stored.** It's always calculated from the transactions (see below).

### How the balance is calculated

```
balance = (sum of all credit amounts) − (sum of all payment amounts)
```

- **Positive**: the customer owes the shop that much baki.
- **Zero**: the account is fully settled.
- **Negative**: the customer has paid in advance.

Because the balance is always recalculated from the transactions, editing or deleting a
transaction automatically gives the correct new balance. Nothing can drift out of sync.
The logic lives in one place, `app/services/balance.py`, with a pure-Python version (used for
running balances) and an identical SQL version (used to sum many customers at once).

- **Running balance**: the customer's transactions are sorted oldest first, and each row
  shows the balance right after it.
- **Total outstanding baki** (dashboard): the sum of *positive* balances only. A customer who
  paid in advance doesn't reduce what other customers owe.
- **Baki older than 30 days** (dashboard): payments are applied to the oldest credits first
  (first in, first out), the way a shopkeeper would think about it. A customer is overdue when
  their oldest *still-unpaid* credit is more than 30 days old. For example, if Rahim took ৳100
  40 days ago and ৳50 5 days ago, then paid ৳100, the old debt is cleared and he isn't overdue.
- **Today's collection**: the sum of payments made during the shop's local calendar day
  (`APP_TIMEZONE`, default `Asia/Dhaka`).

### Time handling

All timestamps are stored and returned in **UTC** (ISO 8601, e.g. `2026-10-26T09:30:00Z`).
If a request sends a date without a timezone, it's read as the shop's local time
(`APP_TIMEZONE`).

## API

Interactive docs are available at `http://localhost:8000/docs` once the server is running.

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/shops` | Create a shop |
| GET | `/shops/{shop_id}` | Get a shop |
| POST | `/shops/{shop_id}/customers` | Create a customer |
| GET | `/shops/{shop_id}/customers?search=` | List customers with balances (optional search by name/note/phone) |
| GET | `/shops/{shop_id}/customers/{customer_id}` | Get one customer with current balance |
| POST | `/shops/{shop_id}/customers/{customer_id}/transactions` | Create a transaction (response includes the new balance) |
| GET | `/shops/{shop_id}/customers/{customer_id}/transactions` | Customer ledger with running balance |
| GET | `/shops/{shop_id}/transactions/{transaction_id}` | Get one transaction |
| PATCH | `/shops/{shop_id}/transactions/{transaction_id}` | Edit a transaction (only the fields you send) |
| DELETE | `/shops/{shop_id}/transactions/{transaction_id}` | Delete a transaction (204) |
| GET | `/shops/{shop_id}/dashboard?overdue_days=30` | Total outstanding, today's collection, top 5, overdue customers |
| POST | `/shops/{shop_id}/parse` | Turn one free-form sentence into a transaction **preview** (saves nothing) |
| POST | `/shops/{shop_id}/parse/confirm` | Save the confirmed preview, creating the customer if new |

Every customer and transaction is looked up within its shop. Asking for another shop's data
returns 404.

**Errors**

- `404` / `409`: `{"detail": "Customer 7 not found in shop 1"}`
- `422`: errors are listed per field, so the app can show them next to the input:

```json
{
  "detail": "Invalid request data",
  "errors": [{"field": "amount", "message": "Amount must be greater than 0"}]
}
```

**Example**

```bash
curl -X POST localhost:8000/shops/1/customers/1/transactions \
  -H 'content-type: application/json' \
  -d '{"type": "credit", "amount": 250, "item": "2 kg chal", "raw_text": "Rahim 2 kg chal nilo 250 taka baki"}'
```

## Running the backend locally

Requires Python 3.11+ (developed on 3.13).

```bash
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                 # then edit if needed
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs. Tables are created automatically on startup in a SQLite file,
`backend/baki_khata.db`. Run commands from inside `backend/` so the `.env` file is picked up.

### Configuration

All settings come from environment variables or `backend/.env`. See `.env.example`.
Don't commit `.env`; it's already in `.gitignore`.

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./baki_khata.db` | Database connection |
| `APP_TIMEZONE` | `Asia/Dhaka` | Decides what "today" means (`Asia/Kolkata` for India) |
| `APP_NAME` | `Baki Khata AI` | Shown in the API docs |
| `ENVIRONMENT` | `development` | Free-form environment label |
| `SQL_ECHO` | `false` | Log SQL statements |
| `GROQ_API_KEY` | *(empty)* | Groq API key for AI parsing. Without it, `/parse` returns 503 and everything else works |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq chat model; must support JSON mode |
| `LLM_TIMEOUT_SECONDS` | `20` | How long to wait for the model |

### Switching to PostgreSQL

No code changes are needed:

```bash
pip install "psycopg[binary]"
# in .env
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/baki_khata
```

### Setting up Groq (AI parsing)

1. Create a free API key at https://console.groq.com/keys.
2. Put it in `backend/.env` (never in code, never committed; `.env` is git-ignored):

   ```bash
   GROQ_API_KEY=gsk_your_key_here
   GROQ_MODEL=llama-3.3-70b-versatile
   ```

   Any model listed at https://console.groq.com/docs/models that supports JSON mode works.
   If Groq retires the default model, just change `GROQ_MODEL`.
3. Restart `uvicorn` and try it:

   ```bash
   curl -X POST localhost:8000/shops/1/parse -H 'content-type: application/json' \
     -d '{"text": "salma apa pach sho taka baki, dal r tel"}'
   ```

## AI parsing

A shopkeeper types (or later speaks) one sentence in Banglish, Bangla script, English or a
mix. The backend turns it into a **preview**; nothing is saved until the shopkeeper confirms.

```
"salma apa pach sho taka baki, dal r tel"
   │ 1. number normalization   (app/services/number_words.py)    no AI
   ▼    "salma apa 500 taka baki, dal r tel"
   │ 2. LLM, JSON mode         (app/services/parse_prompt.py, app/llm/)
   ▼    {"customer_name": "salma", "amount": 500, "type": "credit", "item": "dal, tel", "confidence": 0.95}
   │ 3. Pydantic validation, one retry on bad output   (app/services/parsing.py)
   │ 4. sanity check: is the amount really in the sentence?
   │ 5. customer name matching (app/services/name_matching.py)  no AI
   ▼
preview  →  shopkeeper checks / edits  →  POST /parse/confirm  →  saved, with raw_text
```

### 1. Number normalization (no AI)

LLMs are unreliable with spoken Banglish numbers, so they're converted with plain rules
before the model sees them. Bangla digits (`২০০` → `200`), thousands separators (`2,500`,
`1,25,000`), and spoken amounts:

| Said | Becomes | Rule |
|---|---|---|
| pach sho / pachsho / পাঁচশো | 500 | number × sho (100) |
| dedh hajar / দেড় হাজার | 1500 | dedh = 1.5 × |
| arai sho / আড়াই শো | 250 | arai = 2.5 × |
| sare tin sho / সাড়ে তিন শো | 350 | sare N = N + ½ |
| poune dui hajar | 1750 | poune N = N − ¼ |
| ek hajar pach sho ponchash taka | 1550 | groups add up |
| bish taka / five hundred taka | 20 / 500 | number word before taka/tk/টাকা |

A number word is only converted before a multiplier (sho/hajar/lakh) or a currency word, so
"tin kg alu" or "met at the shop" are left alone. The model gets both the original sentence
and the converted one.

### 2. Prompt design

The prompt lives in `app/services/parse_prompt.py`:

- **Strict output contract**: exactly one JSON object with `customer_name`, `amount`
  (integer taka), `type` (`credit` | `payment`), `item` (nullable) and `confidence` (0–1).
  Groq's JSON mode is on and `temperature` is 0, so the same sentence parses the same way.
- **Explicit rules** for the hard parts: strip honorifics from the name but keep its script;
  the amount is money, never a quantity ("2 kg chal 120 taka" → 120); which words mean
  credit (baki, nilo, dhar, বাকি...) and payment (dilo, jama, shodh, দিল...); goods with no
  payment word count as credit; "r"/"ar"/"আর" join items.
- **Number-word table** as a fallback in case anything slips past step 1.
- **An escape hatch**: if there's no name or no amount, the model answers
  `{"error": "..."}` instead of guessing. The API returns that as a 422.
- **Few-shot examples** covering Banglish, Bangla script, English, a payment and the error
  case. They're deliberately *different* from the evaluation sentences, so the evaluation
  measures generalization rather than memorization.

### 3. Validation and retry

The answer is validated with the Pydantic model `ParsedTransaction`
(`app/schemas/parse.py`): the amount must be a whole number from 1 to 1 crore (`500.0` is
accepted, `"500"` and `12.5` are not), the type must be credit/payment, confidence 0–1. If
the JSON is broken or a field is invalid, the model is asked **once** more, with its bad
answer and the exact problem. If that also fails the API returns **502** with a clear message
and the shopkeeper can enter the transaction manually.

### 4. Sanity check

If the amount the model returned doesn't appear in the (normalized) sentence, it was
probably made up: the preview gets a warning and the confidence is capped at 0.5.

### 5. Customer name matching (no AI)

The parsed name is compared with every customer of the shop. Both sides are cleaned the same
way: honorifics removed (bhai, vai, apa, apu, da, di, dada, didi, kaka, mama, chacha, khala,
bhabi, boudi, sir, saheb, ji, Mr, ভাই, আপা, দা, দি...), Bangla script romanized
(`রহিম` → `rahim`), and a phonetic key that ignores common Banglish spelling differences
(Rohim/Rahim, Korim/Karim, Kareem/Karim, Shalma/Salma, Zakir/Jakir). Each customer gets a
similarity score from 0 to 100.

| `match.status` | Meaning | What the app should do |
|---|---|---|
| `exact` | One customer has the same name (ignoring case, honorifics and script) | Preselect `match.customer` |
| `fuzzy` | No exact match, but one customer is clearly closest (score ≥ 92, 8+ points ahead) | Preselect it and show the warning |
| `ambiguous` | Several fit (e.g. two "Rahim"s with different notes) or the best is only similar (Rahim vs Rahima) | Ask the shopkeeper to pick from `match.candidates` or create a new customer |
| `new` | Nobody is close | Offer to create `match.suggested_name` |

Candidates include each customer's note, phone and current balance, so the shopkeeper can
tell two Rahims apart.

### Endpoints

**Preview**: `POST /shops/{shop_id}/parse` with `{"text": "rahim bhai 2 kg chal 120 taka baki"}`

```json
{
  "raw_text": "rahim bhai 2 kg chal 120 taka baki",
  "parsed": {"customer_name": "rahim", "amount": 120, "type": "credit", "item": "2 kg chal", "confidence": 0.95},
  "match": {
    "status": "exact",
    "customer": {"id": 1, "name": "Rahim", "note": "Bazar road", "balance": 300, "score": 100, "...": "..."},
    "candidates": [{"id": 1, "name": "Rahim", "score": 100, "...": "..."}],
    "suggested_name": "Rahim"
  },
  "warnings": []
}
```

**Confirm**: `POST /shops/{shop_id}/parse/confirm` with the (possibly edited) values and
**either** an existing `customer_id` **or** a `new_customer`:

```json
{"raw_text": "salma apa pach sho taka baki, dal r tel", "type": "credit", "amount": 500,
 "item": "dal, tel", "new_customer": {"name": "Salma", "note": "Mosque road"}}
```

It returns `201` with the saved `transaction` (including `raw_text` and the new balance), the
`customer`, and `customer_created`. A new customer and its transaction are saved in one
commit: if the name clashes with an existing customer (409), nothing is saved.

**Errors**: `422` the sentence has no name/amount, or invalid input; `502` the model gave an
invalid answer twice; `503` no `GROQ_API_KEY`, or Groq is unreachable / rejected the
request (details are logged, not returned).

### Swapping the LLM provider

Everything outside `app/llm/` depends only on the `LLMClient` interface in
`app/llm/base.py`: one method, `complete_json(messages) -> str`. To use another provider,
add a class with that method and return it from `build_llm_client()` in
`app/llm/__init__.py`.

### Evaluation sentences

`backend/tests/fixtures/eval_sentences.json` holds 20 varied sentences (Banglish, Bangla
script, English, mixed; credit and payment; number words, Bangla digits, honorifics, several
items) with the expected output. The test suite checks that the file is well formed and that
the deterministic steps agree with it. The plan is to grow it and add a script that runs it
against the real model to measure accuracy.

## Running the tests

```bash
cd backend
pytest
```

The tests never call Groq and need no API key: the LLM is replaced by a fake that returns
scripted answers (`FakeLLM` in `tests/conftest.py`).

By default the tests use a fresh in-memory SQLite database for each test. To run the same suite
against PostgreSQL, point `TEST_DATABASE_URL` at a **throwaway** database (its tables are dropped):

```bash
TEST_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/baki_test pytest
```

## Next steps (not built yet)

- Alembic migrations (tables are currently created with `create_all` on startup)
- Authentication: one login per shop, and taking `shop_id` from the token instead of the URL
- Pagination for long customer ledgers
- Voice input (speech-to-text in front of `/parse`)
- An accuracy script that runs `eval_sentences.json` against the real model
- Store the AI's original parse next to the confirmed values, to measure how often shopkeepers correct it
- Mobile frontend
