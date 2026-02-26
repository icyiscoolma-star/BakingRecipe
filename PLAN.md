# BakeShift - Implementation Plan

## Context

We're building a baking recipe modification website from a blank repo. The app helps users modify recipes based on allergies, taste preferences, ingredient limitations, and equipment limitations. Built with an 8th grader using Python Flask + Supabase. AI integration will be added later — for now we use placeholders. We build feature by feature: frontend first, then backend.

## App Flow (3 Pages)

1. **Home Page** — Two big buttons: "Upload a Recipe" / "Create a Recipe"
2. **Modification Page** — Recipe input (upload or create mode) + modification criteria form
3. **Results Page** — Modified recipe (top) → Criteria summary (middle) → Original recipe (bottom), with an AI chat panel on the right side

---

## Project Setup (Do First)

### Folder Structure
```
BakingRecipe/
├── .env                    # Supabase keys (never commit)
├── .gitignore
├── requirements.txt
├── app.py                  # All Flask routes
├── templates/
│   ├── base.html           # Shared layout (nav, footer, CSS)
│   ├── home.html           # Page 1
│   ├── modify.html         # Page 2
│   └── results.html        # Page 3
├── static/
│   ├── css/style.css       # All styles
│   └── js/
│       ├── modify.js       # Form validation for Page 2
│       └── chat.js         # Chat interface for Page 3
└── uploads/                # Uploaded recipe files
```

### Steps
1. Create Python virtual environment: `python3 -m venv .venv && source .venv/bin/activate`
2. Create `requirements.txt` with: `flask==3.1.0`, `supabase==2.13.0`, `python-dotenv==1.1.0`
3. `pip install -r requirements.txt`
4. Create `.env` with `SUPABASE_URL` and `SUPABASE_KEY` (from Supabase dashboard)
5. Create `.gitignore` (exclude `.venv/`, `__pycache__/`, `.env`, `uploads/`)
6. Create Supabase tables (SQL below)
7. Create directory structure: `mkdir -p templates static/css static/js static/images uploads`

### Supabase Tables
```sql
CREATE TABLE recipes (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    recipe_name TEXT NOT NULL,
    ingredients TEXT,
    instructions TEXT,
    is_original BOOLEAN DEFAULT TRUE,
    original_recipe_id UUID REFERENCES recipes(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE modifications (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    original_recipe_id UUID REFERENCES recipes(id) NOT NULL,
    modified_recipe_id UUID REFERENCES recipes(id),
    allergies TEXT,
    taste_preferences TEXT,
    ingredient_limitations TEXT,
    equipment_limitations TEXT,
    source_type TEXT NOT NULL CHECK (source_type IN ('upload', 'create')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE chat_messages (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    modification_id UUID REFERENCES modifications(id) NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## Feature 1: Home Page

**Files:** `app.py`, `templates/base.html`, `templates/home.html`, `static/css/style.css`

### Frontend
- `base.html` — Shared layout with nav bar ("BakeShift" brand link), `{% block content %}` slot, footer, CSS link
- `home.html` — Extends base. Hero section with heading + tagline. Two clickable cards side-by-side: "Upload a Recipe" links to `/modify?mode=upload`, "Create a Recipe" links to `/modify?mode=create`
- `style.css` — Warm baking palette (cream background `#fdf6ee`, dark brown text `#3e2723`, brown navbar `#5d4037`). Cards with hover lift animation

### Backend
- `app.py` — Initialize Flask app, load `.env`, create Supabase client. Single route `GET /` renders `home.html`

### Test
- `python app.py` → visit `http://127.0.0.1:5000/` → see landing page with two cards
- Clicking cards gives 404 (expected — Page 2 doesn't exist yet)

---

## Feature 2: Modification Request Page

**Files:** `templates/modify.html`, `static/js/modify.js`, `static/css/style.css` (append), `app.py` (add routes)

### Frontend
- `modify.html` — Extends base. Receives `mode` variable from Flask
  - **Upload mode:** Large textarea to paste recipe + file upload input (`.txt`, images)
  - **Create mode:** Structured form — recipe name, ingredients (one per line), instructions
  - **Shared section (both modes):** Modification criteria with checkboxes + text inputs:
    - Allergies: nut-free, dairy-free, gluten-free, egg-free + "other" text field
    - Taste: less sweet, more savory, less rich, more chocolatey + "other" text field
    - Ingredient limitations: free text field
    - Equipment: no stand mixer, no oven, no food processor + "other" text field
  - Submit button → `POST /submit`
- `modify.js` — Validates that upload mode has either pasted text or a file before submitting

### Backend (2 routes)
- `GET /modify` — Reads `?mode=` query param, renders `modify.html` with mode variable
- `POST /submit` — Collects all form data, combines checkbox values with "other" text fields, saves original recipe to `recipes` table, creates placeholder modified recipe, saves modification request to `modifications` table, redirects to `/results/<modification_id>`

### Test
- Full flow: Home → click card → see correct form mode → fill out → submit
- Check Supabase dashboard for new rows in `recipes` and `modifications`
- Redirect to results page gives 404 (expected — Page 3 doesn't exist yet)

---

## Feature 3: Recipe Results Page

**Files:** `templates/results.html`, `static/css/style.css` (append), `app.py` (add route)

### Frontend
- `results.html` — Extends base. Flex layout: main content (left/center) + chat panel (right)
  - **Main content (3 stacked cards):**
    1. Modified recipe (green left border) — name, ingredients, instructions
    2. Criteria summary (orange left border) — lists active modification criteria
    3. Original recipe (brown left border) — name, ingredients, instructions
  - **Chat panel (right sidebar):** Sticky panel with welcome message, message history area, input + send button
  - Responsive: on mobile (<768px), chat stacks below recipe cards

### Backend
- `GET /results/<modification_id>` — Queries Supabase for the modification record, original recipe, modified recipe, and chat history. Passes all to template.

### Test
- Complete end-to-end flow: Home → Create Recipe → fill form → submit → see results page
- All three cards should display with correct data
- Chat panel visible on right with welcome message
- Resize browser narrow — chat should stack below

---

## Feature 4: AI Chat Interface

**Files:** `static/js/chat.js`, `app.py` (add API route), `templates/results.html` (add chat history loop)

### Frontend
- `chat.js` — On form submit: prevent page reload, show user message bubble immediately, `POST /api/chat` with message + modification_id via fetch, show assistant reply bubble, auto-scroll chat window
- `results.html` update — Loop through `chat_messages` from server to restore history on page load

### Backend
- `POST /api/chat` (JSON API) — Receives `{modification_id, message}`, saves user message to `chat_messages` table, generates placeholder reply (echoes back a canned response), saves assistant reply, returns `{reply: "..."}` as JSON
  - **This is where AI gets swapped in later** — only the reply generation logic changes

### Test
- On results page, type message → see it appear as dark bubble on right
- Placeholder response appears as light bubble on left
- Send multiple messages → chat scrolls automatically
- Refresh page → all messages persist (loaded from Supabase)
- Check `chat_messages` table in Supabase dashboard

---

## Build Order Summary

| Step | Build | Testable Result |
|------|-------|----------------|
| Setup | Venv, packages, .env, Supabase tables, folders | `python app.py` runs |
| Feature 1 | Home page (HTML/CSS → Flask route) | Landing page with two cards |
| Feature 2 | Modify page (HTML/CSS/JS → Flask routes + Supabase) | Form submits, data in Supabase |
| Feature 3 | Results page (HTML/CSS → Flask route + Supabase reads) | End-to-end flow works |
| Feature 4 | Chat (JS → Flask API + Supabase chat storage) | Chat sends, displays, persists |

## Where AI Gets Added Later

Only 2 places change when real AI is added:
1. `app.py` `submit_modification()` — Replace placeholder modified recipe with AI-generated result
2. `app.py` `chat()` — Replace canned reply with AI API call

Everything else (frontend, database, routing) stays the same.

## Verification

After each feature, run `python app.py` and test the flow in the browser. After all 4 features:
1. Start at home page → click "Create a Recipe"
2. Fill in recipe + modification criteria → click "Modify Recipe"
3. See results page with all 3 cards and chat panel
4. Send chat messages → see them appear and persist on refresh
5. Confirm all data in Supabase dashboard (recipes, modifications, chat_messages tables)
