# FitFindr

FitFindr is a secondhand shopping assistant that takes a natural language query, searches a mock listings dataset for matching thrifted items, suggests complete outfits using the user's wardrobe, and generates a shareable social media caption — all in one interaction.

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root with your Groq API key (free at [console.groq.com](https://console.groq.com)):

```
GROQ_API_KEY=your_key_here
```

## Running the App

```bash
python app.py
```

Then open the localhost URL shown in your terminal (usually http://localhost:7860).

## Running the Tests

```bash
python -m pytest tests/ -v
```

---

## Tool Inventory

### `search_listings(description, size, max_price)`

**Purpose:** Searches the mock listings dataset for items matching the user's keywords, optional size, and optional price ceiling. Returns results ranked by relevance so the agent can pick the best match.

**Inputs:**
- `description` (str) — keywords describing the item (e.g., `"vintage graphic tee"`). Scored against each listing's title, description, and style_tags fields.
- `size` (str | None) — size string to filter by (e.g., `"M"`, `"S/M"`). Case-insensitive. Pass `None` to skip.
- `max_price` (float | None) — maximum price in dollars, inclusive. Pass `None` to skip.

**Output:** A list of listing dicts sorted by keyword relevance score (highest first). Each dict contains: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns `[]` if nothing matches — never raises an exception.

---

### `suggest_outfit(new_item, wardrobe)`

**Purpose:** Uses the Groq LLM to suggest 1–2 complete outfits that pair the thrifted item with pieces from the user's wardrobe. Falls back to general styling advice when the wardrobe is empty.

**Inputs:**
- `new_item` (dict) — a listing dict for the item the user is considering. The LLM prompt uses `title`, `description`, `category`, `style_tags`, `colors`, `price`, and `platform`.
- `wardrobe` (dict) — a wardrobe dict with an `items` key containing a list of wardrobe item dicts (each has `name`, `category`, `colors`, `style_tags`, `notes`). May be empty.

**Output:** A non-empty string with outfit suggestions. When the wardrobe has items, specific piece names are referenced. When empty, general styling advice is returned instead.

---

### `create_fit_card(outfit, new_item)`

**Purpose:** Uses the Groq LLM to generate a casual 2–4 sentence Instagram/TikTok-style caption for the thrifted outfit. Uses a higher temperature (1.2) so output varies across calls.

**Inputs:**
- `outfit` (str) — the outfit suggestion string from `suggest_outfit`. Must be non-empty.
- `new_item` (dict) — the listing dict for the thrifted item. Used for `title`, `price`, and `platform` in the caption.

**Output:** A 2–4 sentence casual caption string mentioning the item name, price, and platform once each. If `outfit` is empty or whitespace-only, returns `"Error: outfit suggestion is missing — cannot generate fit card."` without calling the LLM.

---

## Planning Loop

`run_agent()` in `agent.py` orchestrates the interaction in six sequential steps:

1. **Initialize session** — `_new_session()` creates the session dict with all output fields set to `None` / `[]`.
2. **Parse the query** — regex extracts `description` (keywords), `size` (e.g., `"size M"`), and `max_price` (e.g., `"under $30"`). Stored in `session["parsed"]`.
3. **Search** — calls `search_listings()`. If results are empty, sets `session["error"]` and returns immediately — `suggest_outfit` is never called with empty input.
4. **Select item** — sets `session["selected_item"] = results[0]` (the top-ranked match).
5. **Suggest outfit** — calls `suggest_outfit()` with the selected item and wardrobe. Result stored in `session["outfit_suggestion"]`.
6. **Create fit card** — calls `create_fit_card()` with the outfit suggestion and selected item. Result stored in `session["fit_card"]`.

The loop is strictly sequential — each step depends on the previous one. The only branch is the early exit in Step 3.

---

## State Management

All state lives in a single `session` dict initialized at the start of `run_agent()`. The planning loop reads from and writes to it directly — no values are passed between steps via standalone local variables.

Key transitions:
- `session["parsed"]` is written after query parsing and read by `search_listings`.
- `session["selected_item"]` is written after search and passed directly into `suggest_outfit`.
- `session["outfit_suggestion"]` is written after `suggest_outfit` and passed directly into `create_fit_card`.
- `session["fit_card"]` is the final output, read by `handle_query()` in `app.py`.
- `session["error"]` is set on early exit; all other output fields remain `None`.

`handle_query()` in `app.py` receives the completed session and maps its fields to the three Gradio output panels.

---

## Error Handling

### `search_listings` — no results

If no listings match the query, `search_listings` returns `[]`. The planning loop detects this, sets a specific error message in `session["error"]`, and returns immediately without calling `suggest_outfit` or `create_fit_card`.

**Example from testing:**
```
python -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"
[]
```
Full agent response: `"No listings found matching 'designer ballgown' in size XXS under $5. Try broader keywords, a different size, or a higher budget."`

---

### `suggest_outfit` — empty wardrobe

If `wardrobe['items']` is an empty list, the function calls the LLM with a general styling prompt instead of a wardrobe-specific one, so it always returns a useful string.

**Example from testing:**
```python
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(suggest_outfit(results[0], get_empty_wardrobe()))
# → "This Y2K baby tee suits a playful, nostalgic vibe... pairs well with
#    high-waisted jeans, flowy skirts, or distressed denim shorts..."
```

---

### `create_fit_card` — empty outfit string

If `outfit` is empty or whitespace-only, the function returns a descriptive error string immediately without calling the LLM.

**Example from testing:**
```python
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(create_fit_card('', results[0]))
# → "Error: outfit suggestion is missing — cannot generate fit card."
```

---

## Spec Reflection

Writing `planning.md` before any code made the implementation significantly more predictable. Having exact parameter types, return value field lists, and failure mode responses written down meant there was no ambiguity when implementing each function — the spec answered questions like "what does this return when nothing matches?" before they came up in code.

The one place the spec required adjustment during implementation was `search_listings`: the initial keyword scoring was too loose and matched common words like "a" and "item" against listing text, causing unrelated listings to score above zero. Adding a stop word filter before scoring fixed this and was captured in the test `test_search_returns_list_on_no_match`. The planning loop design held up without changes — the session dict structure and early-exit branch worked exactly as diagrammed.

---

## AI Usage

### Instance 1 — Implementing `search_listings`

**What I gave Claude:** The Tool 1 spec block from `planning.md` (description, all three input parameters with types, full return value field list, failure mode) plus a sample listing dict from `data/listings.json`.

**What it produced:** A working implementation using `load_listings()` that filtered by price and size and scored listings by keyword overlap across title, description, and style_tags.

**What I changed:** The generated scoring used raw `.split()` on the description without filtering stop words. Common words like `"a"`, `"item"`, and `"real"` were matching against listing text and causing unrelated listings to score above zero. I added a `_STOP_WORDS` set to strip these before scoring, which fixed the `test_search_returns_list_on_no_match` test that was failing.

---

### Instance 2 — Implementing `run_agent()` (planning loop)

**What I gave Claude:** The full Architecture diagram from `planning.md`, the Planning Loop section (6-step conditional logic), the State Management section, the existing `_new_session()` function, and the 7-step TODO comment from `agent.py`.

**What it produced:** A complete `run_agent()` implementation with regex parsing for size and price, the `search_listings` call, the early-exit branch on empty results, and sequential calls to `suggest_outfit` and `create_fit_card` with session dict writes at each step.

**What I verified before using it:** Confirmed the early-return branch checked `not results` before calling `suggest_outfit`, that each tool result was written to the session dict (not a local variable), and that `session["selected_item"]` was the exact dict passed into `suggest_outfit`. Ran `python agent.py` to confirm both the happy path and the no-results path produced correct output before committing.
