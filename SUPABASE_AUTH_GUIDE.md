# Supabase Dashboard Guide — Setting Up Auth for BakeShift

A click-by-click walkthrough of everything you do **inside the Supabase website** to
make login work. Do the sections in order. Code lives in `auth.py`; this file is only
the dashboard.

> Throughout, "your project" = the Supabase project BakeShift already uses (the one
> whose URL/key are in your `.env`). Start at <https://supabase.com/dashboard> and click
> into that project.

---

## Section 1 — Find your keys (confirm `.env` is correct)

1. In your project, click the **gear icon (Project Settings)** in the left sidebar.
2. Click **API**.
3. You'll see:
   - **Project URL** → this is your `SUPABASE_URL`.
   - **Project API keys**:
     - **`anon` `public`** → this is the key BakeShift should use. Confirm your `.env`
       `SUPABASE_KEY` matches this one.
     - **`service_role` `secret`** → ⚠️ **do not use this in the app.** It bypasses all
       security. Never put it in the browser or commit it.
4. ✅ Checkpoint: `.env` has `SUPABASE_URL` and the **anon** key as `SUPABASE_KEY`.

---

## Section 2 — Where the users will live

1. In the left sidebar, click **Authentication** (the little person icon).
2. Click **Users**. Right now it's empty (or just test rows).
3. This is the screen where every account you create will show up. Keep this tab handy —
   it's how you'll verify sign-up worked. You don't change anything here yet.

---

## Section 3 — Configure URLs and the Email provider

### 3a. URL configuration (critical for redirects)
1. **Authentication → URL Configuration** (sometimes under **Authentication → Settings**).
2. **Site URL**: set to `http://127.0.0.1:5000`
   (your local Flask address. Use `127.0.0.1` *or* `localhost` — pick one and be
   consistent everywhere.)
3. **Redirect URLs** → **Add URL**: add `http://127.0.0.1:5000/auth/callback`
   - This is the page Supabase is allowed to send users back to after Google login.
   - When you deploy later, add your real domain's `/auth/callback` here too.
4. Click **Save**.

### 3b. Enable email/password
1. **Authentication → Providers** (or **Sign In / Providers**).
2. Find **Email**. Make sure it's **enabled**.
3. For easier local testing, expand Email and turn **"Confirm email" OFF** for now
   (so new accounts can log in immediately without clicking an email link).
   - ⚠️ Turn this back **ON** before you launch for real.
4. Click **Save**.

✅ Checkpoint: Email provider on, redirect URL added, Site URL set. You can now build
Build-Order Steps 2–4 from `AUTH_PLAN.md` (email login) without touching Google yet.

---

## Section 4 — Enable Google OAuth (do this for Build-Order Step 5)

Google sign-in has two halves: a project in **Google Cloud** and a toggle in
**Supabase**. They hand two values to each other.

### 4a. Get the Supabase callback URL (you'll need it in a second)
1. In Supabase: **Authentication → Providers → Google**.
2. Expand it. Copy the **Callback URL (redirect URI)** it shows you. It looks like:
   `https://<your-project-ref>.supabase.co/auth/v1/callback`
   - Note: this is **Supabase's** callback (Google talks to Supabase). It is *different*
     from your app's `/auth/callback` (Supabase talks to your app).

### 4b. Create Google OAuth credentials
1. Go to <https://console.cloud.google.com/>.
2. Create a project (or pick an existing one) using the project dropdown at the top.
3. Left menu → **APIs & Services → OAuth consent screen**:
   - Choose **External**, click Create.
   - Fill **App name** (e.g. "BakeShift"), your email for support + developer contact.
   - Save and continue through the screens. Under **Test users**, add your own Google
     email (so you can log in while the app is still in "testing" mode).
4. Left menu → **APIs & Services → Credentials → Create Credentials → OAuth client ID**:
   - **Application type**: Web application.
   - **Name**: anything (e.g. "BakeShift Web").
   - **Authorized redirect URIs → Add URI**: paste the **Supabase Callback URL** from
     step 4a (`https://<ref>.supabase.co/auth/v1/callback`).
   - Click **Create**.
5. A popup shows your **Client ID** and **Client secret**. Copy both.

### 4c. Paste the credentials into Supabase
1. Back in Supabase: **Authentication → Providers → Google**.
2. Toggle **Enable Sign in with Google** ON.
3. Paste the **Client ID** and **Client secret** from Google.
4. Click **Save**.

✅ Checkpoint: Google provider enabled with your Client ID/secret, and the Supabase
callback URL is listed in Google's authorized redirect URIs.

---

## Section 5 — Add the `user_id` columns (SQL Editor)

1. Left sidebar → **SQL Editor** → **New query**.
2. Paste and **Run**:
   ```sql
   ALTER TABLE recipes       ADD COLUMN user_id UUID REFERENCES auth.users(id);
   ALTER TABLE modifications ADD COLUMN user_id UUID REFERENCES auth.users(id);
   ```
3. ✅ Checkpoint: Open **Table Editor → recipes** — you should see a new `user_id`
   column (empty for old rows, which is fine).

> Old recipes made before login will have `user_id = NULL`. That's okay — they just
> won't belong to anyone. You can delete them later if you want a clean slate.

---

## Section 6 — Turn on Row Level Security (do this for Build-Order Step 6)

> ⚠️ Do this **after** email login works and you're setting `user_id` on insert
> (Build-Order Step 4). The instant RLS is on, queries return nothing until policies +
> the user's token are in place.

### 6a. Enable RLS on each table
**SQL Editor → New query**, run:
```sql
ALTER TABLE recipes       ENABLE ROW LEVEL SECURITY;
ALTER TABLE modifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
```

### 6b. Add policies
A policy is a rule the database checks on every read/write. `auth.uid()` returns the id
of whoever's access token made the request.

```sql
-- RECIPES: you can only touch rows you own.
CREATE POLICY "own recipes - select" ON recipes
  FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "own recipes - insert" ON recipes
  FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY "own recipes - update" ON recipes
  FOR UPDATE USING (user_id = auth.uid());
CREATE POLICY "own recipes - delete" ON recipes
  FOR DELETE USING (user_id = auth.uid());

-- MODIFICATIONS: same idea.
CREATE POLICY "own modifications - select" ON modifications
  FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "own modifications - insert" ON modifications
  FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY "own modifications - update" ON modifications
  FOR UPDATE USING (user_id = auth.uid());
CREATE POLICY "own modifications - delete" ON modifications
  FOR DELETE USING (user_id = auth.uid());

-- CHAT_MESSAGES: a message is yours if its parent modification is yours.
-- (chat_messages has no user_id; it inherits ownership through modification_id.)
CREATE POLICY "own chat - select" ON chat_messages
  FOR SELECT USING (
    modification_id IN (SELECT id FROM modifications WHERE user_id = auth.uid())
  );
CREATE POLICY "own chat - insert" ON chat_messages
  FOR INSERT WITH CHECK (
    modification_id IN (SELECT id FROM modifications WHERE user_id = auth.uid())
  );
```

### 6c. The catch — your code must send the user's token
With RLS on, `auth.uid()` is only non-null if the request carries the logged-in user's
**access token**. The single global `supabase` client in `app.py` uses the plain anon
key, so `auth.uid()` is null and everything is blocked.

Fix: for user data reads/writes, use a client that has the user's token attached — that's
exactly what `get_authed_supabase()` in `auth.py` is for. Build-Order Step 6 is where you
switch the queries in `submit()`, `history()`, `results()`, and `chat()` over to it.

✅ Checkpoint: Logged in as User A, you see only A's recipes. Trying to open a results
page belonging to User B returns empty.

---

## Section 7 — Verifying as you go

- **Did sign-up work?** → **Authentication → Users**: your new email appears.
- **Did Google work?** → same Users list, the row shows a Google provider / avatar.
- **Is data tagged?** → **Table Editor → recipes**: new rows have a `user_id`.
- **Is RLS protecting you?** → **Authentication → Policies** lists your policies; try
  loading another user's page and confirm you get nothing.
- **Stuck?** → **Logs** (left sidebar) → **Auth Logs** shows failed logins and why.

---

## Quick reference — the four URLs people mix up

| Name | Example | Who uses it |
|---|---|---|
| **Site URL** | `http://127.0.0.1:5000` | Supabase, as the default place to send users |
| **Your app callback** | `http://127.0.0.1:5000/auth/callback` | Supabase → your Flask app (must be in Redirect URLs) |
| **Supabase callback** | `https://<ref>.supabase.co/auth/v1/callback` | Google → Supabase (must be in Google's redirect URIs) |
| **Project URL** | `https://<ref>.supabase.co` | your `.env` `SUPABASE_URL` |
