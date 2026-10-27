# Baki Khata AI

A mobile-first app for small shopkeepers in Bangladesh and India to track customer
credit (*baki*) by typing or speaking Banglish instead of writing in a paper ledger.

This repository contains:

- a **backend**: a REST API built with FastAPI, SQLAlchemy and Pydantic, plus an **AI parsing
  layer** that turns one free-form sentence ("rahim bhai 2 kg chal 120 taka baki") into a
  transaction preview;
- a **frontend**: a mobile-first React app with one screen. Type or speak a sentence, check
  the confirmation card, save.

## How it works

The whole app is one screen, made for a busy shopkeeper on a cheap Android phone.

1. **Write.** A big box asks *"Ki hisab likhben?"* ("What do you want to note?"). The
   shopkeeper types one sentence the way they'd say it: `salma apa pach sho taka baki, dal r tel`.
   Next to the box is a big **mic button**: hold it, speak, release, and the words appear in the
   box to check and fix before going on (see [Voice input](#voice-input)). Below the box are the
   shop's last 10 entries.
2. **Check.** After *Hisab korun*, a loading message shows while the backend reads the
   sentence (`POST /shops/{id}/parse`, which saves nothing). Then a **confirmation card**
   shows what it understood: the amount in big type (৳500), whether it's **Baki** (red/orange:
   the customer took goods on credit) or **Joma** (green: the customer paid), the item, and the
   customer:
   - **matched**: the customer's name and current balance ("Ekhon: Baki ৳200");
   - **two or more fit** (e.g. two Rahims): each one as a big button with their area/note and
     balance, plus *Notun customer*. Saving waits until the shopkeeper picks one;
   - **new**: "Notun customer: Tanvir", so nobody is created by surprise.
3. **Fix (optional).** *Thik kore din* opens a form to correct the name, amount, type and item.
   Typing a name shows matching customers to pick from; any other name becomes a new customer.
4. **Save.** *Save korun* calls `POST /shops/{id}/parse/confirm`. A success message shows the
   customer's new balance and the entry appears at the top of the list. *Bad din* (cancel)
   goes back to the box with the sentence still there.

If something goes wrong (no internet, the AI is down or gives a bad answer, the sentence has no
name or amount) the app says so in plain words and opens the same form empty, so the shopkeeper
can still write the entry by hand. If the AI isn't sure (confidence below 0.6), its guess opens
in the form to be checked instead of in the confirmation card. The original sentence is always
saved as `raw_text`.

## Running it locally (macOS, step by step)

You need two terminal windows: one for the backend, one for the frontend. No API key is needed:
without one, the backend uses a simple rule-based parser instead of the AI (see
[Demo mode](#demo-mode-without-an-api-key)).

### 1. Install the tools (once)

1. Open **Terminal** (press ⌘ Space, type "Terminal", press Enter).
2. Install [Homebrew](https://brew.sh) if you don't have it: paste the command shown on
   brew.sh into Terminal and follow the instructions.
3. Install Python and Node.js:

   ```bash
   brew install python@3.13 node
   ```

4. Check that both work (any Python 3.11+ and Node 22.12+ is fine):

   ```bash
   python3 --version
   node --version
   ```

5. Get the code, if you haven't yet:

   ```bash
   git clone https://github.com/mrinaldas2514/baki-khata-ai.git
   cd baki-khata-ai
   ```

### 2. Start the backend (terminal window 1)

```bash
cd backend
python3 -m venv .venv                 # a private Python environment for this project (once)
source .venv/bin/activate             # run this every time you open a new terminal
pip install -r requirements-dev.txt   # once, and again when requirements change
cp .env.example .env                  # once; edit .env to add a GROQ_API_KEY if you have one
python -m app.seed                    # once: creates the demo shop, prints its id (1)
uvicorn app.main:app --reload
```

Leave this window open. The API runs at http://localhost:8000 (API docs at
http://localhost:8000/docs). Stop it with Ctrl+C.

### 3. Start the frontend (terminal window 2)

Open a new Terminal window (⌘ N), go to the project folder again, then:

```bash
cd frontend
npm install            # once, and again when package.json changes
cp .env.example .env   # once; VITE_SHOP_ID must match the id the seed script printed
npm run dev
```

Open http://localhost:5173 in your browser. To see it the way a phone does, open Chrome's
developer tools (⌥ ⌘ I) and switch on the device toolbar (⇧ ⌘ M).

Try:

- `salma apa pach sho taka baki, dal r tel`: matched customer
- `rahim 100 taka baki`: two Rahims, pick one
- `tanvir 90 taka baki`: new customer
- `মিজান কাকা ৩৫০ টাকার চিনি আর আটা নিল`: Bangla script
- `rina 2 ta saban`: no amount, so the manual form opens

**Start over with fresh demo data:** stop the backend, run `python -m app.seed --reset`, start it again.

**Try it on your phone:** connect the phone to the same Wi-Fi as the Mac and find the Mac's IP
address (System Settings → Wi-Fi → Details, e.g. `192.168.0.5`). Then:

1. In `backend/.env`, set `CORS_ORIGINS=http://localhost:5173,http://192.168.0.5:5173` and start
   the backend with `uvicorn app.main:app --reload --host 0.0.0.0`.
2. In `frontend/.env`, set `VITE_API_URL=http://192.168.0.5:8000` and start the frontend with
   `npm run dev -- --host`.
3. Open `http://192.168.0.5:5173` on the phone.

The mic won't work this way: browsers only allow the microphone on `https://` pages or
`localhost`, and the app says so when you press it. To try voice on the phone, either open
`chrome://flags/#unsafely-treat-insecure-origin-as-secure` in Chrome on the phone, add
`http://192.168.0.5:5173`, and restart Chrome; or serve the app over https (e.g. a tunnel such as
`cloudflared tunnel --url http://localhost:5173`, then add the tunnel's address to `CORS_ORIGINS`
and point `VITE_API_URL` at a tunnel to port 8000).

### Common problems

| You see | Fix |
|---|---|
| "Internet ba server-e somossa" | The backend isn't running, or `VITE_API_URL` in `frontend/.env` is wrong. Restart `npm run dev` after editing `.env`. |
| "Dokan pawa jayni" | No demo shop. Run `python -m app.seed` in `backend/` and check `VITE_SHOP_ID`. |
| A CORS error in the browser console | Add the address in the browser's address bar to `CORS_ORIGINS` in `backend/.env` (no trailing `/`) and restart the backend. |
| `command not found: uvicorn` | Run `source .venv/bin/activate` in `backend/` first. |
| No mic button | The browser has no speech recognition (Firefox) and the backend has no `GROQ_API_KEY`. Use Chrome or Edge, or add a key. |
| "Mic chalu korar onumoti nei" | The browser blocked the microphone. Click the icon left of the address bar and allow the microphone, then reload. |
| "Ei address-e browser mic chalu korte dey na" | The page isn't on `https://` or `localhost` (see *Try it on your phone*). |
| "Internet-e somossa, tai voice kaj korche na" | Chrome's speech recognition runs on Google's servers and needs internet. Brave blocks it: turn on *Server diye shunun* in the voice settings (needs a key). |

## Project structure

```
backend/
├── app/
│   ├── main.py          # FastAPI app factory, routers, error handlers
│   ├── config.py        # Settings from environment variables / .env
│   ├── database.py      # Engine + per-request session
│   ├── time_utils.py    # UTC / shop-local-time helpers
│   ├── llm/             # LLM interface, Groq client, rule-based demo parser
│   ├── stt/             # speech-to-text interface and the Groq Whisper client
│   ├── models/          # SQLAlchemy tables: Shop, Customer, Transaction
│   ├── schemas/         # Pydantic request/response models and validation
│   ├── routers/         # HTTP endpoints (thin, just call services)
│   └── services/        # Business logic (balance, customers, transactions, dashboard,
│                        #   parsing, parse_prompt, number_words, name_matching, transcription)
├── tests/               # pytest suite (the LLM and speech-to-text are always faked)
│   └── fixtures/eval_sentences.json   # example sentences + expected output
├── app/seed.py          # demo shop: python -m app.seed
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml       # pytest config
└── .env.example
frontend/                # React + Vite + TypeScript + Tailwind
├── src/
│   ├── App.tsx          # the one screen and its steps (entry → confirm/edit → saved)
│   ├── strings.ts       # every UI text, in Banglish (add a Bangla/English set here later)
│   ├── config.ts        # VITE_API_URL, VITE_SHOP_ID
│   ├── api/             # fetch client and the backend's JSON types
│   ├── components/      # SmartEntry, MicButton, ConfirmationCard, EntryForm, RecentTransactions...
│   ├── voice/           # speech engines (browser / server), useVoiceInput, voice settings
│   └── test/            # test setup, the fetch mock and the speech API mocks
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
| GET | `/shops/{shop_id}/transactions?limit=10` | The shop's latest transactions (all customers), newest first, with customer name and note |
| GET | `/shops/{shop_id}/transactions/{transaction_id}` | Get one transaction |
| PATCH | `/shops/{shop_id}/transactions/{transaction_id}` | Edit a transaction (only the fields you send) |
| DELETE | `/shops/{shop_id}/transactions/{transaction_id}` | Delete a transaction (204) |
| GET | `/shops/{shop_id}/dashboard?overdue_days=30` | Total outstanding, today's collection, top 5, overdue customers |
| POST | `/shops/{shop_id}/parse` | Turn one free-form sentence into a transaction **preview** (saves nothing) |
| POST | `/shops/{shop_id}/parse/confirm` | Save the confirmed preview, creating the customer if new |
| POST | `/transcribe` | A short voice recording (multipart `file`, optional `language`) → `{"text": "..."}` (saves nothing) |
| GET | `/transcribe/status` | Whether server-side transcription is set up, and its size/length limits |

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

Step-by-step instructions for macOS are in [Running it locally](#running-it-locally-macos-step-by-step).
In short, with Python 3.11+ (developed on 3.13):

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
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated browser origins allowed to call the API (the frontend) |
| `LLM_PROVIDER` | `auto` | `auto`: Groq when `GROQ_API_KEY` is set, otherwise the rule-based demo parser. `groq`: always Groq (503 without a key). `fake`: always the demo parser |
| `GROQ_API_KEY` | *(empty)* | Groq API key for AI parsing |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq chat model; must support JSON mode |
| `LLM_TIMEOUT_SECONDS` | `20` | How long to wait for the model (also used for transcription) |
| `GROQ_STT_MODEL` | `whisper-large-v3` | Groq speech-to-text model for `POST /transcribe` (`whisper-large-v3-turbo` is faster and cheaper, a little weaker on Bangla) |
| `STT_MAX_AUDIO_BYTES` | `1000000` | Largest recording `POST /transcribe` accepts (413 above it) |
| `STT_MAX_AUDIO_SECONDS` | `30` | Longest recording; the app stops recording at this point too |

### Switching to PostgreSQL

No code changes are needed:

```bash
pip install "psycopg[binary]"
# in .env
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/baki_khata
```

### Frontend configuration

From `frontend/.env` (see `frontend/.env.example`). Vite reads it when `npm run dev` starts.

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | Where the backend runs |
| `VITE_SHOP_ID` | `1` | The shop to use (there's no login yet) |

### Demo mode without an API key

With `LLM_PROVIDER=fake`, or `auto` and no `GROQ_API_KEY`, `/parse` uses a small rule-based
parser (`app/llm/rule_based.py`) instead of the AI. It plugs in behind the same `LLMClient`
interface, so number normalization, validation, the sanity check and customer name matching all
run exactly as with the real model. It's good enough to demo the app (it gets the 20 evaluation
sentences right): the name is the first word, the amount is the number next to "taka" (or the
one that isn't a quantity like "2 kg"), and the type comes from words like baki/nilo vs.
dilo/joma/shodh. Anything less regular needs the real model; the backend logs a warning at the
first parse so it's clear which one is running.

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

## Voice input

A busy shopkeeper can speak instead of typing. Speaking only fills the text box: the words then
go through exactly the same steps as typed text (*Hisab korun* → `POST /parse` → confirmation
card → `POST /parse/confirm`). Nothing is saved from voice without the same check.

**Using it**

- **Hold to talk**: press and hold the mic, speak, let go. Releasing stops listening.
- **Tap to talk** (easier for some, and how keyboards and screen readers work it): tap once to
  start, tap again to stop. Enter or Space on the focused button does the same.
- The button shows what's happening: **Bolun** (idle), red and pulsing **Shunchi** (listening),
  a spinner **Lekha...** (turning speech into text), amber with a message (something went wrong).
- The words appear in the box (live while speaking, with browser recognition). Fix anything
  wrong, then press *Hisab korun*. Recording stops by itself after 30 seconds.
- **Voice settings** (under the box): the language to listen for, *Bangla (Bangladesh)*
  (`bn-BD`, the default), *Bangla (India)* (`bn-IN`) or *English / Banglish (India)* (`en-IN`);
  **auto-submit**, which sends the sentence on as soon as speaking ends (the confirmation card
  still comes before saving); and, when both engines are available, *Server diye shunun* to
  prefer the server. Settings are remembered on the phone (`localStorage`); if storage is
  blocked (private mode) they still apply until the page is closed.
- Problems get a plain message and typing always still works: microphone permission denied,
  no microphone, nothing heard, no internet, a language the browser can't do, a recording that's
  too long, or a server without speech-to-text.

Which language to pick: with `bn-BD`/`bn-IN` the words come back in Bangla script
(`রহিম ভাই ১২০ টাকা বাকি`); with `en-IN` they come back in Latin letters (`rahim bhai 120 taka
baki`), which suits shopkeepers who speak a lot of English words. The parser handles both.

**Two engines**

| | Browser speech recognition (default) | Server: Groq Whisper (`POST /transcribe`) |
|---|---|---|
| How | The browser's Web Speech API | The app records with `MediaRecorder` (Opus, ~32 kbit/s, about 120 KB for 30 s) and uploads it |
| Cost | Free | Groq's speech-to-text pricing; needs `GROQ_API_KEY` |
| Speed | Instant, words appear while speaking | A second or two after letting go |
| Accuracy | Good for plain Bangla or English; weaker on mixed Banglish, names and numbers | Better on mixed Banglish, names and amounts; it's also given a typical shop sentence as a hint |
| Privacy | Audio goes to the browser maker (Google for Chrome) | Audio goes to your backend, then Groq |
| Works in | Chrome, Edge, Samsung Internet (Android and desktop), Safari 14.1+ with Siri enabled; needs internet | Every modern browser, including Firefox and Safari |

The app uses the browser engine when the browser has one, and the server when it doesn't (or when
*Server diye shunun* is on). With no key, `POST /transcribe` returns **503**, `GET
/transcribe/status` says `"available": false`, and the app hides the server option; on a browser
without speech recognition (Firefox) the mic button is then hidden and the app works by typing.

**Browser support**

| Browser | Voice input |
|---|---|
| Chrome / Edge / Samsung Internet (Android, desktop) | Browser recognition (or the server, if chosen) |
| Safari (iPhone, Mac) | Browser recognition when Siri / Dictation is on; otherwise the server |
| Firefox | Server only (no Web Speech recognition) |
| Brave | Has the API but blocks it ("Internet-e somossa"): turn on *Server diye shunun* |
| Any browser on `http://` other than `localhost` | Blocked by the browser: the mic needs `https://` |

**`POST /transcribe`** (multipart form)

```bash
curl -X POST localhost:8000/transcribe -F "file=@voice.webm;type=audio/webm" -F language=bn-BD
# {"text": "রহিম ভাই ২ কেজি চাল ১২০ টাকা বাকি"}
```

- `file`: webm, ogg, mp4/m4a, mp3, wav or flac (`415` otherwise). At most `STT_MAX_AUDIO_BYTES`
  (`413`); empty is `422`.
- `language`: `bn-BD`, `bn-IN`, `en-IN` (or just `bn`/`en`); leave out to auto-detect. Other
  values are `422`.
- Length: the app stops recording at `STT_MAX_AUDIO_SECONDS`. The server checks the length
  Whisper reports and answers `413` above it (with 1.5 s of slack). It can't check before
  transcribing: Chrome writes WebM without a duration header, so the size limit is what keeps
  uploads small. Starlette receives the whole upload before the size check, so in production also
  cap the request body at the proxy (e.g. nginx `client_max_body_size 2m`).
- `text` is empty when nobody spoke: segments Whisper itself marks as silence are dropped, since
  otherwise it tends to invent text such as "Thank you." for silence.
- `502` when Groq fails (details are logged, not returned), `503` without a key.

Everything outside `app/stt/` depends only on the `SpeechToTextClient` interface in
`app/stt/base.py` (`transcribe(audio, filename, language) -> Transcript`), the same way the LLM is
swapped: add a class and return it from `build_stt_client()` in `app/stt/__init__.py`.

## AI parsing

A shopkeeper types or speaks one sentence in Banglish, Bangla script, English or a
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
invalid answer twice; `503` `LLM_PROVIDER=groq` without a `GROQ_API_KEY`, or Groq is
unreachable / rejected the request (details are logged, not returned).

### Swapping the LLM provider

Everything outside `app/llm/` depends only on the `LLMClient` interface in
`app/llm/base.py`: one method, `complete_json(messages) -> str`. To use another provider,
add a class with that method and return it from `build_llm_client()` in
`app/llm/__init__.py` (that's how the rule-based demo parser plugs in too).

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

```bash
cd frontend
npm test            # Vitest + React Testing Library (npm run test:watch to re-run on save)
npm run typecheck   # TypeScript
npm run lint        # oxlint
npm run format      # Prettier
```

The frontend tests drive the real screen with the backend mocked (`src/test/mockApi.ts`
replaces `fetch`): the confirmation card for a matched, fuzzy, ambiguous and new customer, edit
mode, saving, and every error falling back to manual entry. The voice tests
(`src/VoiceInput.test.tsx`) replace the speech APIs (`src/test/mockSpeech.ts`: a fake
`SpeechRecognition`, `MediaRecorder` and microphone) and cover the mic button's states, hold vs.
tap vs. keyboard, the transcript going through the normal flow, auto-submit, saved settings,
permission denied and the other errors, and the server fallback.

The tests never call Groq and need no API key: the LLM and speech-to-text are replaced by fakes
that return scripted answers (`FakeLLM` and `FakeSTT` in `tests/conftest.py`).

By default the tests use a fresh in-memory SQLite database for each test. To run the same suite
against PostgreSQL, point `TEST_DATABASE_URL` at a **throwaway** database (its tables are dropped):

```bash
TEST_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/baki_test pytest
```

## Next steps (not built yet)

- Alembic migrations (tables are currently created with `create_all` on startup)
- Authentication: one login per shop, and taking `shop_id` from the token instead of the URL
- Pagination for long customer ledgers
- Measure voice accuracy: a few recorded Banglish sentences run through both engines and
  `/parse`, to choose the default engine and Whisper model with numbers
- A Bangla-script / English switch for the UI (all texts are in `frontend/src/strings.ts`)
- An accuracy script that runs `eval_sentences.json` against the real model
- Store the AI's original parse next to the confirmed values, to measure how often shopkeepers correct it
- Customer list and per-customer ledger screens in the frontend
- Offline support (queue entries while the phone has no internet)
