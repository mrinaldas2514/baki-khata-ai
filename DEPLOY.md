# Deploying Baki Khata AI (beginner guide)

This puts the app on the internet for free:

- the **backend** (the API) and its **PostgreSQL database** on [Render](https://render.com),
  set up from `render.yaml` in this repository;
- the **frontend** (the app people open on their phone) on [Vercel](https://vercel.com), set up
  from `frontend/vercel.json`.

Do it in this order: **1. backend → 2. frontend → 3. tell the backend the frontend's address
(CORS)**. The backend has to exist first because the frontend needs its address when it's built.

It takes about 20 minutes, most of it waiting.

---

## 0. Before you start

You need:

1. This repository on **GitHub** (your own copy, e.g. `github.com/<you>/baki-khata-ai`).
2. A **Render** account: go to https://dashboard.render.com and click **Sign in with GitHub**.
3. A **Vercel** account: go to https://vercel.com/signup, choose **Hobby**, then
   **Continue with GitHub**.
4. Optional, for real AI parsing: a **Groq API key**. Go to https://console.groq.com/keys, log in,
   click **Create API Key**, give it a name (e.g. `baki-khata-render`), and copy the key (it starts
   with `gsk_`). Groq shows it only once: paste it somewhere safe for step 1. Without a key the app
   still works with the simple rule-based parser (the card says **AI chhara**).

You don't need to install anything on your computer.

---

## 1. Backend + database on Render

### 1.1 Create everything from the blueprint

1. Open https://dashboard.render.com.
2. Top right: click **+ New**, then **Blueprint**.
3. Under **Connect a repository**, find `baki-khata-ai`.
   - Not in the list? Click **Configure account** (or **Connect GitHub**), choose your GitHub
     account, pick **Only select repositories**, select `baki-khata-ai`, click **Save**, and go
     back to Render.
4. Click **Connect** next to the repository.
5. **Blueprint Name**: type `baki-khata`. **Branch**: `main`.
6. Render reads `render.yaml` and lists what it will create:
   - a web service **baki-khata-api** (Python, Free, Singapore)
   - a PostgreSQL database **baki-khata-db** (Free, Singapore)
7. It asks for the values that aren't in the file:

   | Field | What to type |
   |---|---|
   | `CORS_ORIGINS` | `https://example.com` for now. You don't know the Vercel address yet; you'll fix this in step 3. (It can't be empty: the backend refuses to start in production without it.) |
   | `GROQ_API_KEY` | Your `gsk_...` key from step 0.4, or leave it empty for the rule-based parser only. |

8. Click **Apply** (or **Deploy Blueprint**).

Render now creates the database (1-2 minutes), then builds the backend (`pip install`, 2-4
minutes), then starts it. Every start runs `backend/start.sh`: first `alembic upgrade head`
(creates/updates the database tables), then the server. If the migration fails, the server
doesn't start, so you never run on a half-updated database.

### 1.2 Watch it start

1. In the Render dashboard click **baki-khata-api**, then the **Logs** tab.
2. You should see, in this order:
   - `Running upgrade  -> 0001, Initial schema...` up to `0003 -> 0004, ...` (only on the first deploy)
   - `SEED_DEMO_ON_START: created the demo shop 1` (the first time; later starts say it
     `already exists, left as it is`)
   - `Uvicorn running on http://0.0.0.0:10000` (the port number may differ)
3. At the top of the page the status turns **Live**.

### 1.3 Check `/health`

1. At the top of the service page, copy its address, e.g. `https://baki-khata-api.onrender.com`.
   (If the name was taken, Render adds letters, e.g. `https://baki-khata-api-x7k2.onrender.com`.
   Always use **your** address from here on.)
2. Open `https://<your-backend>.onrender.com/health` in a browser. You should see:

   ```json
   {"status": "ok", "database": "ok"}
   ```

   - `{"status": "error", "database": "unreachable"}` (HTTP 503): the backend runs but can't
     reach the database. See [Troubleshooting](#troubleshooting).
   - The page loads for a long time: the free service was asleep; wait up to a minute.

`/docs` is switched off in production on purpose; a 404 there is normal.

---

## 2. Frontend on Vercel

1. Open https://vercel.com/new (or in the dashboard: **Add New...** → **Project**).
2. Under **Import Git Repository**, find `baki-khata-ai` and click **Import**.
   - Not in the list? Click **Adjust GitHub App Permissions**, allow `baki-khata-ai`, and come back.
3. On **Configure Project**:
   1. **Project Name**: e.g. `baki-khata` (this becomes `https://baki-khata.vercel.app` if free).
   2. **Root Directory**: click **Edit**, choose the **`frontend`** folder, click **Continue**.
      This is the most common mistake: without it Vercel builds the wrong folder.
   3. **Framework Preset**: Vite (detected). Leave **Build and Output Settings** alone:
      `frontend/vercel.json` sets them.
   4. Open **Environment Variables** and add these two (Key, Value, **Add**):

      | Key | Value |
      |---|---|
      | `VITE_API_URL` | Your Render address from 1.3, e.g. `https://baki-khata-api.onrender.com`. `https://`, **no** `/` at the end, **no** `/health`. |
      | `VITE_SHOW_DEMO_LOGIN` | `true` for a public demo (shows "Demo login: 01700000000 / demo1234" on the login screen). Leave it out for a real shop. |

4. Click **Deploy**. It takes about a minute. When you see the congratulations screen, click
   **Continue to Dashboard**.
5. Under **Domains**, copy the main address, e.g. `https://baki-khata.vercel.app`.
   Use this one, **not** the long per-deployment address (`baki-khata-abc123-you.vercel.app`):
   the backend only accepts the exact address you give it in step 3.

`VITE_*` values are baked in when Vercel **builds** the app. If you change one later, go to
**Deployments**, click **⋯** on the latest one, **Redeploy**.

---

## 3. Tell the backend the frontend's address (CORS)

The browser only lets the app talk to the backend if the backend lists the app's address.

1. Render dashboard → **baki-khata-api** → **Environment**.
2. Find `CORS_ORIGINS`, click **Edit** (pencil), and replace `https://example.com` with your
   Vercel address from 2.5, e.g. `https://baki-khata.vercel.app`.
   - Exactly as the browser shows it: `https://`, no path, no `*`.
   - Several addresses (e.g. a custom domain too): separate them with commas,
     `https://baki-khata.vercel.app,https://khata.example.com`.
3. Click **Save Changes** (choose **Save, rebuild, and deploy** if asked). Wait until the
   service is **Live** again (1-3 minutes).
4. Open your Vercel address on your phone or computer and log in with **01700000000** /
   **demo1234**. Type `salma apa pach sho taka baki` and check the confirmation card.

Done. From now on, every push to `main` redeploys both automatically (Render: `autoDeploy`,
Vercel: its Git integration). The values you typed in Render's dashboard stay; a later blueprint
sync doesn't overwrite them.

---

## Every environment variable

### Render web service `baki-khata-api`

| Variable | Set by | Value | What it does |
|---|---|---|---|
| `ENVIRONMENT` | blueprint | `production` | Refuses to start with unsafe settings (and lists them in the log), turns off `/docs`, adds HSTS. |
| `DATABASE_URL` | blueprint (from `baki-khata-db`) | Render's `postgresql://...` internal URL | The database. Pasted as is; the backend adds the driver. If you ever set it by hand, use the database's **Internal Database URL**. |
| `JWT_SECRET` | blueprint (`generateValue`) | 256 random bits, made once | Signs logins. **Changing it logs everyone out.** To set your own: run `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` and paste the output (at least 32 characters). Never commit it. |
| `CORS_ORIGINS` | **you** | Your Vercel address, e.g. `https://baki-khata.vercel.app` | Which websites may call the API. |
| `GROQ_API_KEY` | **you** (optional) | `gsk_...` | Real AI parsing and voice transcription. Empty: rule-based parser ("AI chhara"), and voice uses the phone's own speech recognition. |
| `GROQ_MODEL` | blueprint | `openai/gpt-oss-120b` | The Groq model. If Groq retires it, the log says so at startup; change it here. |
| `APP_TIMEZONE` | blueprint | `Asia/Dhaka` | What "today" means. `Asia/Kolkata` for India. |
| `FORWARDED_ALLOW_IPS` | blueprint | `*` | Trust Render's proxy, so rate limits see the real client IP. |
| `SEED_DEMO_ON_START` | blueprint | `true` | Creates the demo shop and login (01700000000 / demo1234) at startup **if they don't exist**. Never resets or deletes anything. Set `false` for a real shop. |
| `PYTHON_VERSION` | blueprint | `3.13` | Python version for the build. |
| `PORT` | Render | (automatic) | Don't add it yourself. |

Optional extras (add with **+ Add Environment Variable**): `LLM_TIMEOUT_SECONDS` (default `20`;
lower, e.g. `8`, makes a slow AI fall back to the rules sooner), `PHONE_COUNTRY_CODE=91` (India),
`RATE_LIMIT_PARSE_PER_MINUTE`. All settings are in the README's
[Configuration](README.md#configuration).

### Render database `baki-khata-db`

Nothing to set. Its connection string goes to the web service automatically. It only accepts
connections from your Render services (`ipAllowList: []`), not from the internet.

### Vercel project (Root Directory `frontend`)

| Variable | Value | What it does |
|---|---|---|
| `VITE_API_URL` | Your Render address, e.g. `https://baki-khata-api.onrender.com` | Where the app sends requests. Build time: redeploy after changing it. |
| `VITE_SHOW_DEMO_LOGIN` | `true` on a demo site, otherwise leave it out | Shows the demo login on the login screen. Build time. |

---

## Free-plan limits to know

These were true when this guide was written (late 2026). Plans change: check
https://render.com/docs/free and https://vercel.com/docs/plans/hobby before relying on them.

**Render free web service**

- **Sleeps after 15 minutes without requests.** The next request wakes it, which takes up to
  about a minute (a "cold start"). The first page load after a quiet period is slow, or the app
  says it can't reach the server; the app's offline mode keeps entries on the phone and sends
  them once the server is up. Open `/health` a minute before a demo to wake it.
- 750 free instance hours a month per workspace: enough for this one service all month.
- Small machine (512 MB RAM); restarts can happen at any time.
- **No Shell tab, no one-off jobs, no pre-deploy command.** That's why the demo data is created
  by `SEED_DEMO_ON_START` instead of `python -m app.seed`, and why `start.sh` runs the migrations.
- The rate limits are counted in memory, so they reset whenever it sleeps or restarts.

**Render free PostgreSQL**

- **Expires 30 days after it's created.** Render emails you; after that you get a grace period
  (about 14 days) to upgrade before the database **and its data are deleted**.
- 1 GB storage, one free database per workspace, no backups.
- To keep the demo going for free: delete the expired database, create a new free one with the
  same name (or re-sync the blueprint), and redeploy the web service. The migrations run again
  and `SEED_DEMO_ON_START` recreates the demo login. **All other accounts and entries are
  lost**, so don't keep a real shop's khata on a free database.

**Vercel Hobby**

- Free for personal, non-commercial projects. The site is static: it never sleeps and loads fast.
- Every push makes a "preview" deployment with its own address. Those addresses aren't in
  `CORS_ORIGINS`, so logging in on them fails; use the main address.

**Groq free tier**

- About **8,000 tokens a minute** for `openai/gpt-oss-120b`, plus daily limits. One sentence uses
  roughly 1,000-1,500 tokens, so a handful of people typing at once can hit it.
- When Groq answers `429` (rate limited) or doesn't answer in time, the app doesn't show an
  error: that sentence is read by the rule-based parser, the card says **AI chhara**, and a short
  note asks the shopkeeper to check it.

---

## Troubleshooting

Look at the logs first: Render → **baki-khata-api** → **Logs**; Vercel → project →
**Deployments** → the deployment → **Build Logs**; in the browser, the developer tools'
**Console** (F12).

| What you see | Why | Fix |
|---|---|---|
| Browser console: *blocked by CORS policy: No 'Access-Control-Allow-Origin' header*; the app says it can't reach the server | `CORS_ORIGINS` on Render isn't exactly the address in the browser bar | Copy the address from the browser bar (e.g. `https://baki-khata.vercel.app`, no path) into `CORS_ORIGINS`, **Save, rebuild, and deploy**. Using a preview URL (`...-git-...vercel.app`)? Use the main domain instead, or add it to the list. |
| CORS error **and** `/health` doesn't load either | The backend is down or still waking up, so there's no answer at all | Open `/health`, wait for it, then reload the app. Check Render's Logs for a crash. |
| **502** / "Bad Gateway" / a very slow first load | The free service was asleep (cold start) or is still deploying | Wait up to a minute and reload. If it stays 502, check Logs: the server may have failed to start. |
| Render deploy fails with *ENVIRONMENT=production, but the settings aren't safe yet* | A required setting is missing or wrong; the log lists each one | Usually `CORS_ORIGINS` is empty, has a `/` path or `*`, or uses `http://`. Fix it in **Environment** and save. |
| Logs show an `alembic` error and *Exited with status 1* (migrations failing) | The database isn't ready, is expired/deleted, or `DATABASE_URL` isn't linked | Check that `baki-khata-db` is **Available**. Check `DATABASE_URL` is set on the web service (it should come "from database"). Then **Manual Deploy → Deploy latest commit**. An expired free database must be recreated (see above). |
| `/health` says `"database": "unreachable"` | Same as above, or the database is restarting | Wait a minute; check the database's status page; redeploy. |
| Login works, but after a refresh or a few hours you're logged out | `JWT_SECRET` changed (every change logs everyone out), or the browser blocks storage (private mode) | Set `JWT_SECRET` once and leave it. Don't use a private window for a demo. |
| Login works, then *every* request answers 401 / logs you out at once | The app's saved login was made by a backend with a different `JWT_SECRET` or a database that was replaced | Log out and log in again. If the database was recreated, register again (or use the demo login). |
| Demo login says the number or password is wrong | The demo shop wasn't created | Set `SEED_DEMO_ON_START=true`, redeploy, and look for *SEED_DEMO_ON_START: created the demo shop* in the Logs. |
| The app calls `http://localhost:8000`, or nothing works on the live site | `VITE_API_URL` was missing when Vercel built the app | Add it in Vercel → **Settings → Environment Variables**, then **Redeploy**. |
| Browser console: *Mixed Content* | `VITE_API_URL` starts with `http://` | Use the `https://` Render address and redeploy. |
| Vercel shows 404 on the site, or on reload of a page | **Root Directory** isn't `frontend`, so `vercel.json` isn't used | Vercel → **Settings → General → Root Directory** → `frontend`, then redeploy. |
| Every card says **AI chhara** | No `GROQ_API_KEY`, the key is wrong, or Groq is rate limiting | Set the key on Render. Logs show *Groq rejected GROQ_API_KEY* for a wrong key, or *Groq is busy* for rate limits (that one fixes itself). |
| Logs: *Groq rejected GROQ_MODEL=...* | Groq retired the model | Pick a current model at https://console.groq.com/docs/models, set `GROQ_MODEL`, save. |
