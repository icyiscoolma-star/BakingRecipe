"""
auth.py — Authentication & user sessions for BakeShift.

This module is a SCAFFOLD. Every function below has a header, a docstring describing
exactly what it should do, and step-by-step hints — but NO implementation. You write
the bodies yourself (that's the point). Follow the Build Order in AUTH_PLAN.md.

How this connects to the rest of the app:
  - app.py registers this blueprint:    app.register_blueprint(auth_bp)
  - app.py imports helpers from here:    from auth import login_required, current_user
  - the routes here render templates/login.html

Key SDK calls you'll use (supabase-py v2 — the version in requirements.txt):
  supabase.auth.sign_up({"email": ..., "password": ...})
  supabase.auth.sign_in_with_password({"email": ..., "password": ...})
  supabase.auth.sign_in_with_oauth({"provider": "google", "options": {"redirect_to": ...}})
  supabase.auth.exchange_code_for_session({"auth_code": ...})
  supabase.auth.refresh_session(refresh_token)
Each returns an object with `.session` (has .access_token, .refresh_token, .expires_at)
and `.user` (has .id, .email). Print one once to see its shape.
"""

import os
from functools import wraps

from flask import (
    Blueprint, render_template, request, redirect, url_for, session, flash
)
from supabase import create_client


# The blueprint groups all auth routes. Register it in app.py.
auth_bp = Blueprint("auth", __name__)


# ---------------------------------------------------------------------------
# Supabase clients
# ---------------------------------------------------------------------------

def get_supabase():
    """Return a plain Supabase client built from the anon key in .env.

    Use this for auth calls (sign up / sign in / oauth) where there is no logged-in
    user yet.

    Hints:
      - Read SUPABASE_URL and SUPABASE_KEY from os.getenv (same as app.py does).
      - Return create_client(url, key).
      - Optional: guard against missing env vars and raise a clear error.
    """
    raise NotImplementedError


def get_authed_supabase(access_token, refresh_token=None):
    """Return a Supabase client that carries the logged-in user's access token.

    This is the one you use for reading/writing the user's recipes once Row Level
    Security is ON, so that auth.uid() inside the DB policies resolves to this user.

    Hints:
      - Start from a normal client: client = get_supabase().
      - Attach the user's session so requests are made "as" them. In supabase-py v2:
            client.auth.set_session(access_token, refresh_token)
        (set_session needs both tokens; pass the refresh token you stored.)
      - Return the client.
      - You'll call this in app.py's submit()/history()/results()/chat() during
        Build-Order Step 6.
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Flask session helpers (where we remember who's logged in)
# ---------------------------------------------------------------------------

def store_session(auth_response):
    """Save the Supabase session into Flask's signed cookie.

    Called after a successful sign-in/sign-up/oauth exchange.

    Hints:
      - auth_response.session has: access_token, refresh_token, expires_at.
      - auth_response.user has: id, email.
      - Write the pieces you need into Flask's `session` dict, e.g.:
            session["access_token"]  = ...
            session["refresh_token"] = ...
            session["expires_at"]    = ...
            session["user"] = {"id": ..., "email": ...}
      - Don't store the whole object — just the plain strings/ids (cookies hold text).
    """
    raise NotImplementedError


def clear_session():
    """Forget the logged-in user (logout).

    Hints:
      - session.clear() wipes everything, or pop the specific keys you set.
      - Optional: also call get_supabase().auth.sign_out() to invalidate server-side.
    """
    raise NotImplementedError


def current_user():
    """Return the logged-in user as a dict, or None if nobody is logged in.

    This is the function app.py and templates lean on the most.

    Hints:
      - Return session.get("user")  (the dict you saved in store_session).
      - Returns None automatically when not logged in — which is what callers expect.
      - Keep this cheap; it runs on basically every request.
    """
    raise NotImplementedError


def refresh_if_needed():
    """Keep the session alive by refreshing an expired/expiring access token.

    Build-Order Step 7 (polish). Skip until email + Google login both work.

    Hints:
      - If there's no session in the cookie, just return (nothing to do).
      - Compare session["expires_at"] against the current time. (You'll need to import
        time; expires_at is usually a Unix timestamp.)
      - If it's expired or within ~60s of expiring:
            resp = get_supabase().auth.refresh_session(session["refresh_token"])
            store_session(resp)   # save the fresh tokens
      - Wrap in try/except: if refresh fails, clear_session() so they re-log in cleanly.
      - You can call this from a @auth_bp.before_app_request hook so it runs everywhere.
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# The @login_required decorator
# ---------------------------------------------------------------------------

def login_required(view):
    """Decorator that blocks a route unless the user is logged in.

    Usage in app.py:
        from auth import login_required

        @app.route("/modify")
        @login_required
        def modify():
            ...

    Hints:
      - Use @wraps(view) on the inner function so Flask keeps the original name.
      - Inside the wrapper:
            if current_user() is None:
                # optional: flash("Please log in first.")
                return redirect(url_for("auth.login"))   # 'auth.login' = blueprint route
            return view(*args, **kwargs)
      - Return the wrapper from login_required.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        # TODO: implement the check described above.
        raise NotImplementedError
    return wrapped


# ---------------------------------------------------------------------------
# Auth actions (called by the routes below)
# ---------------------------------------------------------------------------

def sign_up_email(email, password):
    """Create a new account with email + password. Return the Supabase auth response.

    Hints:
      - client = get_supabase()
      - resp = client.auth.sign_up({"email": email, "password": password})
      - Return resp (the route decides what to do with it).
      - If "Confirm email" is ON in Supabase, resp may have a user but no session yet
        (they must click the email link first). With it OFF (dev), you usually get a
        session immediately. Handle both: see the /signup route hints.
      - Let exceptions bubble up, or catch and return None — pick one and be consistent.
    """
    raise NotImplementedError


def sign_in_email(email, password):
    """Log in with email + password. Return the Supabase auth response.

    Hints:
      - client = get_supabase()
      - resp = client.auth.sign_in_with_password({"email": email, "password": password})
      - On success resp.session and resp.user are populated.
      - Wrong password / unknown user raises an exception — catch it in the route and
        show a friendly "invalid login" message.
    """
    raise NotImplementedError


def get_oauth_url(provider, redirect_to):
    """Ask Supabase for the provider login URL (e.g. Google). Return that URL string.

    Hints:
      - client = get_supabase()
      - resp = client.auth.sign_in_with_oauth({
            "provider": provider,                       # "google"
            "options": {"redirect_to": redirect_to},    # your /auth/callback absolute URL
        })
      - The URL to send the browser to is resp.url.
      - Return resp.url.
    """
    raise NotImplementedError


def exchange_code(code):
    """Exchange the ?code=... that Google/Supabase sent back for a real session.

    Hints:
      - client = get_supabase()
      - resp = client.auth.exchange_code_for_session({"auth_code": code})
      - Return resp (has .session and .user, just like sign-in).
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Show the login page (GET) and handle an email/password login (POST).

    Hints:
      GET:
        - return render_template("login.html")
      POST:
        - email = request.form.get("email", "").strip()
        - password = request.form.get("password", "")
        - try: resp = sign_in_email(email, password)
          except: flash an error and re-render login.html.
        - if resp has a session:
              store_session(resp)
              return redirect(url_for("home"))   # 'home' is the route in app.py
          else:
              flash("Login failed") and re-render.
    """
    raise NotImplementedError


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    """Show the signup form (GET) and create an account (POST).

    You can reuse login.html for both (one template, two forms) or make signup.html.

    Hints:
      GET:
        - render the signup form.
      POST:
        - read email + password from request.form.
        - resp = sign_up_email(email, password)
        - If you got a session back (email confirmation OFF): store_session(resp) and
          redirect to home — they're logged in.
        - If you got a user but NO session (email confirmation ON): flash "Check your
          email to confirm your account" and redirect to /login.
    """
    raise NotImplementedError


@auth_bp.route("/logout")
def logout():
    """Log the user out and send them home.

    Hints:
      - clear_session()
      - return redirect(url_for("home"))
    """
    raise NotImplementedError


@auth_bp.route("/auth/google")
def google_login():
    """Kick off Google sign-in by redirecting to the Supabase/Google URL.

    Hints:
      - Build the absolute callback URL for THIS app:
            redirect_to = url_for("auth.auth_callback", _external=True)
        (_external=True makes it a full http://... URL, which OAuth requires.)
        It must match what you put in Supabase's Redirect URLs (guide Section 3a).
      - url = get_oauth_url("google", redirect_to)
      - return redirect(url)
    """
    raise NotImplementedError


@auth_bp.route("/auth/callback")
def auth_callback():
    """Where Google/Supabase send the user back after they approve sign-in.

    Hints:
      - code = request.args.get("code")
      - if not code: flash an error, redirect to /login.
      - try:
            resp = exchange_code(code)
            store_session(resp)
            return redirect(url_for("home"))
        except: flash "Google sign-in failed", redirect to /login.
      - Tip: if this 'silently' fails, 99% of the time the callback URL isn't in
        Supabase's Redirect URLs list, or 127.0.0.1 vs localhost don't match.
    """
    raise NotImplementedError
