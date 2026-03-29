# BakeShift - Implementation Plan

## Context

We're building a baking recipe modification website from a blank repo. The app helps users modify recipes based on allergies, taste preferences, ingredient limitations, and equipment limitations. Built with an 8th grader using Python Flask + Supabase. AI is powered by the Claude API (Anthropic) using the user's Max plan API key. We build feature by feature: frontend first, then backend.

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
2. Create `requirements.txt` with: `flask==3.1.0`, `supabase==2.13.0`, `python-dotenv==1.1.0`, `anthropic`
3. `pip install -r requirements.txt`
4. Create `.env` with `SUPABASE_URL`, `SUPABASE_KEY` (from Supabase dashboard), and `ANTHROPIC_API_KEY` (from console.anthropic.com)
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
- `home.html` — Extends base. Hero section with heading + tagline. Two large clickable cards side-by-side (`.card-large` — 380px wide, 3.5rem padding, oversized icons and headings): "Upload a Recipe" links to `/modify?mode=upload`, "Create a Recipe" links to `/modify?mode=create`
- `style.css` — Warm baking palette (cream background `#fdf6ee`, dark brown text `#3e2723`, brown navbar `#5d4037`). Large cards with hover lift animation. Cards scale down to full-width on mobile (<768px)

### Backend
- `app.py` — Initialize Flask app, load `.env`, create Supabase client. Single route `GET /` renders `home.html`

### Test
- `python app.py` → visit `http://127.0.0.1:5000/` → see landing page with two cards
- Clicking cards gives 404 (expected — Page 2 doesn't exist yet)

---

## Feature 2: Modification Request Page (Two-Screen Design)

**Files:** `templates/modify.html`, `static/js/modify.js`, `static/css/style.css` (append), `app.py` (add routes)

### Frontend
- `modify.html` — Extends base. Uses Jinja `{% if mode == 'upload' %}` / `{% else %}` for two layouts:

  **Upload mode (`/modify?mode=upload`):**
  - Page title: "Upload a Recipe"
  - Large recipe preview area with two input options:
    - Textarea to paste recipe text
    - File upload button (accepts `.txt` and images) with a preview area showing uploaded content

  **Create mode (`/modify?mode=create`):**
  - Page title: "Create a Recipe"
  - Two-row layout:
    - **Top row (full width):** "Type It In" — large textarea for manually typing a recipe
    - **Bottom row (two columns, 1fr 1fr):** "Paste a URL" (text input + Fetch button + preview area) | "Upload a Photo" (file upload + image preview)
  - Rows stack to single column below 768px

  **Shared Recipe Criteria section (both modes):**
  - Allergies: checkboxes (nut-free, dairy-free, gluten-free, egg-free) + "other" text field
  - Taste preferences: checkboxes (less sweet, more savory, less rich, more chocolatey) + "other" text field
  - Ingredient limitations: free text field
  - Equipment limitations: checkboxes (no stand mixer, no oven, no food processor) + "other" text field
  - Submit button → `POST /submit`

- `modify.js` — Upload mode: validate pasted text OR uploaded file. Create mode: validate at least one input method has content. URL preview via `POST /api/fetch-url`. File upload image/text preview.

### Backend (2 routes)
- `GET /modify` — Reads `?mode=` query param, renders `modify.html` with mode variable
- `POST /api/fetch-url` — Receives a URL, returns placeholder JSON (AI extraction added later)

### Test
- Home → "Upload a Recipe" → see title, paste/upload area with preview, criteria section
- Home → "Create a Recipe" → see title, two-row layout (type on top, URL + photo below), criteria section
- Test file upload preview in both modes
- Test URL fetch preview on create screen
- Resize below 768px → columns stack vertically
- Submit button visible and styled on both screens

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

## Feature 5: AI Recipe Modification (Claude API)

**Files:** `app.py` (update `submit()` route + add helper), `requirements.txt` (add `anthropic`)

### Setup
- Add `ANTHROPIC_API_KEY` to `.env`
- `pip install anthropic`
- Initialize the Anthropic client in `app.py` alongside the Supabase client

### Backend — Update `POST /submit`
- After collecting the original recipe + criteria, call the Claude API to generate the modified recipe
- **System prompt:** You are a professional baker and recipe developer. The user will give you a recipe and modification criteria. Return a modified version of the recipe that satisfies all the criteria. Format your response as: recipe name on the first line, then "## Ingredients" section, then "## Instructions" section. Keep the same general structure as the original recipe.
- **User message:** Include the original recipe text + all criteria (allergies, taste, ingredient limitations, equipment limitations)
- **Model:** `claude-sonnet-4-20250514` (fast, cost-effective for recipe tasks)
- Parse Claude's response to extract recipe name, ingredients, and instructions
- Save the AI-generated modified recipe to the `recipes` table (replacing the old placeholder text)
- If the API call fails, fall back to the placeholder text so the app doesn't break

### Frontend — Update `POST /api/fetch-url`
- When user pastes a URL on the Create screen and clicks "Fetch", send the URL to the backend
- Backend calls Claude API with the URL text and asks it to extract the recipe (name, ingredients, instructions) from the page content
- Return the extracted recipe text to the frontend preview area
- **Note:** We are not actually fetching the URL content (that requires additional libraries). For now, Claude receives just the URL and returns a message explaining this. Full URL scraping can be added later.

### Test
- Submit a recipe with criteria → results page shows an AI-modified recipe (not placeholder text)
- Ingredients and instructions should reflect the requested modifications (e.g., dairy-free substitutions)
- If `ANTHROPIC_API_KEY` is missing, app still works with placeholder text

---

## Feature 6: AI Chat on Results Page (Claude API)

**Files:** `app.py` (update `chat()` route)

### Backend — Update `POST /api/chat`
- Replace the canned placeholder reply with a Claude API call
- **System prompt:** You are a helpful baking assistant. The user is looking at a modified recipe. Here is the context: [include original recipe, modified recipe, and modification criteria]. Help them with follow-up questions — they might ask for further tweaks, substitution ideas, baking tips, or explanations of why a change was made. Keep responses concise and friendly.
- **User message:** The chat message from the user
- **Conversation history:** Load all previous `chat_messages` for this `modification_id` from Supabase and include them as prior messages in the Claude API call, so the conversation has full context
- **Model:** `claude-sonnet-4-20250514`
- Save both user message and Claude's reply to `chat_messages` table (already implemented)
- If the API call fails, return a friendly error message instead of crashing

### Test
- On results page, ask "Why did you substitute almond milk?" → get a context-aware answer referencing the dairy-free criteria
- Ask a follow-up → Claude remembers the conversation
- Refresh page → all messages persist and Claude still has context on next message
- If API key is missing, chat returns a friendly fallback message

---

---

## Feature 7: Recipe History Dashboard

**Files:** `templates/history.html` (new), `static/css/style.css` (append), `app.py` (add route)

### Frontend
- `history.html` — Extends base. Grid of recipe cards showing all past modifications
  - Each card shows: original recipe name, modification date, dietary tags (from criteria), and a link to the results page
  - Search/filter bar to filter by recipe name or dietary tags
  - Empty state message if no history exists

### Backend
- `GET /history` — Queries Supabase `modifications` table joined with `recipes`, ordered by `created_at` descending. Passes list to template.

### Navigation
- Add "History" link to the navbar in `base.html`

### Test
- Submit a few recipes → visit `/history` → see all past modifications listed
- Click a card → navigate to that recipe's results page

---

## Feature 8: Print / Export Recipe

**Files:** `static/css/style.css` (append print styles), `templates/results.html` (add button), `static/js/results.js` (new, optional)

### Frontend
- Add a "Print Recipe" button at the top of the results main content area
- CSS `@media print` stylesheet that:
  - Hides navbar, footer, chat panel, and print button
  - Formats the modified recipe card as a clean, single-column cookbook-style layout
  - Uses readable serif font and appropriate margins for paper

### Test
- Click "Print Recipe" → browser print dialog opens with a clean recipe layout
- Chat panel and navigation are not visible in the print preview

---

## Feature 9: Recipe Scaling

**Files:** `templates/results.html` (add scaling controls), `static/js/results.js` (new or extend), `static/css/style.css` (append)

### Frontend
- Add a scaling selector (0.5x, 1x, 2x, 3x) above the modified recipe card
- When user selects a multiplier, JavaScript parses ingredient quantities (numbers, fractions) and multiplies them
- Display the scaled ingredients inline, with the original quantities shown in parentheses
- Instructions remain unchanged (only ingredients scale)

### Test
- Select 2x → "1 cup butter" becomes "2 cups butter"
- Select 0.5x → "2 eggs" becomes "1 egg"
- Switch back to 1x → original quantities restored

---

## Feature 10: Share Recipe

**Files:** `app.py` (add route), `templates/results.html` (add share button), `static/js/results.js` (extend)

### Frontend
- Add a "Share" button on the results page
- Clicking it copies the results page URL to the clipboard with a toast notification: "Link copied!"

### Backend
- Results pages are already accessible via `/results/<modification_id>` — no new route needed, just ensure the page works for anyone with the link

### Test
- Click "Share" → URL copied to clipboard → paste it in a new tab → same results page loads

---

## Feature 11: Favorites / Save Recipes

**Files:** `app.py` (add routes), `templates/results.html` (add favorite button), `templates/history.html` (add filter), `static/css/style.css` (append)

### Supabase
- Add a `is_favorite` boolean column to the `modifications` table:
  ```sql
  ALTER TABLE modifications ADD COLUMN is_favorite BOOLEAN DEFAULT FALSE;
  ```

### Frontend
- Add a heart/star toggle button on the results page
- On the history page, add a "Favorites" filter toggle to show only favorited recipes

### Backend
- `POST /api/favorite` — Receives `{modification_id}`, toggles `is_favorite` in Supabase
- Update `/history` route to support `?filter=favorites` query param

### Test
- Click the favorite button → heart fills in → refresh → still favorited
- Go to history → filter by favorites → only favorited recipes appear

---

## Feature 12: Dietary Presets

**Files:** `templates/modify.html` (add preset buttons), `static/js/modify.js` (extend), `static/css/style.css` (append)

### Frontend
- Add a row of preset buttons above the criteria section: "Vegan", "Keto", "Paleo", "Dairy-Free", "Nut-Free"
- Clicking a preset auto-checks the relevant checkboxes and fills in relevant text fields:
  - **Vegan:** dairy-free, egg-free + ingredient limitation "no animal products"
  - **Keto:** less sweet + ingredient limitation "low carb, no sugar, no flour"
  - **Paleo:** gluten-free + ingredient limitation "no refined sugar, no dairy, no grains"
  - **Dairy-Free:** dairy-free checkbox
  - **Nut-Free:** nut-free checkbox
- Clicking the same preset again deselects it (toggle behavior)
- Multiple presets can be combined

### Test
- Click "Vegan" → dairy-free and egg-free checked, ingredient limitation filled
- Click "Keto" additionally → less sweet also checked
- Click "Vegan" again → those specific selections removed

---

## Feature 13: Side-by-Side Recipe Diff

**Files:** `templates/results.html` (add diff view toggle), `static/js/results.js` (extend), `static/css/style.css` (append)

### Frontend
- Add a "Show Changes" toggle button on the results page
- When toggled on, display the original and modified recipes side-by-side in a two-column layout
- Highlight differences:
  - **Green background** for added/changed ingredients or steps in the modified version
  - **Red strikethrough** for removed/replaced items in the original version
- JavaScript performs a simple line-by-line comparison between original and modified ingredients/instructions

### Test
- Toggle "Show Changes" → see side-by-side view with highlighted differences
- Toggle off → return to normal stacked card view
- Substituted ingredients should appear red (original) / green (modified)

---

## Feature 14: AI Recipe Image Generation

**Files:** `app.py` (add route), `templates/results.html` (add image area), `static/css/style.css` (append)

### Frontend
- Add a "Generate Photo" button on the modified recipe card
- When clicked, shows a loading animation, then displays the AI-generated image of the recipe

### Backend
- `POST /api/generate-image` — Receives `{modification_id}`, builds a prompt from the modified recipe name and ingredients, calls an image generation API, returns the image URL
- **Note:** This requires an image generation API (e.g., DALL-E, Stability AI). Implementation details depend on which service is chosen. Can start as a placeholder that returns a stock baking image.

### Test
- Click "Generate Photo" → loading animation → image appears above the recipe
- Image should visually represent the modified recipe

---

## Design 1: Custom Typography

**Files:** `templates/base.html` (add Google Fonts link), `static/css/style.css` (update font rules)

### Implementation
- Add Google Fonts link in `base.html` `<head>`: Playfair Display (headings) + Inter (body text)
- Update CSS:
  - `body` font-family → `'Inter', sans-serif`
  - `h1, h2, h3` font-family → `'Playfair Display', serif`
  - Adjust font sizes and letter-spacing for the new fonts
  - Recipe content (ingredients, instructions) uses Inter for readability

### Test
- All pages show serif headings and clean sans-serif body text
- Recipe content is easy to read at all sizes

---

## Design 2: Illustrated SVG Icons

**Files:** `static/images/` (add SVG files), `templates/home.html` (replace emoji), `static/css/style.css` (update)

### Implementation
- Create or source hand-drawn style SVG icons: whisk (upload), rolling pin (create), oven, mixing bowl, timer
- Replace emoji card icons on the home page with `<img>` tags pointing to SVGs
- Add SVG icons to section headers on the modify and results pages
- Style icons with CSS (size, color tinting via `filter` or `fill`)

### Test
- Home page cards show illustrated icons instead of emoji
- Icons scale correctly on mobile

---

## Design 3: Animated Transitions

**Files:** `static/css/style.css` (append animations), `static/js/transitions.js` (new, optional)

### Implementation
- **Page entrance:** Cards and sections fade-in and slide-up on page load using CSS `@keyframes` and `animation`
- **Scroll animations:** Recipe cards on the results page animate in as user scrolls using `IntersectionObserver` in JS
- **Hover effects:** Enhanced card hover with smooth shadow growth and slight rotation
- **Form interactions:** Smooth expand/collapse on criteria fieldsets
- Keep animations subtle (200-400ms) — enhance, don't distract

### Test
- Navigate between pages → content fades/slides in smoothly
- Scroll down results page → cards animate into view
- Hover cards → smooth shadow and lift effect

---

## Design 4: Dietary Tag Badges

**Files:** `static/css/style.css` (append badge styles), `templates/results.html` (add badges), `templates/history.html` (add badges)

### Implementation
- Color-coded pill badges displayed on recipe cards:
  - Green → vegan / dairy-free
  - Blue → gluten-free
  - Orange → nut-free
  - Purple → keto
  - Red → egg-free
- Parse the modification criteria and generate the appropriate badges
- Display on both the results page (criteria card) and history page (recipe cards)

### Test
- Submit a dairy-free, gluten-free recipe → see green and blue badges on results page
- History page shows matching badges on each card

---

## Design 5: Dark Mode

**Files:** `static/css/style.css` (add dark mode variables and rules), `templates/base.html` (add toggle button), `static/js/theme.js` (new)

### Implementation
- Define CSS custom properties for all colors (background, text, card, border, accent)
- Add a `[data-theme="dark"]` selector that overrides all color variables:
  - Background: `#1a1a2e` → `#16213e`
  - Text: `#e0d6cc`
  - Cards: `#1f2937`
  - Navbar: `#0f172a`
  - Accents: warm amber tones
- Add a sun/moon toggle button in the navbar
- `theme.js` — Toggles `data-theme` attribute on `<html>`, saves preference to `localStorage`

### Test
- Click toggle → entire app switches to dark palette
- Refresh page → dark mode persists
- All text remains readable, cards have clear borders

---

## Design 6: Baking Loading Animation

**Files:** `static/css/style.css` (append loader styles), `templates/modify.html` (add loader overlay), `static/js/modify.js` (extend)

### Implementation
- When the user clicks "Modify My Recipe", show a full-page overlay with:
  - A CSS-animated rolling pin or rising dough illustration
  - Rotating text messages: "Preheating the oven...", "Mixing ingredients...", "Letting it rise...", "Almost ready..."
- The overlay stays visible until the server redirects to the results page
- Pure CSS animation — no external libraries

### Test
- Click submit → see baking-themed loading animation
- Animation displays until results page loads
- Messages rotate every 2-3 seconds

---

## Design 7: Texture & Depth

**Files:** `static/css/style.css` (update), `static/images/` (add texture images, optional)

### Implementation
- Add subtle paper/parchment texture to the page background using a CSS repeating pattern or a light image overlay
- Layered card shadows: cards appear to float above the textured background with multi-layer `box-shadow`
- Criteria section fieldsets have a slightly inset appearance
- Buttons have a pressed/raised 3D effect using `box-shadow` and active state transforms
- Keep it subtle — texture should be barely noticeable, not distracting

### Test
- Background has a warm, tactile feel rather than flat color
- Cards appear layered and elevated
- Buttons feel clickable with depth cues

---

## Design 8: Typography Hierarchy & Cookbook Styling

**Files:** `static/css/style.css` (update)

### Implementation
- Increase heading sizes: page titles 2.5-3rem, section headings 1.5-1.8rem
- Add generous spacing: more padding in cards, more margin between sections
- Recipe content styled like a cookbook page:
  - Ingredients displayed as a clean bulleted list with increased line-height (1.8)
  - Instructions displayed as numbered steps with each step having extra bottom margin
  - Subtle left border or indent on recipe content areas
- Pull quotes or highlighted tips from AI chat styled with a decorative left border and italic text

### Test
- Results page feels like reading a real cookbook
- Clear visual hierarchy — eyes naturally flow from title → ingredients → instructions
- Comfortable reading experience with no cramped text

---

## Design 9: Mobile Polish

**Files:** `static/css/style.css` (update responsive rules), `templates/base.html` (update nav)

### Implementation
- **Bottom navigation on mobile (<768px):** Fixed bottom bar with 3 icons — Home, History, Theme toggle
- **Touch-friendly inputs:** Increase checkbox/radio tap targets to 44x44px minimum
- **Swipeable results cards:** On mobile, allow horizontal swiping between modified/criteria/original cards
- **Full-width buttons:** All action buttons stretch to full width on mobile
- **Collapsible criteria section:** On mobile, criteria fieldsets start collapsed with tap-to-expand
- **Safe area support:** Respect `env(safe-area-inset-bottom)` for notched devices

### Test
- View on mobile → bottom nav appears, top nav simplifies
- Tap checkboxes easily with thumb
- Swipe between recipe cards on results page
- All content readable without horizontal scrolling

---

## Design 10: Micro-interactions

**Files:** `static/css/style.css` (append), `static/js/interactions.js` (new)

### Implementation
- **Checkbox animations:** Custom styled checkboxes with a satisfying checkmark draw animation on check
- **Button ripple effect:** Material-style ripple on click for all buttons using CSS pseudo-elements
- **Toast notifications:** Slide-in notification bar for actions like "Recipe saved", "Link copied", "Message sent"
- **Input focus glow:** Warm amber glow on text inputs and textareas when focused
- **Send button pulse:** Chat send button subtly pulses when there's text in the input
- All animations use CSS transitions/keyframes — no external libraries

### Test
- Check a checkbox → see smooth checkmark animation
- Click any button → see ripple effect from click point
- Successful actions show toast notification that auto-dismisses after 3 seconds
- Focus a text input → see warm glow border

---

## Build Order Summary

| Step | Build | Testable Result |
|------|-------|----------------|
| Setup | Venv, packages, .env, Supabase tables, folders | `python app.py` runs |
| Feature 1 | Home page (HTML/CSS → Flask route) | Landing page with two cards |
| Feature 2 | Modify page (HTML/CSS/JS → Flask routes + Supabase) | Form submits, data in Supabase |
| Feature 3 | Results page (HTML/CSS → Flask route + Supabase reads) | End-to-end flow works |
| Feature 4 | Chat (JS → Flask API + Supabase chat storage) | Chat sends, displays, persists |
| Feature 5 | AI recipe modification (Claude API in submit route) | Modified recipe is AI-generated |
| Feature 6 | AI chat (Claude API in chat route) | Chat gives context-aware baking answers |
| Feature 7 | Recipe history dashboard | Past modifications browsable |
| Feature 8 | Print / export recipe | Clean print layout |
| Feature 9 | Recipe scaling | Ingredient quantities adjust by multiplier |
| Feature 10 | Share recipe | Copyable link with toast notification |
| Feature 11 | Favorites / save recipes | Heart toggle, favorites filter on history |
| Feature 12 | Dietary presets | One-click preset buttons on modify page |
| Feature 13 | Side-by-side diff | Highlighted changes between original and modified |
| Feature 14 | AI recipe image generation | AI-generated photo of the recipe |
| Design 1 | Custom typography (Google Fonts) | Serif headings, clean body text |
| Design 2 | Illustrated SVG icons | Hand-drawn icons replace emoji |
| Design 3 | Animated transitions | Fade/slide entrance, scroll animations |
| Design 4 | Dietary tag badges | Color-coded pills on recipe cards |
| Design 5 | Dark mode | Theme toggle with localStorage persistence |
| Design 6 | Baking loading animation | Themed loader during AI generation |
| Design 7 | Texture & depth | Paper texture, layered card shadows |
| Design 8 | Typography hierarchy & cookbook styling | Cookbook-style recipe layout |
| Design 9 | Mobile polish | Bottom nav, swipeable cards, touch targets |
| Design 10 | Micro-interactions | Checkbox animations, ripples, toasts, glow |

## AI Integration Summary

All AI is powered by the **Claude API** (Anthropic) via the `anthropic` Python SDK. Only two routes contain AI logic:
1. `app.py` `submit()` — Calls Claude to generate a modified recipe based on criteria
2. `app.py` `chat()` — Calls Claude with conversation history + recipe context for follow-up chat

**Model:** `claude-sonnet-4-20250514` for both (good balance of quality and speed)
**API key:** Stored in `.env` as `ANTHROPIC_API_KEY`, loaded via `python-dotenv`
**Fallback:** Both routes gracefully degrade to placeholder text if the API key is missing or the call fails

## Verification

After each feature, run `python app.py` and test the flow in the browser. After all 6 core features:
1. Start at home page → click "Create a Recipe"
2. Fill in recipe + modification criteria → click "Modify Recipe"
3. See results page with AI-modified recipe reflecting the criteria
4. Send chat messages → get context-aware AI responses about the recipe
5. Refresh page → chat history persists, AI remembers conversation
6. Confirm all data in Supabase dashboard (recipes, modifications, chat_messages tables)
