# Baki Khata AI

[![CI](https://github.com/mrinaldas2514/baki-khata-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/mrinaldas2514/baki-khata-ai/actions/workflows/ci.yml)

**One sentence instead of a ledger page.** A shopkeeper types or says
*"salma apa pach sho taka baki, dal r tel"*, checks a big confirmation card, and the credit is in
the customer's khata, with the balance, reminders and a dashboard worked out for them.

## The problem

Millions of small shops in Bangladesh and India still keep customer credit (*baki*) in a paper
*khata*: one page per customer, every entry by hand, balances added up in the head. Paper gets
lost or wet, can't send a reminder, and a dispute is word against word. Existing ledger apps
digitize the page but not the work: they want the shopkeeper to pick a customer from a list, type
an amount into a number field, choose credit or payment and type the goods, which is four or five
taps and fields per entry, at a busy counter, often on a cheap phone with a weak connection. Baki
Khata AI keeps the shopkeeper's own habit instead: say or type the entry the way you'd say it, in
Banglish, Bangla script or English, and the app turns it into a structured entry to confirm.

## Key features

- **One-sentence entries, typed or spoken**: an LLM (Groq, `openai/gpt-oss-120b`) reads
  Banglish/Bangla/English and code-mixed sentences, spoken number words (*pach sho, dedh hajar,
  sowa sho*), Bangla digits and several customers in one sentence; spoken amounts are normalized
  by rules before the model sees them.
- **Confirmation before saving**: a big card shows amount, Baki/Joma, item and customer, labelled
  **AI** or **AI chhara**, with fuzzy name matching that asks when two customers fit.
- **Works on weak or no internet**: installable PWA that opens offline; entries are read on the
  phone by the rule-based parser and kept with *Pending sync*, then sent in order with an
  idempotency key so nothing is saved twice.
- **Voice**: browser speech recognition, with a server-side Whisper fallback.
- **Khata, dashboard, reminders**: running balances, overdue (FIFO) baki, last 7 days, WhatsApp
  reminder text, CSV export, and how long an entry takes (*Gore ekta hisab: 8 second*).
- **Privacy**: consent at sign-up, an *AI bondho* (AI off) switch that keeps every sentence on
  the server, logs without names or amounts, account deletion.
- **Measured**: an evaluation of 186 labelled sentences across 14 categories, for the rules and
  the LLM, with accuracy per field and category and p95 latency.
- **Deploy-ready**: production mode that refuses unsafe settings, security headers, `/health`
  with a database check, Docker + compose, Render + Vercel config, CI on every push.

## Tech stack

| | |
|---|---|
| **Backend** | Python 3.13, FastAPI, SQLAlchemy 2, Alembic, Pydantic 2, PostgreSQL (SQLite for development), argon2id + JWT, Groq SDK (LLM + Whisper), RapidFuzz |
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS 4, Web Speech API / MediaRecorder, IndexedDB, a hand-written service worker |
| **Quality** | pytest (742 tests, SQLite and PostgreSQL), Vitest + Testing Library (428 tests), ruff, oxlint, Prettier, axe-core audits, an LLM evaluation harness |
| **Delivery** | Docker, docker compose, GitHub Actions, Render (API + PostgreSQL), Vercel (static PWA) |

## Architecture

```mermaid
flowchart LR
    subgraph Phone["Shopkeeper's phone (PWA)"]
        UI["React app<br/>Hisab · Customer · Dashboard"]
        SW["Service worker<br/>app shell cache"]
        Rules["Rule parser (TS port)<br/>+ cached customers"]
        Queue[("IndexedDB<br/>offline queue")]
        UI -- offline --> Rules
        UI -- save offline --> Queue
        SW -. serves .-> UI
    end

    subgraph API["FastAPI backend"]
        Parse["/parse<br/>numbers → LLM or rules → validate → match names"]
        Confirm["/parse/confirm(-many)<br/>Idempotency-Key"]
        Ledger["customers · transactions<br/>dashboard · reminders · export"]
        Auth["auth · ownership · rate limits"]
    end

    DB[("PostgreSQL")]
    Groq["Groq<br/>gpt-oss-120b · Whisper"]

    UI -- "HTTPS + JWT" --> Parse
    UI --> Confirm
    Queue -- "sync, same key" --> Confirm
    UI --> Ledger
    Parse -- "AI on" --> Groq
    Parse --> DB
    Confirm --> DB
    Ledger --> DB
    Auth --> DB
```

The sentence is never saved from the model directly: `/parse` returns a preview (nothing saved),
the shopkeeper confirms or fixes it, and `/parse/confirm` saves it with the original sentence.

## Evaluation results

`python -m eval.run_eval --parser both` (in `backend/`) runs 186 labelled sentences in 14
categories through the same steps as `/parse` (see [Accuracy evaluation](#accuracy-evaluation)).
A sentence counts as right only if every entry has the right name, amount, type and item.
Results of a local run on 2026-10-29, the LLM on Groq's free tier:

| Metric | Rule-based parser (AI off) | LLM (`openai/gpt-oss-120b` on Groq) |
|---|---|---|
| **All fields correct, per sentence** | **90.3%** (168/186) | **96.8%** (180/186) |
| Customer name | 97.7% | 100.0% |
| Amount | 97.7% | 99.4% |
| Type (baki / joma) | 95.5% | 99.4% |
| Item | 90.9% | 97.7% |
| Non-transactions refused | 87.5% (21/24) | 100.0% (24/24) |
| Latency per sentence, average / p95 | 0.0 ms / 0.1 ms | 670 ms / 1025 ms |

Sentence by sentence, the LLM gets **17** right that the rules miss, and the rules get **5** right
that the LLM misses.

**The set is synthetic**: the sentences were written to cover the categories above, not
collected from shops. Real shopkeeper sentences (typed and spoken, `backend/eval/my_sentences.csv`)
are the next step, and the numbers may well drop on them.

Where the rules fall short (full list in
[`backend/eval/results/2026-10-28_rules_rule-based.md`](backend/eval/results/2026-10-28_rules_rule-based.md)):
typos in keywords (*dlo*, *jma*, *shod*: 60%), several customers without commas
(*"Hasan paid 500 and Rina took 200"*: 75% for multi-entry), verbs it doesn't know (*diye gelo*),
and sentences with a number that aren't transactions (*"chal er dam 70 taka kg"*). Those are what
the LLM is for, at the cost of ~0.7 s and a network call per sentence. The rules stay as the
fallback: with AI off, offline, and when the AI is rate limited or slow (see
[Rate limits](#rate-limits)).

## Design decisions and trade-offs

- **Confirmation before every save.** The AI only proposes; the shopkeeper sees the amount in
  big type and the customer before anything is written, and low-confidence readings open the
  edit form instead. It costs one tap per entry, but a wrong baki in someone's khata costs trust,
  and AI mistakes on names and amounts are the expensive kind.
- **Fuzzy name matching, with "ambiguous" as an answer.** Names are matched without the AI:
  honorifics dropped, Bangla romanized, Banglish spelling ironed out (Rohim = Rahim = রহিম). When
  two customers fit (two Rahims), the app asks rather than guessing; when nobody fits it says
  *Notun customer*, so nobody is created by surprise. The price is an extra tap on look-alikes.
- **AI-off privacy mode.** *AI bondho rakhun* sends nothing to the AI provider: the server's
  rule-based parser reads the sentences instead (90% of the evaluation set) and voice falls back
  to the browser. Shopkeepers who don't want their customers' names leaving the shop can still
  use the app, with lower accuracy on messy sentences, and the card says **AI chhara** so it's
  never a surprise.
- **Browser speech first, Whisper as fallback.** The Web Speech API is free, instant and shows
  words while speaking, but is weaker on mixed Banglish and absent in Firefox; Groq Whisper is
  better on names and amounts but costs money and a round trip. The app uses the browser when it
  can and the server when it must (or when chosen), and either way the words go into the box to
  check, never straight to save.
- **An offline queue with idempotency keys.** Shops have bad connections, so an entry must
  never be lost or doubled. Offline, the sentence is read on the phone by a TypeScript port of
  the rules (checked against the Python parser on 237 sentences) and kept in IndexedDB; every save
  carries a random key from the moment *Save* is pressed, and the server stores the answer with
  the entry in one commit, so a retry after a lost answer is a no-op. Trade-offs: offline
  readings are rules-only and balances shown offline are the last known ones.
- **Provider model retirement is a config change.** Groq retires models (the old default
  `llama-3.3-70b-versatile` went in 2026). The model is `GROQ_MODEL`; the backend checks it
  against Groq's model list at startup and logs exactly what to change, and everything outside
  `app/llm/` depends on a one-method `LLMClient` interface, so switching provider is one class.
- **Balances are never stored.** They're computed from the transactions (with a window function
  for running balances), so editing or deleting an entry can't leave a balance out of sync.

## Screenshots

*(Placeholders: add the images to `docs/screenshots/`.)*

| Hisab: one sentence | Confirmation card | Offline: Pending sync |
|---|---|---|
| ![Hisab](docs/screenshots/hisab.png) | ![Confirmation](docs/screenshots/confirm.png) | ![Offline](docs/screenshots/offline.png) |

| Customer khata | Dashboard | Settings (AI off) |
|---|---|---|
| ![Khata](docs/screenshots/khata.png) | ![Dashboard](docs/screenshots/dashboard.png) | ![Settings](docs/screenshots/settings.png) |

---

## What's in this repository

A mobile-first app for small shopkeepers in Bangladesh and India to track customer
credit (*baki*) by typing or speaking Banglish instead of writing in a paper ledger.

This repository contains:

- a **backend**: a REST API built with FastAPI, SQLAlchemy (with Alembic migrations) and
  Pydantic, plus an **AI parsing layer** that turns one free-form sentence ("rahim bhai 2 kg chal
  120 taka baki") into a transaction preview;
- a **frontend**: a mobile-first React app. Each shopkeeper has their own **account** (mobile
  number or email and password) and only ever sees their own shop. Three tabs: **Hisab** (type or
  speak a sentence, check the confirmation card, save), **Customer** (everyone's balance, and each
  customer's khata) and **Dashboard** (what's owed, today's money, old baki), plus **Settings**
  (turn the AI off, download everything as CSV, log out, delete the account).

**Demo login** (after `python -m app.seed`, see [Running it locally](#running-it-locally-macos-step-by-step),
or on a deployed demo with `SEED_DEMO_ON_START=true`): mobile **`01700000000`**, password **`demo1234`**.

## How it works

The app is made for a busy shopkeeper on a cheap Android phone (it's checked at 360 px wide).
The shopkeeper logs in once (it stays logged in for a week, see
[Accounts](#accounts-and-logging-in)). Three big tabs sit at the bottom, in thumb reach:
**Hisab**, **Customer** and **Dashboard**, and **Settings** is at the top right (see
[The screens](#the-screens)). The phone's back button works between them, because each screen
has its own address (`#/customers`, `#/customers/7`, `#/dashboard`, `#/settings`).

### Hisab: writing an entry

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
5. **Undo (10 seconds).** Under the success message, **↶ Bhul hoyeche? Undo (10)** counts down.
   Tapping it deletes what was just saved (and the customer, if the entry had just created
   them), and puts the sentence back in the box to fix and try again. After 10 seconds the button
   goes; an entry can still be fixed or deleted from the customer's khata.

**Several customers in one sentence.** `rahim 200 baki, karim 500 dilo, salma 100 baki` becomes
**three cards**, one per customer, each with its amount, Baki/Joma, item and customer (pick
between look-alikes on the card). Each card has *Thik kore din* (fix it in place) and *Bad din*
(drop it). **Sob save korun (3 ta)** saves them all together (`POST /parse/confirm-many`: all of
them or, if anything fails, none), then the same Undo removes them all. A sentence like
`salma apa pach sho taka baki, dal r tel` stays one entry: "dal r tel" is goods, not a customer.

**AI off.** With *AI bondho rakhun* switched on in Settings, the sentence is read on the server
by the simple rule-based parser (see [Demo mode](#demo-mode-without-an-api-key)) and nothing is
sent to the AI provider. A note above the box says so; when the parser can't read a sentence the
manual form opens as usual.

If something goes wrong (no internet, the AI is down or gives a bad answer, the sentence has no
name or amount) the app says so in plain words and opens the same form empty, so the shopkeeper
can still write the entry by hand. If the AI isn't sure (confidence below 0.6), its guess opens
in the form to be checked instead of in the confirmation card. The original sentence is always
saved as `raw_text`.

Tapping an entry in the list below the box opens that customer's khata.

### Weak or no internet (offline)

Shops often have a bad connection, so the app keeps working without one:

- **Installable, opens offline.** It's a PWA: Chrome offers *Install app* / *Add to Home
  screen* (manifest `frontend/public/manifest.webmanifest`, icons in `frontend/public/icons/`).
  A service worker (`frontend/pwa/sw.js`) keeps the app's own files on the phone, so it opens at
  once with good, weak or no internet. It never touches the API: answers with names and money
  are not cached (the API also says `Cache-Control: no-store`).
- **Online / Offline** in the title bar (and how many entries are still on the phone, e.g.
  *Offline · 2 ta pending*). Screen readers hear the change.
- **Writing an entry offline.** When the phone is offline (or `/parse` gets no answer at all),
  the sentence is read **on the phone** by the same rule-based parser as *AI bondho*, ported to
  TypeScript (`frontend/src/offline/rules.ts`), and matched against the shop's last customer list
  (kept on the phone). The card says **AI chhara** and *Internet nei, tai phone-ei pora hoyeche*;
  balances are the last known ones. If the rules can't read it, the manual form opens as usual.
- **Saved on the phone, sent later.** *Save korun* while offline (or when the save gets no
  answer) keeps the entry in IndexedDB: *📱 Phone-e save hoyeche*, and it appears above the
  recent list with **⏳ Pending sync**. It's sent by itself, **in the order written**, as soon as
  there is internet (when the phone comes back online, every 20 s while some wait, and at every
  start; *Ekhon pathan* sends now). It keeps the time it was written (`created_at`), so the khata
  shows when it really happened. Entries survive closing the app. *Undo* works on them too.
- **Never saved twice.** Every save carries a random **`Idempotency-Key`** from the moment
  *Save* is pressed, and every retry sends the same key. If a try did reach the server but its
  answer was lost, the server answers the stored result instead of saving it again (see
  [the API](#api)). A new customer written twice offline ("tanvir 50 baki", then "tanvir 20
  dilo") is created once: later entries go to the customer the first one created.
- **When the server refuses one** (say, a new customer whose name already exists), it's marked
  *⚠ Sync hoyni* with the reason and *Bad din* to drop it; the others go on. Logging out keeps
  waiting entries (Settings warns); deleting the account deletes them from the phone too.

**Try it in Chrome DevTools:** run the app (`npm run build && npm run preview`, or Docker: the
service worker only runs in a production build), log in once, then DevTools → **Network** →
throttling **Offline** (or **Application → Service workers → Offline**). Reload: the app opens.
Write `rahim 200 baki`, save: it shows *Pending sync*. Set **No throttling**: it's sent within
a moment and appears in the recent list. **Application → IndexedDB → baki-khata → queue** shows
what's waiting; **Slow 3G** shows the weak-connection behaviour.

### Accessibility

Checked on every screen (login, register, Hisab, the confirmation card for a matched, ambiguous
and new customer, edit form, several entries, customers, khata, dashboard, settings) at **360 px
wide** with [axe-core](https://github.com/dequelabs/axe-core) (WCAG 2.1 A/AA and best
practices) at **100%, 150% and 200% text size** (what Android's font-size setting does to the
page): no violations, and no sideways scrolling at any size.

- **Large text**: everything is sized in `rem`, so the phone's text size scales the whole app.
  Rows of buttons wrap one under the other when the text doesn't fit (Hisab korun + mic, Thik
  kore din + Bad din, Baki likhun + Joma likhun, the sort buttons), the bottom tabs' labels shrink
  a little and break as a last resort, and the chart's screen-reader table no longer widens the
  page.
- **The amount on the confirmation card** is as big as fits: up to 88 px (৳500, ৳1,500), smaller
  for long amounts (৳1,25,000) so it never runs past the card, bold, in red (Baki) or green
  (Joma) with the word next to it, so colour is never the only signal.
- **Visible focus**: keyboard focus always shows a dark ring with a yellow halo, visible on the
  white cards and on the green title bar.
- **Screen readers**: every input has a label, icon buttons have names, the mic button says what
  it's doing (`aria-pressed`, "Shunchi..."), the chart has a table version, status messages
  (saved, offline, sync) are live regions, and the AI / AI chhara label reads "Ke porlo: AI".
- **Contrast**: text meets AA (4.5:1) everywhere, placeholders included (`stone-500` on white).

## The screens

### Login and register

- **Login korun**: *Mobile number ba email* and *Password*, big boxes, and a **Dekhun / Lukan**
  button to show the password while typing it. The number can be typed any way
  (`01711-000001`, `+880 1711 000001`...). A wrong number or password gets one message for both
  (*Mobile number/email ba password thik nei*), so nobody can find out which numbers have an
  account.
- **Notun account khulun**: your name, the shop's name, a mobile number (Bangladesh or India; or
  an email instead), and a password of at least 8 characters. Below them is a short privacy note
  in Banglish (*Apnar hisab, apnar odhikar*, see [Privacy](#privacy)) with a box to tick:
  without the tick the account isn't made. Registering creates the shop and logs straight in.
- The app stays logged in across reloads and restarts of the phone's browser. When the login
  ends (after 7 days, after *Logout*, or when the server says the login is no longer valid) the
  login screen comes back with a message such as *Login-er shomoy shesh hoye geche. Abar login
  korun.*

### Settings

Opened with **Settings** at the top right.

- **Apnar account**: name, shop and mobile number.
- **AI bondho rakhun**: a switch. Off (default): sentences go to the AI for the best reading.
  On: nothing is sent to the AI provider (see [Privacy](#privacy)).
- **Data export (CSV)**: *Download korun* saves the whole khata as one file that opens in Excel.
- **Logout**.
- **Account muchhe din**: deletes the account, the shop and every customer and entry, after a
  confirmation that needs the password (*Na, rakhun* is the safe choice).

### Customer list

- Every customer with their current balance: **Baki ৳1,200** in red, **✓ Clear** in green (and
  **Agrim ৳200** in green for someone who paid ahead). Under the name: their area/note and how
  long the baki has been waiting ("35 din dhore baki").
- **Sort**: *Beshi baki* (biggest baki first, the default), *Purono baki* (the baki that has
  waited longest first, by the oldest still-unpaid credit) and *Naam*. Customers who owe nothing
  come last in both baki sorts.
- **Search** by name, area/note or phone. It works across scripts and Banglish spellings: `rahim`,
  `Rohim` and `রহিম` all find Rahim, `ayesha` finds আয়েশা (the same idea as the backend's name
  matching, in `frontend/src/customers.ts`). Search and sort are kept when you open a khata and
  come back.
- Tap a customer to open their khata.
- **+ Notun customer** adds someone before their first entry: name, mobile number (optional) and
  area/note. Then their (empty) khata opens.

### Customer khata

- At the top: the name, area/note, phone (tap to call) and the current balance in big type.
- **✎ Tottho bodlan** fixes the name, mobile number or area/note. Mobile numbers must be from
  Bangladesh (`01XXXXXXXXX`, `+880...`) or India (`+91...`); anything else gets *Bangladesh
  (01XXXXXXXXX ba +880) ba India (+91) mobile number likhun* before it's sent. They're saved in
  one form (`+8801711000001`) and shown the way people read them (`01711-000001`).
- **Baki likhun** / **Joma likhun** open a small form for this customer with the type already
  picked: amount, item, save.
- **Reminder pathan** (only when the customer owes something): see [Reminders](#reminders).
- **The full history**, newest first. Each entry shows the date, item, the original sentence the
  shopkeeper typed or spoke, the amount (Baki/Joma) and the balance right after it
  (*Tarpor: Baki ৳800*). It loads 20 at a time; **Aro dekhun** loads older ones.
- **Tap an entry** to fix its amount, type, item or **date** (*Kobe?*), or to delete it (*Muche
  felun*). The date can't be in the future; moving an entry to another day keeps its time of day.
  Deleting always asks first (*Ei hisab muche felben?*, with *Na, rakhun* as the safe default).
  After any change the balance and every running balance on screen are reloaded from the backend,
  so moving an old payment to an earlier date changes the running balances after it.
- *Baki likhun* / *Joma likhun* have the same date box, for an entry from yesterday.

### Dashboard

- Big numbers: **Mot baki** (total owed, and by how many customers), **Ajker joma** (payments
  today) and **Ajker notun baki** (new baki today).
- **Gore ekta hisab: 8.4 second**: how long writing one entry takes, the median of the last 50
  entries, from the first keystroke (or mic press) on the Hisab screen until it's saved. The app
  sends that number with the save (`timing: {duration_ms, input: "typed" | "voice"}` on
  `/parse/confirm` and `/parse/confirm-many`); the backend keeps only the number, typed/voice and
  how many entries were saved together, per shop (`entry_timings`), never the text. Clearing
  the box starts over; anything over an hour (the phone was put down) is ignored.
- **Shesh 7 din**: new baki (orange) and joma (green) per day for the last 7 days. Tap a day to
  read its numbers; screen readers get the same numbers as a table.
- **Shobcheye beshi baki**: the top 5 customers by baki.
- **30 diner beshi purono baki**: customers whose oldest unpaid baki is more than 30 days old,
  oldest first. Every customer in both lists opens their khata.

### Reminders

*Reminder pathan* on a khata asks the backend for a polite Banglish message with the customer's
name and baki:

```
Priyo Rahim,
Ashakori bhalo achen. Demo Dokan-e apnar 1,200 taka baki ache (12 September theke).
Shubidha moto shodh kore dile khub upokar hoy.
Dhonnobad,
Karim, Demo Dokan
```

The message can be changed in the box. **WhatsApp-e khulun** opens WhatsApp
(`https://wa.me/<number>?text=...`) with the message typed in; the shopkeeper checks it and
presses send. **The app never sends anything by itself.** If the customer has no phone number,
the reminder asks for it right there (*Phone number save korun*): it's checked, saved to the
customer and then *WhatsApp-e khulun* appears. *Message copy korun* always works too.

- The message comes from a fixed template, so it works without AI. When Groq is set up the AI
  may reword it to sound more natural, but its version is only used if it keeps the customer's
  name and exact amount and adds no numbers of its own; otherwise the template is used. With the
  rule-based demo parser there is no rewording.
- Phone numbers are saved with their country code (`+8801711000001`), so the WhatsApp number is
  just its digits. Numbers saved before that (without a country code) get `PHONE_COUNTRY_CODE`
  (`880` Bangladesh by default, `91` for India): `01711-000001` → `8801711000001`.

## Accounts and logging in

- **One shopkeeper, one shop.** Registering makes a user and their shop together; the user's
  name signs the WhatsApp reminders. Logging in works with the mobile number in any format
  (`01711-000001`, `+8801711000001`...) or the email.
- **Passwords** are stored only as **argon2id** hashes (`argon2-cffi`, RFC 9106's settings).
  A wrong login and an unknown account get the same answer and take the same time.
- **Login tokens** are JWTs (HS256) signed with `JWT_SECRET`, holding the user and shop ids and
  an expiry (**7 days** by default, `JWT_EXPIRE_MINUTES`): long enough that a shopkeeper isn't
  typing a password every morning, short enough that a lost phone's login ends on its own.
  *Logout* ends it at once: the token's id goes on a deny list (`revoked_tokens`) until it would
  have expired anyway. Deleting the account ends every login.
- **Every shop endpoint checks ownership**: `/shops/{id}/...` must be the logged-in user's shop,
  and each customer and transaction is looked up inside that shop. Anything else is `404`, the
  same as for something that doesn't exist, so nothing leaks (not even whether a shop id exists).
  `tests/test_ownership.py` tries every endpoint with another shopkeeper's ids.
- **In the app** the token and user are kept in `localStorage`, so a reload stays logged in. A
  `401` from the backend, or reaching the token's expiry time while the app is open, goes back to
  the login screen. *Trade-off:* `localStorage` can be read by script on the page, so an XSS bug
  would expose the token; an `HttpOnly` cookie would avoid that but needs CSRF protection and
  cookie settings that work across the two development ports. React escapes everything shown and
  the app has no `dangerouslySetInnerHTML`; a cookie is listed in [Next steps](#next-steps-not-built-yet).

## Privacy

Bangladesh's 2025 data protection rules ask for clear consent that can be withdrawn. The app:

- **Asks before anything is stored.** The registration screen shows a short Banglish note and
  can't continue without the tick:
  - entries (the typed or spoken sentence) are sent to an AI service (Groq) to understand them;
  - voice is sent to the server (and Groq) for transcription only when the browser can't do it;
  - the data is not sold, and not used for loans or credit;
  - AI can be turned off, everything downloaded, or the account deleted, any time in Settings.

  The backend refuses a registration without `consent: true` and the note's current version
  (`CONSENT_VERSION` in `backend/app/privacy.py`, `frontend/src/config.ts`), and stores the version
  and time with the user (`consent_version`, `consent_at`). Change the version when the note's
  meaning changes.
- **AI bondho rakhun** (Settings) withdraws the AI part: `/parse` uses the rule-based parser on
  the server, reminders use the fixed template, `/transcribe` refuses (`403`) and
  `/transcribe/status` says unavailable, so nothing reaches the AI provider. The browser's own
  speech recognition still works (Chrome sends that audio to Google, which the browser decides).
  Tests check that the fake LLM and speech-to-text are never called with AI off.
- **Data export (CSV)**: `GET /shops/{id}/export.csv`, one row per transaction (oldest first per
  customer) and one per customer without any: `customer_id, customer_name, phone, area_note,
  date` (shop's local time), `type` (Baki/Joma), `amount, item, original_sentence,
  balance_after`. UTF-8 **with a BOM**, so Excel shows Bangla correctly; cells starting with
  `= + - @` get a leading `'` so Excel won't run them as formulas.
- **Account muchhe din** deletes the user, the shop, every customer and every transaction (the
  database cascades from the shop), after the password is typed again.
- **Entry speed is numbers only**: how long an entry took, typed or spoken, and how many
  entries, per shop. No sentence or customer is attached; it's deleted with the account.
- **Logs carry ids, not people.** No sentence, name, phone number or amount is logged at INFO or
  above (e.g. *Saved 3 entries in shop 4*, *Registered user 7 with shop 7*); a model's broken
  answer is only logged at DEBUG. uvicorn's access log has its query strings cut off
  (`?search=rahim`). `tests/test_privacy.py` runs a whole parse/save/reminder flow and checks
  the logs.

## Rate limits

Too many requests in a short time get `429` with a `Retry-After` header and the Banglish
*Onek bar chesta hoyeche. 42 second por abar chesta korun.*, which the app shows as it is (and
voice says *Onek bar bola hoyeche...*).

| What | Default limit | Counted per |
|---|---|---|
| `POST /auth/login` | 10 a minute | client IP, and separately per account typed |
| `POST /auth/register` | 10 an hour | client IP |
| `POST /shops/{id}/parse` | 30 a minute | shop (each one may cost an AI call) |
| `POST /transcribe` | 15 a minute | shop |

The limiter (`app/rate_limit.py`) keeps counts in the server's memory: they're per process and
reset when it restarts. Behind a proxy, set `FORWARDED_ALLOW_IPS` so the real client IP is used
(the Render blueprint does); with several processes each counts on its own, so `start.sh` runs
one. For more, put limits in the proxy too (e.g. nginx `limit_req`). Change them with the
`RATE_LIMIT_*` settings.

**Groq's own limits.** Groq's free tier allows about 8,000 tokens a minute, which the
evaluation ran into (429s). When Groq answers `429` or doesn't answer within
`LLM_TIMEOUT_SECONDS`, `/parse` doesn't fail: that sentence is read by the rule-based parser,
the card says **AI chhara** (`"parser": "rules"`) and shows the note *AI ekhon byasto, tai AI
chhara pora hoyeche. Save korar age ekbar mile nin.* (`"notice"` in the answer). Other Groq
errors (bad key, retired model) are still a `503`, so a broken setup isn't hidden.

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
cp .env.example .env                  # once (see below for JWT_SECRET and GROQ_API_KEY)
alembic upgrade head                  # creates the database; run again after every git pull
python -m app.seed                    # once: the demo shop, and prints its login
uvicorn app.main:app --reload
```

`python -m app.seed` prints:

```
Created the demo shop 'Demo Dokan' with its customers and hisab.
Log in to the app with:
  Phone:    01700000000
  Password: demo1234
```

Leave this window open. The API runs at http://localhost:8000 (API docs at
http://localhost:8000/docs). Stop it with Ctrl+C.

**The login secret (`JWT_SECRET`).** Logins are signed with a secret from `backend/.env`. Make
one (once) and paste it after `JWT_SECRET=` in `backend/.env`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Without it the backend still runs in development, with a random secret it makes at each start:
everyone is logged out whenever the backend restarts (and with `--reload`, that's every time you
save a Python file). On a real server (`ENVIRONMENT=production`) it refuses to start without one.

#### The database, step by step (Alembic)

The tables are made by **migrations** (the files in `backend/migrations/versions/`), not by the
app. The backend refuses to start until the database is up to date and says so:

```
The database has no tables yet; this code needs migration 0002. Run `alembic upgrade head` in
backend/ (see README), then start the server again.
```

All commands run in `backend/` with the virtual environment on (`source .venv/bin/activate`):

| To... | Run |
|---|---|
| Create the database, or bring it up to date after `git pull` | `alembic upgrade head` |
| See which migration the database is at | `alembic current` |
| List every migration | `alembic history` |
| Start completely over with the demo data | stop the backend, `rm baki_khata.db`, `alembic upgrade head`, `python -m app.seed` |
| Go back one migration (rarely needed) | `alembic downgrade -1` |

The database is the one in `DATABASE_URL` (`backend/.env`); `sqlite:///./baki_khata.db` means the
file `backend/baki_khata.db`.

**Had the app running before accounts existed?** That database was made without migrations, so
`alembic upgrade head` fails with *table shops already exists*. If it only has demo data, delete
it and start over (row "Start completely over" above). To keep its data, run
`alembic stamp 0001` once (it marks the old tables as migration 0001), then
`alembic upgrade head`. Old shops have no login; add one by registering a new account in the app
(that makes a new, empty shop) or ask a developer to link the old shop to a user.

### 3. Start the frontend (terminal window 2)

Open a new Terminal window (⌘ N), go to the project folder again, then:

```bash
cd frontend
npm install            # once, and again when package.json changes
cp .env.example .env   # once
npm run dev
```

Open http://localhost:5173 in your browser and log in with the demo login (**01700000000** /
**demo1234**), or tap *Notun account khulun* to make your own shop. To see it the way a phone
does, open Chrome's developer tools (⌥ ⌘ I) and switch on the device toolbar (⇧ ⌘ M).

Try:

- `salma apa pach sho taka baki, dal r tel`: matched customer
- `rahim 100 taka baki`: two Rahims, pick one
- `tanvir 90 taka baki`: new customer
- `মিজান কাকা ৩৫০ টাকার চিনি আর আটা নিল`: Bangla script
- `rina 2 ta saban`: no amount, so the manual form opens
- `rahim 200 baki, jasim 500 dilo, tanvir 100 taka baki`: three cards; save all, then *Undo*
- the **Customer** tab: sort, search `রহিম` or `ayesha`, open Rahim (Bazar road) and send a reminder
- the **Dashboard** tab: Rahim and Jasim have baki older than 30 days
- **Settings**: switch *AI bondho rakhun* on and parse again; download the CSV and open it in
  Excel (Bangla names show correctly); log out and back in

**Start over with fresh demo data:** stop the backend, run `python -m app.seed --reset` (it
deletes the demo shop and everything in it, then makes it again), start it again.

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
| The backend stops at start with "The database has no tables yet" (or "is at migration ...") | Run `alembic upgrade head` in `backend/`, then start it again. |
| `alembic upgrade head` says *table shops already exists* | The database is from before migrations: see *Had the app running before accounts existed?* above. |
| "Mobile number/email ba password thik nei" with the demo login | The demo shop isn't there: run `python -m app.seed` in `backend/`. |
| Logged out every time the backend restarts | Set `JWT_SECRET` in `backend/.env` (see *The login secret* above). |
| "Onek bar chesta hoyeche. ... por abar chesta korun." | Too many tries in a short time (see [Rate limits](#rate-limits)). Wait, or restart the backend while developing. |
| "Dokan pawa jayni" | The saved login is for a shop that no longer exists (e.g. after `--reset`). Log out (Settings) and log in again. |
| A CORS error in the browser console | Add the address in the browser's address bar to `CORS_ORIGINS` in `backend/.env` (no trailing `/`) and restart the backend. |
| `command not found: uvicorn` | Run `source .venv/bin/activate` in `backend/` first. |
| No mic button | The browser has no speech recognition (Firefox) and the backend has no `GROQ_API_KEY`. Use Chrome or Edge, or add a key. |
| "Mic chalu korar onumoti nei" | The browser blocked the microphone. Click the icon left of the address bar and allow the microphone, then reload. |
| "Ei address-e browser mic chalu korte dey na" | The page isn't on `https://` or `localhost` (see *Try it on your phone*). |
| "Internet-e somossa, tai voice kaj korche na" | Chrome's speech recognition runs on Google's servers and needs internet. Brave blocks it: turn on *Server diye shunun* in the voice settings (needs a key). |

## Running it with Docker

Everything (PostgreSQL, the API and the frontend) with one command, from the repository root.
You need [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine
with the compose plugin):

```bash
docker compose up --build
```

Then open **http://localhost:8080**. For the demo login (**01700000000** / **demo1234**), in a
second terminal:

```bash
docker compose exec backend python -m app.seed
```

- **db**: PostgreSQL 16; its data stays in the `pgdata` volume between runs.
- **backend**: `backend/Dockerfile`, on http://localhost:8000. It runs in production mode and
  **migrates the database at every start** (`start.sh`: `alembic upgrade head`, then uvicorn),
  so it's the same as on a server. It waits until PostgreSQL is ready.
- **frontend**: `frontend/Dockerfile`, the built app served by nginx (non-root, port 8080) with
  the same caching and security headers as on Vercel (`frontend/docker/nginx.conf.template`).

Settings go in a `.env` file next to `docker-compose.yml` (it's git-ignored), for example:

```bash
JWT_SECRET=paste-a-long-random-value-here   # python3 -c "import secrets; print(secrets.token_urlsafe(48))"
GROQ_API_KEY=gsk_...                        # optional: AI parsing
```

Without `JWT_SECRET` compose uses a fixed one that is only fit for trying it on your own
computer. Stop with Ctrl+C; `docker compose down -v` also deletes the database.

## Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request (the badge at the top):

| Job | What it checks |
|---|---|
| **Backend (sqlite)** | `ruff check`, `ruff format --check`, the whole test suite on SQLite, and the evaluation with the rule-based parser |
| **Backend (postgresql)** | the migrations on PostgreSQL (`alembic upgrade head`, `alembic check`: they build exactly the models' schema, `downgrade base`), then the whole test suite on PostgreSQL |
| **Frontend** | `oxlint`, Prettier, the TypeScript type-check, the Vitest tests and the production build |
| **Docker compose** | builds both images, starts PostgreSQL, the API and the frontend, and checks `/health` (database included) and that the frontend serves the app |

pip and npm downloads are cached between runs (keyed on the requirements files and
`package-lock.json`). Groq is never called: the tests use fakes.

## Deploying (Render + Vercel)

The backend and its PostgreSQL database run on [Render](https://render.com) (`render.yaml`, a
"blueprint"); the frontend is a static site on [Vercel](https://vercel.com)
(`frontend/vercel.json`). Both have free plans. **First time? Follow [DEPLOY.md](DEPLOY.md)**:
click by click, every variable, free-plan limits and troubleshooting. Below is the summary.

### 1. Backend and database on Render

1. Push this repository to GitHub. In Render: **New → Blueprint**, pick the repository. Render
   reads `render.yaml` and proposes a web service `baki-khata-api` and a database
   `baki-khata-db` (Singapore, the region closest to Bangladesh and India).
2. It asks for the two values that aren't in the file: `CORS_ORIGINS` (put a placeholder like
   `https://example.com` for now, fixed in step 3) and `GROQ_API_KEY` (optional).
3. **Apply.** Every deploy runs `backend/start.sh`: `alembic upgrade head` first, then uvicorn.
   A failed migration stops the deploy instead of starting on a half-migrated database. Render
   checks `GET /health`, which also checks the database.
4. Open `https://baki-khata-api.onrender.com/health`: `{"status": "ok", "database": "ok"}`.
5. Demo data: the blueprint sets `SEED_DEMO_ON_START=true`, so the demo login exists after the
   first start (free web services have no **Shell** tab to run `python -m app.seed`). Set it to
   `false` for a real shop.

Environment variables of the **web service** (all set by the blueprint except where noted):

| Variable | Value | Notes |
|---|---|---|
| `ENVIRONMENT` | `production` | Refuses to start without a safe `JWT_SECRET`, a PostgreSQL `DATABASE_URL` and an https `CORS_ORIGINS`, and lists what's missing. Turns off `/docs`, adds HSTS. |
| `DATABASE_URL` | from the database | Render's `postgresql://...` URL works as it is (the backend adds the psycopg driver). |
| `JWT_SECRET` | generated by Render | 256 random bits, made once. Changing it logs everyone out. |
| `CORS_ORIGINS` | **you set it**: the Vercel address, e.g. `https://baki-khata.vercel.app` | Exact origins, comma-separated, `https://` only, no `*`, no trailing `/`. |
| `GROQ_API_KEY` | **you set it** (optional) | Without it the parser is the rule-based one, and the app says "AI chhara". |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Change here if Groq retires the model (the backend logs it at startup). |
| `APP_TIMEZONE` | `Asia/Dhaka` | `Asia/Kolkata` for India. |
| `FORWARDED_ALLOW_IPS` | `*` | Render's proxy is in front, so the rate limits use the client IP it forwards. |
| `SEED_DEMO_ON_START` | `true` | Creates the demo login at startup if it's missing. `false` for a real shop. |
| `PYTHON_VERSION` | `3.13` | |
| `PORT` | set by Render | `start.sh` listens on it. |

Any other setting from [Configuration](#configuration) can be added the same way (e.g.
`RATE_LIMIT_PARSE_PER_MINUTE`, `MAX_REQUEST_BYTES`, `PHONE_COUNTRY_CODE=91`).

Free-plan notes: the web service sleeps after 15 minutes without requests (the first request
then takes ~30-60 s; the app's offline queue covers it), and Render's free PostgreSQL databases
expire after a few weeks unless upgraded. Run **one** instance: the rate limits are counted in
memory per process.

### 2. Frontend on Vercel

1. In Vercel: **Add New → Project**, import the repository, and set **Root Directory** to
   `frontend`. The framework (Vite), build command and output folder come from
   `frontend/vercel.json`.
2. Add the environment variable below, then **Deploy**.
3. Copy the site's address (e.g. `https://baki-khata.vercel.app`) into `CORS_ORIGINS` on Render
   (step 1.2) and let Render redeploy.

| Variable | Value | Notes |
|---|---|---|
| `VITE_API_URL` | `https://baki-khata-api.onrender.com` | The backend's address, no trailing `/`. Read at **build** time: redeploy after changing it. |
| `VITE_SHOW_DEMO_LOGIN` | `true` (demo site only) | Shows the demo login on the login screen. Build time too. |

`vercel.json` sends every path to `index.html` (the app's own routing), caches `/assets/*`
forever (their names change with every build), never caches the service worker (`/sw.js`), and
adds security headers: a Content-Security-Policy that only lets the page load its own files and
talk to `https://` servers, no framing, `nosniff`, and the microphone only for the app itself.

### What production mode changes in the backend

- **Refuses unsafe settings** at startup, listing all of them (see `ENVIRONMENT` above).
- **Strict CORS**: only the origins in `CORS_ORIGINS`; only `GET POST PATCH DELETE` and the
  headers the app sends (`Authorization`, `Content-Type`, `Idempotency-Key`).
- **Security headers** on every answer: `X-Content-Type-Options: nosniff`, `X-Frame-Options:
  DENY`, `Referrer-Policy: no-referrer`, a `Content-Security-Policy` that allows nothing (the
  API only serves JSON), `Cache-Control: no-store` (answers hold names and money: no browser,
  proxy or service worker keeps them), and `Strict-Transport-Security` in production.
- **No debug output**: `/docs`, `/redoc` and `/openapi.json` are off; an unexpected error answers
  `500 {"detail": "Something went wrong on the server. Please try again."}` and is logged with
  its traceback, never sent; database errors never include the values (SQLAlchemy
  `hide_parameters`), so a failed insert can't put a customer's name in the logs.
- **Request size limits**: bodies over `MAX_REQUEST_BYTES` (128 KB) get `413`, except
  `POST /transcribe`, which may be `STT_MAX_AUDIO_BYTES` + 64 KB. Bodies without a
  `Content-Length` are counted as they arrive.
- **`GET /health`** runs `SELECT 1`: `200 {"status": "ok", "database": "ok"}`, or `503
  {"status": "error", "database": "unreachable"}`, which tells Render to restart or hold the deploy.

## Project structure

```
backend/
├── app/
│   ├── main.py          # FastAPI app factory, routers, error handlers
│   ├── config.py        # Settings from environment variables / .env
│   ├── database.py      # Engine, per-request session, "is the database migrated?" check
│   ├── auth.py          # logged-in user dependency, "this shop is yours" check (404 if not)
│   ├── security.py      # argon2id password hashes, JWT login tokens
│   ├── rate_limit.py    # in-memory rate limiter (login, register, parse, transcribe)
│   ├── privacy.py       # the privacy note's version, and where its promises are kept
│   ├── logging_privacy.py # keeps query strings (names) out of the access log
│   ├── groq_models.py   # startup check: logs a clear error if Groq doesn't serve a configured model
│   ├── http_security.py # security headers and the request body size limit (middleware)
│   ├── time_utils.py    # UTC / shop-local-time helpers
│   ├── llm/             # LLM interface, Groq client, rule-based demo parser
│   ├── stt/             # speech-to-text interface and the Groq Whisper client
│   ├── models/          # SQLAlchemy tables: Shop, User, RevokedToken, Customer, Transaction,
│   │                    #   EntryTiming (entry speed), IdempotencyKey
│   ├── schemas/         # Pydantic request/response models and validation
│   ├── routers/         # HTTP endpoints (thin, just call services)
│   └── services/        # Business logic (auth, balance, customers, transactions, dashboard,
│                        #   reminders, parsing, parse_prompt, number_words, name_matching,
│                        #   transcription, phones, export, entry_speed, idempotency)
├── migrations/          # Alembic: env.py and versions/ (0001 initial schema, 0002 accounts,
│                        #   0003 entry timings, 0004 idempotency keys)
├── eval/                # accuracy evaluation: run_eval.py, data/sentences.json (186),
│                        #   results/, my_sentences.template.csv, rules_parity.py (README inside)
├── start.sh             # server start: alembic upgrade head, then uvicorn (Render, Docker)
├── Dockerfile
├── alembic.ini
├── tests/               # pytest suite (the LLM and speech-to-text are always faked)
│   └── fixtures/eval_sentences.json   # example sentences + expected output
├── app/seed.py          # demo shop: python -m app.seed
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml       # pytest and ruff config
└── .env.example
frontend/                # React + Vite + TypeScript + Tailwind, an installable PWA
├── src/
│   ├── App.tsx          # the shell: login while logged out; title bar, screen, bottom tabs
│   ├── session.ts       # who is logged in (token + user), kept in localStorage
│   ├── route.ts         # which screen is open, kept in the URL hash (#/customers/7)
│   ├── screens/         # HisabScreen (entry → confirm/edit/several → saved + undo),
│   │                    #   CustomersScreen, KhataScreen, DashboardScreen, SettingsScreen,
│   │                    #   AuthScreens (login, register)
│   ├── customers.ts     # customer list search (Bangla ↔ English) and sorting
│   ├── reminder.ts      # wa.me link and copy-to-clipboard
│   ├── strings.ts       # every UI text, in Banglish (add a Bangla/English set here later)
│   ├── phone.ts         # Bangladesh / India mobile numbers (same rules as the backend)
│   ├── config.ts        # VITE_API_URL, the privacy note's version
│   ├── api/             # fetch client and the backend's JSON types
│   ├── components/      # SmartEntry, MicButton, ConfirmationCard, MultiConfirm, EntryForm,
│   │                    #   BottomNav, TransactionForm, CustomerForm, ReminderSheet,
│   │                    #   SavedMessage (with Undo), WeekChart, Dialog...
│   ├── voice/           # speech engines (browser / server), useVoiceInput, voice settings
│   ├── offline/         # rules.ts (the rule parser in TypeScript) + rulesParity.json,
│   │                    #   localPreview, queue (IndexedDB, sync, Idempotency-Key),
│   │                    #   customerCache, store, online
│   ├── entrySpeed.ts    # first keystroke / mic press → saved timer
│   └── test/            # test setup, the fetch mock and the speech API mocks
├── pwa/sw.js            # the service worker (vite.config.ts fills in the file list)
├── public/              # manifest.webmanifest, icons/, favicon
├── docker/              # nginx config for the Docker image
├── vercel.json          # Vercel: SPA routing, caching, security headers
├── Dockerfile
└── .env.example
docker-compose.yml       # PostgreSQL + API + frontend: docker compose up --build
render.yaml              # Render blueprint: API + PostgreSQL
.github/workflows/ci.yml # CI: lint, tests (SQLite + PostgreSQL), build, docker compose smoke test
```

## Data model

```
users 1 ──── 1 shops 1 ──── * customers 1 ──── * transactions
                 └──────────────────────────────────┘ (transactions also carry shop_id)
revoked_tokens (logged-out logins, until they would have expired)
```

| Table | Columns |
|---|---|
| **users** | `id`, `shop_id` (unique: one shop each), `name`, `phone` (unique, optional), `email` (unique, optional; one of the two is required), `password_hash` (argon2id), `ai_enabled`, `consent_version`, `consent_at`, `created_at` |
| **revoked_tokens** | `jti` (the token's id), `expires_at` |
| **shops** | `id`, `name`, `owner_name`, `created_at` |
| **customers** | `id`, `shop_id`, `name`, `phone` (optional), `note` (optional area/note), `created_at` |
| **transactions** | `id`, `shop_id`, `customer_id`, `type` (`credit` \| `payment`), `amount`, `item` (optional), `raw_text` (optional), `created_at` |
| **entry_timings** | `id`, `shop_id`, `duration_ms`, `input_method` (`typed` \| `voice`), `entry_count`, `created_at`: the dashboard's entry speed, numbers only |

- **`type`**: `credit` means the customer took goods on baki. `payment` means the customer paid money.
- **`amount`**: a whole number of taka, always greater than 0 (also enforced by a database
  CHECK constraint). The `type` says which direction the money moved, so amounts are never negative.
- **`phone`** (customers and users): a Bangladesh or India mobile, stored as `+8801711000001` /
  `+919876543210` whatever way it was typed (`app/services/phones.py`). Anything else is refused.
- Deleting a shop deletes its user, customers and transactions with it (`ON DELETE CASCADE`).
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
The logic lives in one place, `app/services/balance.py`, with a pure-Python version and an
identical SQL version (used to sum many customers at once, and for running balances).

- **Running balance**: the customer's transactions are sorted oldest first, and each row
  shows the balance right after it. It's worked out in the database with a window function over
  the customer's whole history, so a page of a long khata (newest 20, say) shows exactly the same
  numbers as the full list.
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

Everything except `/health`, `/auth/register` and `/auth/login` needs the login token from
`/auth/login` or `/auth/register` in an `Authorization: Bearer <access_token>` header. Every
`/shops/{shop_id}/...` path must be the logged-in user's own shop: any other shop id (and any
customer or transaction of another shop) answers **404**, exactly like one that doesn't exist.

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check (no login) |
| POST | `/auth/register` | Create a shop and its shopkeeper (`name`, `shop_name`, `phone` and/or `email`, `password` ≥ 8 characters, `consent: true`, `consent_version`); logs in. `409` if the phone/email has an account |
| POST | `/auth/login` | `{"login": "<phone in any format, or email>", "password": "..."}` → `access_token`, `expires_at`, `user` (with its `shop`). `401` for a wrong login or password |
| POST | `/auth/logout` | This token stops working now (204) |
| GET | `/auth/me` | The logged-in user and shop, `ai_enabled`, consent version and time |
| PATCH | `/auth/me` | Settings: `{"ai_enabled": false}` turns the AI off |
| DELETE | `/auth/me` | Delete the account, shop, customers and transactions. Body `{"password": "..."}`; `403` if wrong |
| GET | `/shops/{shop_id}` | The shop |
| GET | `/shops/{shop_id}/export.csv` | The whole khata as CSV (see [Privacy](#privacy)) |
| POST | `/shops/{shop_id}/customers` | Create a customer |
| GET | `/shops/{shop_id}/customers?search=` | List customers with balances and `owed_since` (date of the oldest unpaid credit, or null); optional search by name/note/phone |
| GET | `/shops/{shop_id}/customers/{customer_id}` | Get one customer with current balance |
| PATCH | `/shops/{shop_id}/customers/{customer_id}` | Change `name`, `phone`, `note` (only the fields sent; `null` clears phone/note). `409` if it would clash with another customer |
| DELETE | `/shops/{shop_id}/customers/{customer_id}` | Only for a customer without transactions (`409` otherwise); used by Undo |
| POST | `/shops/{shop_id}/customers/{customer_id}/transactions` | Create a transaction (response includes the new balance) |
| GET | `/shops/{shop_id}/customers/{customer_id}/transactions?order=newest&limit=20&offset=0` | Customer ledger with running balance. `order`: `oldest` (default) or `newest`; `limit` (1–200, default all) and `offset` page through it; the answer has `total` and `has_more` |
| POST | `/shops/{shop_id}/customers/{customer_id}/reminder` | A polite Banglish baki reminder (`message`, `polished`, `phone`, `whatsapp_number`). Body optional: `{"polish": false}` skips the AI. Sends and saves nothing; `409` if nothing is owed |
| GET | `/shops/{shop_id}/transactions?limit=10` | The shop's latest transactions (all customers), newest first, with customer name and note |
| GET | `/shops/{shop_id}/transactions/{transaction_id}` | Get one transaction |
| PATCH | `/shops/{shop_id}/transactions/{transaction_id}` | Edit a transaction (only the fields you send), including `created_at` (not in the future) |
| DELETE | `/shops/{shop_id}/transactions/{transaction_id}` | Delete a transaction (204) |
| GET | `/shops/{shop_id}/dashboard?overdue_days=30` | Total outstanding, today's collection and new baki, top 5, overdue customers, and `last_7_days` (`date`, `credit`, `payment` per local day, oldest first) |
| POST | `/shops/{shop_id}/parse` | Turn one free-form sentence into a transaction **preview** (saves nothing); `entries` has one item per customer |
| POST | `/shops/{shop_id}/parse/confirm` | Save the confirmed preview, creating the customer if new. Optional `Idempotency-Key` header (see below) |
| POST | `/shops/{shop_id}/parse/confirm-many` | Save several confirmed entries together (`{"entries": [...]}`, 1–10), all or none. Optional `Idempotency-Key` header |
| POST | `/transcribe` | A short voice recording (multipart `file`, optional `language`) → `{"text": "..."}` (saves nothing). `403` when the user turned AI off |
| GET | `/transcribe/status` | Whether server-side transcription can be used (not without a key, not with AI off), and its size/length limits |

**Errors**

- `401`: not logged in, or the login expired / was logged out (`WWW-Authenticate: Bearer`).
  The app then shows the login screen.
- `403`: a wrong password when deleting the account; server voice while AI is off.
- `404` / `409`: `{"detail": "Customer 7 not found in shop 1"}`
- `429`: too many tries; `{"detail": "Onek bar chesta hoyeche. 42 second por abar chesta korun.",
  "retry_after": 42}` and a `Retry-After` header (see [Rate limits](#rate-limits)).
- `422`: errors are listed per field, so the app can show them next to the input:

```json
{
  "detail": "Invalid request data",
  "errors": [{"field": "amount", "message": "Amount must be greater than 0"}]
}
```

**Example**

```bash
# Log in and keep the token (the demo login from `python -m app.seed`)
TOKEN=$(curl -s localhost:8000/auth/login -H 'content-type: application/json' \
  -d '{"login": "01700000000", "password": "demo1234"}' | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

curl -X POST localhost:8000/shops/1/customers/1/transactions \
  -H "Authorization: Bearer $TOKEN" \
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
cp .env.example .env                 # then set JWT_SECRET (see below)
alembic upgrade head                 # create / update the database
python -m app.seed                   # optional: the demo login and shop
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs (use **Authorize** with a token from `/auth/login` to try the
shop endpoints). The database is a SQLite file, `backend/baki_khata.db`, created by
`alembic upgrade head`; the app never creates tables itself and refuses to start on a database
that isn't up to date. Run commands from inside `backend/` so the `.env` file is picked up.

### Migrations (for developers)

After changing `app/models/`, make a migration, read it, and apply it:

```bash
alembic revision --autogenerate -m "add customer birthday"   # writes migrations/versions/0003_...
alembic upgrade head
alembic check            # "No new upgrade operations detected" = models and migrations agree
```

Number new files by hand if you like (`--rev-id 0003`). Keep migrations free of app imports
(plain `sa.DateTime()` for `UTCDateTime`), and give constraints names: SQLite runs `ALTER`s in
"batch mode" (it copies the table), which needs them. `tests/test_migrations.py` checks that
`upgrade head` builds exactly the models' schema, that downgrade works, and that the app won't
start on an un-migrated database. The tests themselves use `create_all` on an in-memory database
for speed.

### Configuration

All settings come from environment variables or `backend/.env`. See `.env.example`.
Don't commit `.env`; it's already in `.gitignore`.

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./baki_khata.db` | Database connection |
| `APP_TIMEZONE` | `Asia/Dhaka` | Decides what "today" means (`Asia/Kolkata` for India) |
| `APP_NAME` | `Baki Khata AI` | Shown in the API docs |
| `ENVIRONMENT` | `development` | `production`: refuses to start without `JWT_SECRET`, a PostgreSQL `DATABASE_URL` and https `CORS_ORIGINS`; no `/docs`; HSTS (see [Deploying](#what-production-mode-changes-in-the-backend)) |
| `JWT_SECRET` | *(empty)* | Signs login tokens; a long random value (≥ 32 characters). Empty outside production: a random one per start |
| `JWT_EXPIRE_MINUTES` | `10080` | How long a login lasts (7 days) |
| `RATE_LIMIT_ENABLED` | `true` | Switch the rate limits off (e.g. load tests) |
| `RATE_LIMIT_LOGIN_PER_MINUTE` | `10` | Login tries per minute, per IP and per account |
| `RATE_LIMIT_REGISTER_PER_HOUR` | `10` | New accounts per hour, per IP |
| `RATE_LIMIT_PARSE_PER_MINUTE` | `30` | `/parse` calls per minute, per shop |
| `RATE_LIMIT_TRANSCRIBE_PER_MINUTE` | `15` | `/transcribe` calls per minute, per shop |
| `SQL_ECHO` | `false` | Log SQL statements |
| `CORS_ORIGINS` | *(empty)*: `http://localhost:5173,http://127.0.0.1:5173` outside production | Comma-separated browser origins allowed to call the API (the frontend). Required in production, `https://` only |
| `MAX_REQUEST_BYTES` | `131072` | Largest request body (128 KB); `/transcribe` may be `STT_MAX_AUDIO_BYTES` + 64 KB |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1` | Read by uvicorn (`start.sh`): proxies whose `X-Forwarded-For` is trusted. `*` behind Render's proxy |
| `LLM_PROVIDER` | `auto` | `auto`: Groq when `GROQ_API_KEY` is set, otherwise the rule-based demo parser. `groq`: always Groq (503 without a key). `fake`: always the demo parser |
| `GROQ_API_KEY` | *(empty)* | Groq API key for AI parsing |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Groq chat model for parsing and reminder wording; must support JSON mode |
| `LLM_TIMEOUT_SECONDS` | `20` | How long to wait for the model (also used for transcription) |
| `GROQ_STT_MODEL` | `whisper-large-v3` | Groq speech-to-text model for `POST /transcribe` (`whisper-large-v3-turbo` is faster and cheaper, a little weaker on Bangla) |
| `STT_MAX_AUDIO_BYTES` | `1000000` | Largest recording `POST /transcribe` accepts (413 above it) |
| `STT_MAX_AUDIO_SECONDS` | `30` | Longest recording; the app stops recording at this point too |
| `SEED_DEMO_ON_START` | `false` | `true`: create the demo shop and login (`01700000000` / `demo1234`) at startup if they don't exist. Never resets them. For a public demo only |
| `PHONE_COUNTRY_CODE` | `880` | Country calling code for WhatsApp links of phones saved without one (from before numbers were normalized; `91` for India) |

### Switching to PostgreSQL

No code changes are needed (the driver, psycopg, is in `requirements.txt`):

```bash
# in .env
DATABASE_URL=postgresql://user:password@localhost:5432/baki_khata
# then, as always
alembic upgrade head
```

`postgres://` and `postgresql://` URLs get the psycopg driver automatically. Or run everything,
PostgreSQL included, with [Docker](#running-it-with-docker).

### Frontend configuration

From `frontend/.env` (see `frontend/.env.example`). Vite reads it when `npm run dev` starts.

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | Where the backend runs |
| `VITE_SHOW_DEMO_LOGIN` | `false` | `true`: the login screen shows "Demo login: 01700000000 / demo1234" (public demo only) |

There's no shop setting: the app uses the shop of whoever logs in. (`VITE_SHOP_ID` is gone; delete
it from an old `frontend/.env`.)

### Demo mode without an API key

With `LLM_PROVIDER=fake`, or `auto` and no `GROQ_API_KEY`, `/parse` uses a small rule-based
parser (`app/llm/rule_based.py`) instead of the AI. It plugs in behind the same `LLMClient`
interface, so number normalization, validation, the sanity check and customer name matching all
run exactly as with the real model. It's good enough to demo the app (it reads 90% of the 186
evaluation sentences fully right, see [Evaluation results](#evaluation-results)): the name is the first word, the amount is the number next to "taka" (or the
one that isn't a quantity like "2 kg"), and the type comes from words like baki/nilo vs.
dilo/joma/shodh. Anything less regular needs the real model; the backend logs a warning at the
first parse so it's clear which one is running.

### Setting up Groq (AI parsing)

1. Create a free API key at https://console.groq.com/keys.
2. Put it in `backend/.env` (never in code, never committed; `.env` is git-ignored):

   ```bash
   GROQ_API_KEY=gsk_your_key_here
   GROQ_MODEL=openai/gpt-oss-120b
   ```

   Any model listed at https://console.groq.com/docs/models that supports JSON mode works.
   `openai/gpt-oss-120b` is a reasoning model; the backend asks it for low reasoning effort,
   which is plenty for one sentence and keeps parsing fast.
3. **If Groq retires a model** (as it did `llama-3.3-70b-versatile`, the old default, in 2026):
   at startup the backend asks Groq for the list of models it serves and checks that
   `GROQ_MODEL` and `GROQ_STT_MODEL` are in it. If one isn't, it logs an error such as

   ```
   Groq rejected GROQ_MODEL='llama-3.3-70b-versatile': The model `llama-3.3-70b-versatile` is
   not in the list of models Groq serves to this API key. The model may have been retired or
   misspelled. Set GROQ_MODEL in backend/.env to a current model from
   https://console.groq.com/docs/models and restart the backend.
   ```

   (Ids with a slash, like `openai/gpt-oss-120b`, are looked up in that list. Asking Groq for one
   model by id doesn't work for them: the SDK escapes the slash in the URL and Groq answers
   "The model `openai%2Fgpt-oss-120b` does not exist".) A similar message is logged if a request
   fails later because of the model. Change the setting in `backend/.env` and restart. The check
   runs in the background and never stops the backend from starting (no internet only gives a
   warning). Check https://console.groq.com/docs/deprecations from time to time.
4. Restart `uvicorn` and try it:

   ```bash
   curl -X POST localhost:8000/shops/1/parse -H "Authorization: Bearer $TOKEN" \
     -H 'content-type: application/json' -d '{"text": "salma apa pach sho taka baki, dal r tel"}'
   ```

   (`$TOKEN` from `/auth/login`, see the [API example](#api).) With *AI bondho rakhun* on, the
   rule-based parser answers instead and Groq is never called.

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
The same happens when the shopkeeper turned AI off in Settings: `/transcribe/status` says
`"available": false` for them and `POST /transcribe` answers `403`, so their voice never reaches
Groq. Both endpoints need the login token, and `/transcribe` is rate-limited per shop.

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
   ▼    {"entries": [{"customer_name": "salma", "amount": 500, "type": "credit", "item": "dal, tel", "confidence": 0.95}]}
   │ 3. Pydantic validation, one retry on bad output   (app/services/parsing.py)
   │ 4. sanity check: is the amount really in the sentence?
   │ 5. customer name matching (app/services/name_matching.py)  no AI
   ▼
preview  →  shopkeeper checks / edits  →  POST /parse/confirm  →  saved, with raw_text
                                        (or /parse/confirm-many for several customers)
```

With *AI bondho rakhun* on (Settings), step 2 is the rule-based parser on the server instead of
the LLM; every other step is the same.

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
| sowa sho / সোয়া শো, sowa tin sho | 125, 325 | sowa = 1.25 ×; sowa N = N + ¼ |
| ek hajar pach sho ponchash taka | 1550 | groups add up |
| bish taka / five hundred taka | 20 / 500 | number word before taka/tk/টাকা |

A number word is only converted before a multiplier (sho/hajar/lakh) or a currency word, so
"tin kg alu" or "met at the shop" are left alone. The model gets both the original sentence
and the converted one.

### 2. Prompt design

The prompt lives in `app/services/parse_prompt.py`:

- **Strict output contract**: exactly one JSON object, `{"entries": [...]}`, each entry with
  `customer_name`, `amount` (integer taka), `type` (`credit` | `payment`), `item` (nullable) and
  `confidence` (0–1). Usually one entry; one per customer when the sentence lists several, each
  with their own amount ("rahim 200 baki, karim 500 dilo"), at most 10. Several goods for one
  customer stay one entry. A bare single entry object (the old contract) is still accepted.
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
  "warnings": [],
  "parser": "llm",
  "model": "openai/gpt-oss-120b"
}
```

`parser` says who read the sentence: `"llm"` (the AI model named in `model`) or `"rules"` (the
rule-based parser, `model: "rule-based"`: AI turned off in Settings, or no `GROQ_API_KEY` on the
server). The confirmation card shows it as a small **AI** or **AI chhara** label, with the model
name on hover, so nobody mistakes a rules reading for the AI's.

For a sentence about several customers, `entries` holds one `{parsed, match, warnings}` per
customer, in the order written; the top-level `parsed`, `match` and `warnings` are always the
first entry (so a client that only knows single entries keeps working). Each entry's amount is
checked against the sentence and each name is matched on its own.

**Confirm**: `POST /shops/{shop_id}/parse/confirm` with the (possibly edited) values and
**either** an existing `customer_id` **or** a `new_customer`:

```json
{"raw_text": "salma apa pach sho taka baki, dal r tel", "type": "credit", "amount": 500,
 "item": "dal, tel", "new_customer": {"name": "Salma", "note": "Mosque road"}}
```

It returns `201` with the saved `transaction` (including `raw_text` and the new balance), the
`customer`, and `customer_created`. A new customer and its transaction are saved in one
commit: if the name clashes with an existing customer (409), nothing is saved.

**Confirm several**: `POST /shops/{shop_id}/parse/confirm-many` with
`{"entries": [<confirm body>, ...]}` (1–10) returns `{"results": [<confirm result>, ...]}` in the
same order. One commit: if any entry fails (another shop's customer, a name clash), nothing is
saved. Two entries for the same new customer ("tanvir 50 baki, tanvir 20 dilo") create them once.
Each result's balance is the customer's balance after all of them.

**Idempotency-Key** (both confirm endpoints): a random key per save, 8–100 of `A-Z a-z 0-9 _ . : -`
(the app uses a UUID). The answer is stored with the shop and key in the same commit as the
entries (`idempotency_keys`). Sending the same save again with the key answers the stored result
(`201`, header `Idempotent-Replayed: true`) and saves nothing; the same key with different data
is `409`. Two requests racing with one key save once (the unique key stops the second at its
commit). A failed save doesn't use the key up. Keys are forgotten after 30 days.

**Errors**: `422` the sentence has no name/amount, or invalid input; `502` the model gave an
invalid answer twice; `503` `LLM_PROVIDER=groq` without a `GROQ_API_KEY`, or Groq is
unreachable / rejected the request (details are logged, not returned). A Groq `429` or timeout
is not an error: the rules read the sentence and `notice` says so (see [Rate limits](#rate-limits)).

### Swapping the LLM provider

Everything outside `app/llm/` depends only on the `LLMClient` interface in
`app/llm/base.py`: one method, `complete_json(messages) -> str`. To use another provider,
add a class with that method and return it from `build_llm_client()` in
`app/llm/__init__.py` (that's how the rule-based demo parser plugs in too).

### Accuracy evaluation

`backend/eval/` measures how well each parser reads shopkeeper sentences: 186 labelled
sentences in 14 categories (Banglish/Bangla/English/code-mixed, credit and payment, number
words, Bangla digits, honorifics, items, typos and missing spaces, past-tense payments, several
entries in one sentence, no amount, not a transaction), plus any real ones you add in
`backend/eval/my_sentences.csv`. In `backend/`:

```bash
python -m eval.run_eval --parser rules   # rule-based parser, no key needed
python -m eval.run_eval --parser llm     # the AI model (GROQ_API_KEY in backend/.env)
python -m eval.run_eval --parser both    # both, with a side-by-side comparison
```

It reports accuracy per field and for whole sentences, per category and language, average and
p95 latency, and every failure, as Markdown and JSON in `backend/eval/results/`. See
[backend/eval/README.md](backend/eval/README.md) for how answers are scored and how to add
real sentences. (`tests/fixtures/eval_sentences.json`, the first 20 sentences, is still used by
unit tests; all of them are in the evaluation set too.)

## Running the tests

```bash
cd backend
pytest              # 742 tests
ruff check . && ruff format --check .
```

```bash
cd frontend
npm test            # Vitest + React Testing Library, 428 tests (npm run test:watch to re-run on save)
npm run typecheck   # TypeScript
npm run lint        # oxlint
npm run format      # Prettier
```

CI runs all of it on every push (see [Continuous integration](#continuous-integration)).

**Added in this round:** the Groq model check with ids that contain a slash
(`test_groq_models.py`), which parser read a sentence (`test_parse_api.py`, `test_privacy.py`),
the evaluation's data, scoring, CSV and reports with no real API (`test_eval.py`, plus a floor
under the rule parser's accuracy), entry speed (`test_entry_speed.py`), production mode,
security headers, size limits and `/health` (`test_production.py`), idempotency keys including
two requests racing (`test_idempotency.py`), and that the browser's copy of the rules is up to
date (`test_rules_parity.py`). In the frontend: the AI / AI chhara label, entry timing
(`src/EntrySpeed.test.tsx`), the rule parser's 237 parity cases (`src/offline/rules.test.ts`),
the queue's order, retries, refusals and created customers (`src/offline/queue.test.ts`), and the
whole offline flow on the Hisab screen (`src/Offline.test.tsx`, with a fake IndexedDB).

The backend tests cover (besides the parsing, balances, dashboard, reminders and voice from
before): migrations (`test_migrations.py`: `upgrade head` equals the models, downgrade, the app
refusing an un-migrated database), accounts (`test_auth.py`: register with consent, login by
phone in any format or email, wrong logins, token expiry, forged tokens, logout, deleting the
account), ownership (`test_ownership.py`: shopkeeper A against every one of B's endpoints and
ids), privacy (`test_privacy.py`: AI off never calls the LLM or speech-to-text, the CSV with
Bangla text and formula escaping, logs without names or amounts), phone numbers
(`test_phones.py`), customer editing, date editing with running balances, several entries per
sentence with a faked LLM (`test_multi_entry.py`), undo (`test_undo.py`) and rate limits
(`test_rate_limit.py`).

The frontend tests drive the real screens with the backend mocked (`src/test/mockApi.ts`
replaces `fetch`): the confirmation card for a matched, fuzzy, ambiguous and new customer, edit
mode, saving, and every error falling back to manual entry; the bottom tabs; the customer list's
sorting and search in both scripts (`src/CustomerList.test.tsx`, `src/customers.test.ts`); the
khata's running balance, *Aro dekhun*, edit, delete with its confirm, quick baki/joma and the
WhatsApp reminder (`src/Khata.test.tsx`); and the dashboard (`src/Dashboard.test.tsx`). The voice tests
(`src/VoiceInput.test.tsx`) replace the speech APIs (`src/test/mockSpeech.ts`: a fake
`SpeechRecognition`, `MediaRecorder` and microphone) and cover the mic button's states, hold vs.
tap vs. keyboard, the transcript going through the normal flow, auto-submit, saved settings,
permission denied and the other errors, and the server fallback. Every test starts logged in
(`src/test/setup.ts`); `src/Auth.test.tsx` covers login, show/hide password, register with the
privacy note, staying logged in across a reload, a 401 or the token's expiry going back to
login, and logout. `src/Settings.test.tsx` covers the AI switch, the CSV download and deleting the
account; `src/CustomerEdit.test.tsx` adding and editing customers, phone checks, the reminder's
"add phone" and changing an entry's date; `src/MultiEntry.test.tsx` the cards for several
customers; `src/Undo.test.tsx` the 10-second undo.

The tests never call Groq and need no API key: the LLM and speech-to-text are replaced by fakes
that return scripted answers (`FakeLLM` and `FakeSTT` in `tests/conftest.py`).

By default the tests use a fresh in-memory SQLite database for each test. To run the same suite
against PostgreSQL, point `TEST_DATABASE_URL` at a **throwaway** database (its tables are dropped):

```bash
TEST_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/baki_test pytest
```

## Next steps (not built yet)

- **Run the LLM evaluation** with a key (`python -m eval.run_eval --parser both` in `backend/`),
  commit `backend/eval/results/`, and put the numbers in [Evaluation results](#evaluation-results).
  Then add real shopkeeper sentences in `backend/eval/my_sentences.csv`.
- **Fill in the screenshots** (`docs/screenshots/`, see [Screenshots](#screenshots)).
- **Offline is rules-only**: entries written offline are read by the rule-based parser; re-reading
  pending entries with the AI when the connection is back (before the shopkeeper confirms) would
  need the confirmation to move to after sync.
- **Offline balances** are the last ones known; pending entries aren't added to them yet.
- A **Content-Security-Policy** listing the exact API origin on Vercel (today `connect-src` allows
  any `https:` origin, since the API's address is a build setting).

- **Password reset** (by SMS code or email). Today a forgotten password means a new account.
- **Change password / phone** in Settings, and see where you're logged in ("log out everywhere").
- **Shared rate limits** (Redis, or the proxy) for more than one server process.
- **An `HttpOnly` cookie for the login** instead of `localStorage` (with CSRF protection), and
  shorter tokens with a refresh token.
- **Link shops from before accounts** to a user (a small admin script); they have no login now.
- **Several people per shop** (owner and helper) with their own logins.
- Record consent withdrawals and AI on/off changes with their time (today only the current
  state is stored), and show the privacy note again in Settings.
- Undo for entries saved on the khata screen (Undo is on the Hisab screen only).
- Measure voice accuracy: a few recorded Banglish sentences run through both engines and
  `/parse`, to choose the default engine and Whisper model with numbers
- A Bangla-script / English switch for the UI (all texts are in `frontend/src/strings.ts`)
- Store the AI's original parse next to the confirmed values, to measure how often shopkeepers correct it
