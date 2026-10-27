# Baki Khata AI

A mobile-first app for small shopkeepers in Bangladesh and India to track customer
credit (*baki*) by typing or speaking Banglish instead of writing in a paper ledger.

This repository currently contains the **backend foundation**: a REST API built with
FastAPI, SQLAlchemy and Pydantic. There's no AI and no frontend yet.

## Project structure

```
backend/
├── app/
│   ├── main.py          # FastAPI app factory, routers, error handlers
│   ├── config.py        # Settings from environment variables / .env
│   ├── database.py      # Engine + per-request session
│   ├── time_utils.py    # UTC / shop-local-time helpers
│   ├── models/          # SQLAlchemy tables: Shop, Customer, Transaction
│   ├── schemas/         # Pydantic request/response models and validation
│   ├── routers/         # HTTP endpoints (thin, just call services)
│   └── services/        # Business logic (balance, customers, transactions, dashboard)
├── tests/               # pytest suite
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

### Switching to PostgreSQL

No code changes are needed:

```bash
pip install "psycopg[binary]"
# in .env
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/baki_khata
```

## Running the tests

```bash
cd backend
pytest
```

By default the tests use a fresh in-memory SQLite database for each test. To run the same suite
against PostgreSQL, point `TEST_DATABASE_URL` at a **throwaway** database (its tables are dropped):

```bash
TEST_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/baki_test pytest
```

## Next steps (not built yet)

- Alembic migrations (tables are currently created with `create_all` on startup)
- Authentication: one login per shop, and taking `shop_id` from the token instead of the URL
- Pagination for long customer ledgers
- Banglish text and voice parsing (the AI layer) that turns `raw_text` into transactions
- Mobile frontend
