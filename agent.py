"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import json
import re

from tools import (
    LLM_MODEL,
    _get_groq_client,
    search_listings,
    suggest_outfit,
    create_fit_card,
)


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
        "wardrobe_empty": not bool(wardrobe.get("items", [])) if isinstance(wardrobe, dict) else True,
    }


def _fallback_parse_query(query: str) -> dict:
    """Extract basic search params if the LLM parser is unavailable."""
    max_price = None
    price_match = re.search(r"(?:under|below|less than|up to)?\s*\$?\s*(\d+(?:\.\d+)?)", query, re.I)
    if price_match and any(marker in query.lower() for marker in ["$", "under", "below", "less than", "up to"]):
        max_price = float(price_match.group(1))

    size = None
    size_match = re.search(
        r"\b(?:size\s*)?(one size|us\s*\d+(?:\.\d+)?|w\d+(?:\s*l\d+)?|s/m|m/l|l/xl|xxs|xs|s|m|l|xl|xxl)\b",
        query,
        re.I,
    )
    if size_match:
        size = size_match.group(1).strip()

    description = query
    description = re.sub(r"(?:under|below|less than|up to)\s*\$?\s*\d+(?:\.\d+)?", " ", description, flags=re.I)
    description = re.sub(r"\bsize\s+", " ", description, flags=re.I)
    if size:
        description = re.sub(re.escape(size), " ", description, flags=re.I)
    description = re.sub(r"\$?\d+(?:\.\d+)?", " ", description)
    description = re.sub(r"\s+", " ", description).strip(" ,.")

    return {
        "description": description or query.strip(),
        "size": size,
        "max_price": max_price,
    }


def _coerce_parsed_query(parsed: dict, original_query: str) -> dict:
    description = str(parsed.get("description") or original_query).strip()
    size = parsed.get("size")
    if isinstance(size, str):
        size = size.strip() or None
    elif size is not None:
        size = str(size).strip() or None

    max_price = parsed.get("max_price")
    if max_price in ("", None):
        max_price = None
    else:
        try:
            max_price = float(max_price)
        except (TypeError, ValueError):
            max_price = None

    return {
        "description": description,
        "size": size,
        "max_price": max_price,
    }


def _parse_query_with_llm(query: str) -> dict:
    prompt = (
        "Parse this thrift shopping query into JSON with exactly these keys: "
        "description, size, max_price.\n"
        "- description: the item/style keywords to search for, without price or size words.\n"
        "- size: a string like M, US 8, W30 L30, S/M, or null if not provided.\n"
        "- max_price: a number or null if not provided.\n\n"
        f"Query: {query}\n\n"
        "Return only valid JSON."
    )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "You extract structured search parameters from user queries."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=150,
            temperature=0,
        )
        text = (response.choices[0].message.content or "").strip()
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("Parsed query was not a JSON object.")
        return _coerce_parsed_query(parsed, query)
    except Exception:
        return _fallback_parse_query(query)


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    session = _new_session(query, wardrobe)

    cleaned_query = (query or "").strip()
    session["query"] = cleaned_query
    session["wardrobe"] = wardrobe

    if not cleaned_query:
        session["error"] = "Please enter a search query before looking for listings."
        return session

    parsed = _parse_query_with_llm(cleaned_query)
    session["parsed"] = parsed

    results = search_listings(
        description=parsed["description"],
        size=parsed.get("size"),
        max_price=parsed.get("max_price"),
    )
    session["search_results"] = results

    if not results:
        session["error"] = "No listings matched your search. Try a broader description, different size, or higher price."
        return session

    selected_item = results[0]
    session["selected_item"] = selected_item

    outfit = suggest_outfit(selected_item, wardrobe)
    if not outfit or not outfit.strip():
        session["error"] = "I found a listing, but could not generate an outfit suggestion for it."
        return session
    session["outfit_suggestion"] = outfit

    fit_card = create_fit_card(outfit, selected_item)
    if not fit_card or not fit_card.strip():
        session["error"] = "I found an outfit, but could not create a fit card for it."
        return session
    session["fit_card"] = fit_card

    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
