# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.
---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock listings dataset for items that match a keyword description, an optional size filter, and an optional maximum price. Returns a ranked list of matching listing dicts sorted by keyword relevance score (highest first).

**Input parameters:**
- `description` (str): Keywords describing what the user wants (e.g., "vintage graphic tee"). Used to score listings by overlap with each listing's title, description, and style_tags fields.
- `size` (str | None): Size string to filter by (e.g., "M", "S/M", "W30 L30"). Matching is case-insensitive. Pass None to skip size filtering.
- `max_price` (float | None): Maximum price in dollars, inclusive (e.g., 30.0). Pass None to skip price filtering.

**What it returns:**
A list of listing dicts sorted by relevance score (highest first). Each dict contains: `id` (str), `title` (str), `description` (str), `category` (str — one of tops/bottoms/outerwear/shoes/accessories), `style_tags` (list[str]), `size` (str), `condition` (str — excellent/good/fair), `price` (float), `colors` (list[str]), `brand` (str or None), `platform` (str — depop/thredUp/poshmark). Returns an empty list `[]` if nothing matches — does not raise an exception.

**What happens if it fails or returns nothing:**
The agent sets `session["error"]` to: `"No listings found matching '[description]' in your size/price range. Try broader keywords, a different size, or a higher budget."` and returns the session immediately. `suggest_outfit` is never called with empty input.

---

### Tool 2: suggest_outfit

**What it does:**
Calls the Groq LLM (llama-3.3-70b-versatile) to suggest 1–2 complete outfits pairing the new thrifted item with pieces from the user's wardrobe. If the wardrobe is empty, returns general styling advice for the item instead.

**Input parameters:**
- `new_item` (dict): A listing dict — the item the user is considering buying. The prompt uses: `title`, `description`, `category`, `style_tags`, `colors`, `price`, `platform`.
- `wardrobe` (dict): A wardrobe dict with an `items` key containing a list of wardrobe item dicts. Each item has: `id`, `name`, `category`, `colors`, `style_tags`, `notes`. The list may be empty.

**What it returns:**
A non-empty string with 1–2 outfit suggestions. When the wardrobe has items, suggestions name specific wardrobe pieces by name (e.g., "pair with your baggy straight-leg jeans and chunky white sneakers"). When the wardrobe is empty, the string gives general styling advice — what vibes the item suits and what categories of pieces pair well with it.

**What happens if it fails or returns nothing:**
If `wardrobe['items']` is empty, the function calls the LLM with a general styling prompt rather than raising an exception or returning `""`. The function always returns a non-empty string regardless of wardrobe state.

---

### Tool 3: create_fit_card

**What it does:**
Calls the Groq LLM (llama-3.3-70b-versatile) to generate a casual, shareable 2–4 sentence outfit caption suitable for Instagram or TikTok, based on the outfit suggestion and the thrifted item's details.

**Input parameters:**
- `outfit` (str): The outfit suggestion string returned by `suggest_outfit`. Must be non-empty.
- `new_item` (dict): The listing dict for the thrifted item. Used for `title`, `price`, and `platform` in the caption.

**What it returns:**
A 2–4 sentence string written in a casual OOTD voice — mentions the item name, price, and platform naturally (once each), captures the outfit vibe in specific terms, and sounds different on each call (LLM temperature ≥ 1.0). If `outfit` is empty or whitespace-only, returns the error string `"Error: outfit suggestion is missing — cannot generate fit card."` without calling the LLM.

**What happens if it fails or returns nothing:**
Guards against an empty or whitespace-only `outfit` string at the start of the function and returns a descriptive error message string rather than raising an exception.

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**

The planning loop in `run_agent()` runs sequentially and branches early if search returns nothing:

1. **Initialize session**: Call `_new_session(query, wardrobe)` to set all fields to None / [].
2. **Parse the query** using regex to extract:
   - `description`: the query with size/price tokens stripped, lowercased.
   - `size`: matched from patterns like `"size M"`, `"in size XL"`, `"size S/M"`. None if not found.
   - `max_price`: matched from patterns like `"under $30"`, `"under 30"`, converted to float. None if not found.
   Store as `session["parsed"] = {"description": ..., "size": ..., "max_price": ...}`.
3. **Call `search_listings`** with the parsed parameters. Store result in `session["search_results"]`.
   - **If `results == []`**: set `session["error"]` to a helpful message and `return session` immediately — do NOT proceed.
   - **If `results != []`**: set `session["selected_item"] = results[0]`.
4. **Call `suggest_outfit`** with `session["selected_item"]` and `session["wardrobe"]`. Store result in `session["outfit_suggestion"]`.
5. **Call `create_fit_card`** with `session["outfit_suggestion"]` and `session["selected_item"]`. Store result in `session["fit_card"]`.
6. **Return `session`**.

`suggest_outfit` and `create_fit_card` are never called unconditionally — both are gated on Step 3 returning at least one result.

---

## State Management

**How does information from one tool get passed to the next?**

The `session` dict is initialized once at the start of `run_agent()` and is the single source of truth for the entire interaction. The planning loop reads from and writes to it directly — values are not passed between steps via standalone local variables.

Key state transitions:
- **After parse**: `session["parsed"]` holds `{description, size, max_price}`.
- **After `search_listings`**: `session["search_results"]` holds the full ranked list; `session["selected_item"]` holds `results[0]` — the exact dict passed into `suggest_outfit`.
- **After `suggest_outfit`**: `session["outfit_suggestion"]` holds the LLM-generated string — the exact value passed into `create_fit_card`.
- **After `create_fit_card`**: `session["fit_card"]` holds the final caption string.
- **On early exit**: `session["error"]` is set to a message string; `outfit_suggestion` and `fit_card` remain `None`.

`handle_query()` in `app.py` reads the returned session and maps its fields to the three Gradio output panels.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Sets `session["error"]` to `"No listings found matching '[description]' in your size/price range. Try broader keywords, a different size, or a higher budget."` and returns session immediately without calling subsequent tools. |
| suggest_outfit | `wardrobe['items']` is an empty list | Calls the LLM with a general styling prompt ("What styles and clothing categories pair well with this item?") and returns a non-empty string — does not crash or return `""`. |
| create_fit_card | `outfit` is an empty or whitespace-only string | Returns `"Error: outfit suggestion is missing — cannot generate fit card."` immediately without calling the LLM. |

---

## Architecture

```
User query (e.g. "vintage graphic tee under $30, size M")
    │
    ▼
Planning Loop (agent.py → run_agent())
    │
    ├─► Step 1: _new_session(query, wardrobe)
    │       → session initialized; all output fields = None / []
    │
    ├─► Step 2: Parse query (regex)
    │       → session["parsed"] = {description, size, max_price}
    │
    ├─► Step 3: search_listings(description, size, max_price)
    │       → session["search_results"] = [listing_dict, ...]
    │       │
    │       ├── results == []
    │       │       → session["error"] = "No listings found..."
    │       │       → return session     ◄── EARLY EXIT (error path)
    │       │
    │       └── results != []
    │               → session["selected_item"] = results[0]
    │
    ├─► Step 4: suggest_outfit(selected_item, wardrobe)
    │       → session["outfit_suggestion"] = "Pair with your wide-leg jeans..."
    │       │
    │       └── wardrobe["items"] == []
    │               → LLM returns general styling advice (no crash)
    │
    ├─► Step 5: create_fit_card(outfit_suggestion, selected_item)
    │       → session["fit_card"] = "found this $18 tee on depop..."
    │       │
    │       └── outfit == ""
    │               → returns error string (no crash)
    │
    └──► return session
                │
                ▼
         handle_query() in app.py
                │
                ├── session["error"] set
                │       → panel 1: error message | panels 2+3: ""
                │
                └── success
                        → panel 1: title, price, platform, condition, size
                          panel 2: session["outfit_suggestion"]
                          panel 3: session["fit_card"]
```

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**

- **search_listings**: I'll give Claude the Tool 1 spec block from planning.md (description, all input params with types, return value with full field list, failure mode) plus a sample listing dict from `data/listings.json`. I'll ask it to implement the function in `tools.py` using `load_listings()` from `utils/data_loader.py`, scoring each listing by counting keyword overlaps across `title`, `description`, and `style_tags`. Before using the output I'll verify: (1) it filters by `max_price` before scoring, (2) it filters `size` case-insensitively, (3) it drops zero-score listings, (4) it returns `[]` without raising an exception. I'll test with 3 queries: `"vintage graphic tee"` (expect results), `"designer ballgown" size="XXS" max_price=5.0` (expect `[]`), and `"jacket" max_price=10.0` (all results must have `price <= 10`).

- **suggest_outfit**: I'll give Claude the Tool 2 spec block and the wardrobe schema from `data/wardrobe_schema.json`. I'll ask it to call Groq's `llama-3.3-70b-versatile` with a prompt that includes the new item's title, description, colors, and style_tags, plus each wardrobe item's name, category, colors, and style_tags. Before using the output I'll verify: (1) the empty-wardrobe branch calls the LLM with a different general styling prompt, (2) the function always returns a non-empty string, (3) a call with the example wardrobe references specific wardrobe piece names in the output.

- **create_fit_card**: I'll give Claude the Tool 3 spec block and the caption style guidelines from the docstring (casual OOTD voice, mention item/price/platform once each, temperature ≥ 1.0). Before using the output I'll verify: (1) the guard against empty `outfit` returns the error string without calling the LLM, (2) running it 3 times on the same input produces noticeably different captions.

**Milestone 4 — Planning loop and state management:**

- **run_agent()**: I'll give Claude the full Architecture diagram, the Planning Loop section, and the State Management section from this planning.md, plus the existing `_new_session()` function and the 7-step TODO from `agent.py`. I'll ask it to implement `run_agent()` matching the spec exactly. Before using the output I'll verify: (1) the early-return branch checks `search_results == []` before calling `suggest_outfit`, (2) each tool result is stored in the session dict, (3) `session["selected_item"]` is the exact dict passed into `suggest_outfit`.

- **handle_query()**: I'll give Claude the `handle_query()` docstring from `app.py` and the session dict field definitions from `_new_session()`. I'll ask it to map session fields to the three Gradio output panel strings and handle the error case. I'll verify by running `python app.py` and submitting both a valid query and the deliberate no-results query (`"designer ballgown size XXS under $5"`).

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
<!-- What does the agent do first? Which tool is called? With what input? -->
<p align="left">After scanning the prompt, the search_listings() function retrieves the clothing type, size, and the maximumm price the user is willing to pay.</p>

**Step 2:**
<!-- What happens next? What was returned from step 1? What tool is called now? -->
<p align="left">Now, the suggest_outfit() function is called and returns a suggested outfit that includes other clothing pieces that could potentially interest the user as well as a styling tip.</p>

**Step 3:**
<!-- Continue until the full interaction is complete -->
<p align="left">Next, the create_fit_card() function is called. It lets the user share their purchase with others and includes the details about the clothing style, price, and outfit suggestions.</p>

**Final output to user:**
<!-- What does the user actually see at the end? -->
<p align="left">In the end, the user gets to see outfit suggestions alongside the option to share their outifts and clothign pieces they found on Depop, with other people.</p>