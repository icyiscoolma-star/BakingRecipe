# BakeShift — Authentication & Users Plan

This is your roadmap for adding real user accounts (email/password **and** Google
sign-in) using **Supabase Auth**. You will write all the code yourself — this plan
gives you the architecture, the decisions, the files to touch, and exactly what each
piece needs to do.

Read these three files together:
- **`AUTH_PLAN.md`** (this file) — the big picture and the build order
- **`SUPABASE_AUTH_GUIDE.md`** — what to click in the Supabase dashboard
- **`auth.py`** — the scaffolded code you fill in (function headers + hints)

---

## 1. What we're adding (in plain English)

Right now BakeShift has no idea *who* is using it. Every recipe and modification is
saved into one big shared pile, and `/history` shows **everyone's** recipes to
**everyone**. That's the core problem login solves.

After this work:
- A visitor can **sign up** and **log in** (with email+password or "Sign in with Google").
- Every recipe / modification they create is **tagged with their user id**.
- `/history` only shows **their own** recipes.
- The database itself refuses to hand one user another user's rows (Row Level Security).

---

## 2. Key decisions (and what we chose)

| Decision | Options | Our choice & why |
|---|---|---|
| **Login methods** | email/password, Google OAuth, magic link, GitHub | **Email/password first** (simplest to learn the flow), **then add Google OAuth**. Both go through Supabase. |
| **Where does login happen?** | Supabase-hosted UI vs. our own page | **Our own `/login` page** in Flask. We call the Supabase Python SDK from the server. This keeps everything in your app and teaches you the real flow. |
| **Which Supabase key?** | `anon` key vs. `service_role` key | **`anon` key** (the public one). Combined with Row Level Security, this is the safe, normal choice. The `service_role` key bypasses all security and must never touch the browser. |
| **Where do we store the logged-in session?** | Flask cookie vs. database vs. JWT in JS | **Flask's signed `session` cookie.** We save the Supabase access + refresh tokens and the user's id/email there. Requires a Flask `SECRET_KEY`. |
| **Required or optional login?** | force login vs. allow guests | **Start required** for `/modify`, `/submit`, `/history`, and the chat APIs. (You can loosen this later to allow guest demos.) |
| **How is ownership enforced?** | app-side filtering vs. database RLS | **Both.** Phase 1: app adds `user_id` on insert and filters reads. Phase 2: turn on RLS so the database enforces it even if your code has a bug. Defense in depth. |

---

## 3. How Supabase Auth actually works (the mental model)

Supabase gives you a built-in, hidden table called **`auth.users`**. You never write
to it directly — Supabase manages it. When someone signs up:

1. Supabase creates a row in `auth.users` with a unique **user id** (a UUID).
2. Supabase issues two tokens:
   - **access token** (a JWT) — short-lived (~1 hour), proves "I am this user."
   - **refresh token** — long-lived, used to silently get a new access token.
3. You store those tokens in the Flask session cookie.
4. On later requests, you read the cookie to know who's logged in. When the access
   token expires, you use the refresh token to get a fresh one.

**The two flows you'll implement:**

**A. Email / password (no redirects — easiest):**
```
User submits /login form
  → auth.py calls supabase.auth.sign_in_with_password(email, password)
  → Supabase returns a session (access + refresh token + user)
  → store it in Flask session
  → redirect to home
```

**B. Google OAuth (the "redirect dance" — PKCE flow):**
```
User clicks "Sign in with Google"
  → auth.py calls supabase.auth.sign_in_with_oauth({provider: "google", redirect_to: <our callback>})
  → we redirect the browser to the Google URL Supabase gave us
  → user picks their Google account
  → Google → Supabase → redirects back to OUR /auth/callback?code=XXXX
  → auth.py calls supabase.auth.exchange_code_for_session(code)
  → Supabase returns a session
  → store it in Flask session
  → redirect to home
```

Both flows end the same way: **a Supabase session saved in the Flask cookie.**

---

## 4. Database changes

You'll run this SQL in the Supabase **SQL Editor** (the guide walks you through it).
The idea: add a `user_id` column to the tables that hold user-owned data, pointing at
the built-in `auth.users` table.

```sql
-- Tag recipes and modifications with their owner.
ALTER TABLE recipes       ADD COLUMN user_id UUID REFERENCES auth.users(id);
ALTER TABLE modifications ADD COLUMN user_id UUID REFERENCES auth.users(id);

-- (chat_messages and cookbooks are reached THROUGH a modification, so they inherit
--  ownership. You can add user_id to them later if you want stricter direct rules.)
```

Then **Row Level Security** — see `SUPABASE_AUTH_GUIDE.md` Section 6 for the full
policy SQL. The short version of what the policies say:
- "A user may SELECT/INSERT/UPDATE/DELETE a row only if `row.user_id = auth.uid()`."
- `auth.uid()` is a function Supabase provides that returns the id of whoever's token
  made the request — which is why **reads/writes must carry the user's access token**
  (see `get_authed_supabase()` in `auth.py`).

---

## 5. Files you will create or change

### New files
- **`auth.py`** — already scaffolded for you. A Flask **Blueprint** holding all the auth
  routes (`/login`, `/signup`, `/logout`, `/auth/google`, `/auth/callback`) plus helper
  functions (`current_user`, `login_required`, session helpers, the authed client).
- **`templates/login.html`** — already scaffolded. The login + signup form and the
  "Sign in with Google" button.

### Files you'll edit
- **`app.py`**
  - Add a `SECRET_KEY` so Flask can sign the session cookie:
    ```python
    app.secret_key = os.getenv("FLASK_SECRET_KEY")  # add FLASK_SECRET_KEY to .env
    ```
  - Register the blueprint:
    ```python
    from auth import auth_bp
    app.register_blueprint(auth_bp)
    ```
  - Protect routes with the `@login_required` decorator (import it from `auth`):
    `modify`, `submit`, `history`, `results`, `chat`, `chat_apply`.
  - **Set the owner on insert.** In `submit()`, when you insert into `recipes` and
    `modifications`, add `"user_id": current_user()["id"]`.
  - **Filter reads by owner.** In `history()`, add `.eq("user_id", current_user()["id"])`
    to the query (Phase 1). In `results()` / `chat()`, after fetching, confirm the row's
    `user_id` matches the logged-in user before showing it (don't let someone open
    `/results/<someone-elses-id>`).
- **`templates/base.html`**
  - In the `.nav-links` div, show **"Log in"** when logged out, and the user's email +
    a **"Log out"** link when logged in. (Hint: pass the user into templates — see
    "Make the user available everywhere" below.)
- **`.env`**
  - Add `FLASK_SECRET_KEY=<a long random string>` and confirm `SUPABASE_URL` /
    `SUPABASE_KEY` are the **anon** key (the guide shows where to find it).

### Make the user available in every template (nice-to-have)
So `base.html` can show the right nav on every page without you passing `user=` into
every `render_template`, add a **context processor** in `app.py`:
```python
@app.context_processor
def inject_user():
    from auth import current_user
    return {"current_user": current_user()}
```
Then in templates you can use `{% if current_user %}...{% endif %}`.

---

## 6. Build order (do it in these small, testable steps)

> Same philosophy as the rest of BakeShift: build one slice, test it, then continue.

| Step | Build | How to test |
|---|---|---|
| **0. Dashboard prep** | Follow `SUPABASE_AUTH_GUIDE.md` Sections 1–3: confirm anon key, set Site URL + redirect URLs, enable Email provider. | You can see the Auth settings; no code yet. |
| **1. Plumbing** | Add `FLASK_SECRET_KEY`, register the blueprint, create the (empty-bodied) `auth.py` + `login.html`. App still runs. | `python app.py` starts with no errors. |
| **2. Sign up + log in (email)** | Implement `sign_up_email`, `sign_in_email`, `store_session`, `current_user`, the `/signup` + `/login` routes, and the login form. | Create an account → see it appear in **Authentication → Users** in Supabase. Log out, log back in. |
| **3. Gate the app** | Implement `login_required`, decorate the protected routes, update the navbar. | Logged out → visiting `/modify` redirects to `/login`. Logged in → it works. |
| **4. Tag + filter data** | Run the `ALTER TABLE` SQL. Set `user_id` on insert in `submit()`. Filter `history()` by `user_id`. | Make recipes on two different accounts → each `/history` shows only its own. |
| **5. Google OAuth** | Follow guide Section 4 (Google Cloud + Supabase). Implement `get_oauth_url`, `exchange_code`, the `/auth/google` + `/auth/callback` routes, and the Google button. | Click "Sign in with Google" → pick account → land back logged in. |
| **6. Lock it down with RLS** | Run the RLS policy SQL (guide Section 6). Switch reads/writes to `get_authed_supabase()` so the user's token rides along. | Try to load another user's `/results/<id>` → you get nothing back. |
| **7. Token refresh (polish)** | Implement `refresh_if_needed` so sessions don't die after ~1 hour. | Stay logged in past an hour, or shorten the JWT expiry to test, then load a page — still logged in. |

---

## 7. Common gotchas (read before you debug for an hour)

- **`redirect_to` must be on the allow-list.** Supabase only redirects back to URLs you
  added under **Authentication → URL Configuration → Redirect URLs** (guide Section 3).
  In dev that's `http://127.0.0.1:5000/auth/callback`. A mismatch = silent failure.
- **`127.0.0.1` vs `localhost`.** Pick ONE and use it everywhere (browser URL, Site URL,
  redirect URL). Cookies and OAuth redirects treat them as different sites.
- **Email confirmation.** By default Supabase emails a confirmation link on sign-up. For
  local development you can turn "Confirm email" **off** (guide Section 3) so you can log
  in immediately. Turn it back on before real launch.
- **RLS makes everything disappear.** The moment you enable RLS, every query returns
  nothing **until** you (a) add policies and (b) send the user's token. If your lists go
  empty right after Step 6, that's expected — finish wiring `get_authed_supabase()`.
- **Secret key.** If `FLASK_SECRET_KEY` is missing or changes between restarts, sessions
  won't persist / will log everyone out. Set a fixed value in `.env`.
- **Never expose `service_role`.** It must stay server-side and out of git. Your app uses
  the `anon` key.

---

## 8. What to read next

Open `SUPABASE_AUTH_GUIDE.md` and do Sections 1–3 first (no code). Then open `auth.py`
and start filling in functions following Build Order Step 2.
