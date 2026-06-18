# FitFindr

FitFindr is a multi-tool AI agent for secondhand shopping. Given a natural language request, it searches mock thrift listings, suggests an outfit using the user's wardrobe when available, and creates a short social-style fit card.

## Setup

```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```text
GROQ_API_KEY=your_key_here
```

Run the app:

```bash
python app.py
```

Open the URL printed in the terminal, usually `http://localhost:7860`.

## Tool Inventory

### `search_listings(description: str, size: str | None = None, max_price: float | None = None) -> list[dict]`

Purpose: searches `data/listings.json` for secondhand listings matching the parsed item description, optional size, and optional maximum price.

Inputs:
- `description` (`str`): item/style keywords, such as `"vintage graphic tee"`.
- `size` (`str | None`): optional size filter, such as `"M"`, `"US 8"`, or `"W30 L30"`.
- `max_price` (`float | None`): optional price ceiling.

Output: a `list[dict]` of matching listing dictionaries sorted from most to least relevant. Each listing includes fields such as `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`. If no listings match, it returns `[]`.

### `suggest_outfit(new_item: dict, wardrobe: dict) -> str`

Purpose: suggests 1-2 outfits for a selected listing. If the wardrobe has saved items, the LLM uses named wardrobe pieces. If the wardrobe is empty, it provides general styling advice instead.

Inputs:
- `new_item` (`dict`): the listing selected from `search_listings`.
- `wardrobe` (`dict`): a wardrobe dictionary with an `items` list.

Output: a non-empty `str` with outfit suggestions when successful. If the LLM call fails or the item is missing, it returns an empty string so the agent can stop gracefully.

### `create_fit_card(outfit: str, new_item: dict) -> str`

Purpose: turns an outfit suggestion and selected listing into a short Instagram/TikTok-style caption.

Inputs:
- `outfit` (`str`): the outfit suggestion returned by `suggest_outfit`.
- `new_item` (`dict`): the selected listing.

Output: a `str` containing a 2-4 sentence caption. If the outfit is empty or the selected item is missing required details, it returns a descriptive error string instead of raising an exception.

## Planning Loop

The main planning loop lives in `run_agent(query, wardrobe)` in `agent.py`. It does not call all tools blindly; it branches based on what each step returns.

1. The agent initializes a `session` dictionary with the original query, wardrobe, empty tool outputs, and `error = None`.
2. It asks the LLM to parse the natural language query into `description`, `size`, and `max_price`. If parsing fails, it falls back to a simple regex parser.
3. It calls `search_listings(description, size, max_price)`.
4. If search returns `[]`, the agent sets `session["error"]` and returns early. It does not call `suggest_outfit` or `create_fit_card`.
5. If search succeeds, the agent stores the full list in `session["search_results"]` and selects the top result as `session["selected_item"]`.
6. It passes that same selected item and the wardrobe into `suggest_outfit`.
7. If the outfit response is empty, the agent sets `session["error"]` and returns early before calling `create_fit_card`.
8. If outfit generation succeeds, it stores the string in `session["outfit_suggestion"]`.
9. It passes `session["outfit_suggestion"]` and `session["selected_item"]` into `create_fit_card`.
10. If a fit card is returned, the agent stores it in `session["fit_card"]` and returns the completed session.

## State Management

State is stored in one `session` dictionary for each user interaction. The important fields are:

- `query`: the cleaned original user query.
- `parsed`: structured search parameters from the LLM or fallback parser.
- `search_results`: the full list returned by `search_listings`.
- `selected_item`: the top listing selected from `search_results`.
- `wardrobe`: the user's wardrobe dictionary.
- `wardrobe_empty`: whether the selected wardrobe has no saved items.
- `outfit_suggestion`: the string returned by `suggest_outfit`.
- `fit_card`: the string returned by `create_fit_card`.
- `error`: a helpful error message if the workflow stops early.

The key state handoff is `selected_item`: it is produced by `search_listings`, stored in the session, passed into `suggest_outfit`, and then passed again into `create_fit_card`. The user does not need to re-enter item details between steps.

## Interaction Walkthrough

User query:

```text
vintage graphic tee under $30
```

Step 1: the agent parses the query.

```python
{
    "description": "vintage graphic tee",
    "size": None,
    "max_price": 30.0,
}
```

Step 2: the agent calls:

```python
search_listings("vintage graphic tee", size=None, max_price=30.0)
```

The top result is:

```text
Graphic Tee - 2003 Tour Bootleg Style
$24.00 on depop
Size: L
```

Step 3: the agent calls:

```python
suggest_outfit(selected_item, wardrobe)
```

With the example wardrobe, the LLM suggests using pieces such as baggy straight-leg jeans, chunky white sneakers, and a vintage black denim jacket.

Step 4: the agent calls:

```python
create_fit_card(outfit_suggestion, selected_item)
```

Final user-facing output includes the top listing, outfit idea, and a short fit card caption.

## Error Handling and Fail Points

| Tool | Failure mode | Agent response |
|------|--------------|----------------|
| `search_listings` | No listings match the query. | Returns `[]`. The agent stores a helpful message in `session["error"]` and stops before calling the other tools. |
| `suggest_outfit` | Wardrobe is empty. | This is not treated as a failure. The tool asks the LLM for general styling advice and tells the user no saved wardrobe items were available. |
| `suggest_outfit` | LLM call fails or returns an empty response. | Returns `""`. The agent stores an error and stops before calling `create_fit_card`. |
| `create_fit_card` | Outfit string is empty. | Returns a descriptive error string: `Could not create a fit card because the outfit suggestion is missing.` |
| `create_fit_card` | Selected item is missing required details. | Returns a descriptive error string instead of raising an exception. |

Concrete failure test from Milestone 5:

```bash
python -c "from tools import search_listings, create_fit_card; results = search_listings('vintage graphic tee', size=None, max_price=50); print(create_fit_card('', results[0]))"
```

Output:

```text
Could not create a fit card because the outfit suggestion is missing.
```

I also tested `search_listings` with an impossible query:

```bash
python -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"
```

Output:

```text
[]
```

## Testing

Run the tool tests with printed terminal logs:

```bash
python -m pytest -s tests/test_tools.py
```

The test suite covers:
- relevant listing search
- size normalization
- no-results search behavior
- outfit suggestion with example wardrobe
- outfit suggestion with empty wardrobe
- missing item handling
- fit card generation
- missing fit card inputs

## Spec Reflection

One way `planning.md` helped during implementation: it forced the tool interfaces to be precise before coding. The biggest example was `search_listings`: the planning doc clarified that it should return `list[dict]`, not a wrapper object, so the agent could detect no-results with a simple empty-list check.

Another way the spec helped was with state management. Writing down the session fields first made it straightforward to implement `run_agent` because each tool had an obvious place to store its output before the next tool needed it.

One divergence from the spec: the planning document originally leaned heavily on LLM parsing for query understanding, but the implementation also includes a regex fallback parser. I added this because the agent should still behave predictably if the parsing call fails or returns invalid JSON.

Another small divergence: the tool tests mock the Groq response shape instead of making live LLM calls. This keeps tests deterministic and avoids depending on network/API state, while still verifying that prompts are constructed and responses are read correctly.

## AI Usage

I used ChatGPT/Codex to help implement and review the project in several specific ways.

First, I gave it the Tool 1 section of `planning.md`, the `search_listings` stub in `tools.py`, and the shape of `listings.json`. It produced the first implementation of deterministic search, including price filtering, size normalization, keyword scoring, and sorted results. I revised the scoring after testing because `"Y2K Baby Tee"` initially outranked the actual `"Graphic Tee"` for the query `"vintage graphic tee"`. The final version weights title phrase matches more strongly.

Second, I gave it the Tool 2 and Tool 3 specs plus the wardrobe schema. It helped build the LLM prompts for `suggest_outfit` and `create_fit_card`. I overrode the initial design to keep empty wardrobe as a supported branch instead of an error, because the project requires useful styling advice even when no wardrobe items exist.

Third, I gave it the Planning Loop, State Management section, and Mermaid architecture diagram from `planning.md` to implement `run_agent`. It generated the session-based control flow, and I revised it to add fallback query parsing and early returns for no-results and empty LLM responses.

## Demo Notes

The demo video should show:

1. A happy-path query in the Gradio app, such as `vintage graphic tee under $30`.
2. The top listing, outfit suggestion, and fit card panels populated.
3. A verbal explanation that `selected_item` flows from `search_listings` into `suggest_outfit`, then into `create_fit_card`.
4. At least one triggered failure. The easiest terminal screenshot/demo is the empty outfit case for `create_fit_card`, which returns a clear error string.
