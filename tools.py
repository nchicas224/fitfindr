"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()

LLM_MODEL = os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")


_SIZE_WORDS = {
    "small": "s",
    "medium": "m",
    "large": "l",
    "extra large": "xl",
    "x large": "xl",
    "x-large": "xl",
}

_STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "in",
    "of",
    "the",
    "to",
    "under",
    "with",
}


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


def _normalize_size(value: str | None) -> str | None:
    """Normalize user/listing size strings while preserving meaningful symbols."""
    if value is None:
        return None

    normalized = str(value).strip().lower()
    if not normalized:
        return None

    normalized = re.sub(r"\bsize\b", " ", normalized)
    for phrase, replacement in _SIZE_WORDS.items():
        normalized = re.sub(rf"\b{re.escape(phrase)}\b", replacement, normalized)
    normalized = re.sub(r"[^a-z0-9./ ]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or None


def _size_tokens(value: str) -> set[str]:
    """Tokenize sizes while keeping combined values like w30 and l30 intact."""
    return set(re.findall(r"[a-z]+\d+(?:\.\d+)?|[a-z]+|\d+(?:\.\d+)?", value))


def _size_matches(query_size: str | None, listing_size: str | None) -> bool:
    """Return True when a parsed size should match a listing size."""
    normalized_query = _normalize_size(query_size)
    if normalized_query is None:
        return True

    normalized_listing = _normalize_size(listing_size)
    if normalized_listing is None:
        return False

    if normalized_query == normalized_listing:
        return True

    query_tokens = _size_tokens(normalized_query)
    listing_tokens = _size_tokens(normalized_listing)
    return bool(query_tokens and query_tokens.issubset(listing_tokens))


def _description_tokens(value: str) -> set[str]:
    tokens = set(re.findall(r"[a-z0-9]+", value.lower()))
    return {token for token in tokens if token not in _STOPWORDS}


def _listing_search_text(listing: dict) -> str:
    style_tags = " ".join(listing.get("style_tags", []))
    colors = " ".join(listing.get("colors", []))
    return " ".join(
        str(part)
        for part in [
            listing.get("title", ""),
            listing.get("description", ""),
            listing.get("category", ""),
            style_tags,
            colors,
            listing.get("brand") or "",
        ]
    )


def _format_listing_for_prompt(listing: dict) -> str:
    style_tags = ", ".join(listing.get("style_tags", [])) or "none"
    colors = ", ".join(listing.get("colors", [])) or "unknown"
    brand = listing.get("brand") or "unknown"
    return "\n".join(
        [
            f"Title: {listing.get('title', 'Unknown item')}",
            f"Description: {listing.get('description', '')}",
            f"Category: {listing.get('category', 'unknown')}",
            f"Style tags: {style_tags}",
            f"Size: {listing.get('size', 'unknown')}",
            f"Condition: {listing.get('condition', 'unknown')}",
            f"Price: ${listing.get('price', 'unknown')}",
            f"Colors: {colors}",
            f"Brand: {brand}",
            f"Platform: {listing.get('platform', 'unknown')}",
        ]
    )


def _wardrobe_items(wardrobe: dict) -> list[dict]:
    if not isinstance(wardrobe, dict):
        return []
    return wardrobe.get("items", [])


def _format_wardrobe_for_prompt(wardrobe: dict) -> str:
    items = _wardrobe_items(wardrobe)
    if not items:
        return "No saved wardrobe items."

    formatted_items = []
    for item in items:
        colors = ", ".join(item.get("colors", [])) or "unknown"
        style_tags = ", ".join(item.get("style_tags", [])) or "none"
        notes = item.get("notes") or "none"
        formatted_items.append(
            "\n".join(
                [
                    f"- Name: {item.get('name', 'Unknown wardrobe item')}",
                    f"  Category: {item.get('category', 'unknown')}",
                    f"  Colors: {colors}",
                    f"  Style tags: {style_tags}",
                    f"  Notes: {notes}",
                ]
            )
        )
    return "\n".join(formatted_items)


def _score_listing(query: str, query_tokens: set[str], listing: dict) -> int:
    title_tokens = _description_tokens(listing.get("title", ""))
    tag_tokens = _description_tokens(" ".join(listing.get("style_tags", [])))
    body_tokens = _description_tokens(
        " ".join(
            str(part)
            for part in [
                listing.get("description", ""),
                listing.get("category", ""),
                " ".join(listing.get("colors", [])),
                listing.get("brand") or "",
            ]
        )
    )

    score = 0
    score += 3 * len(query_tokens & title_tokens)
    score += 2 * len(query_tokens & tag_tokens)
    score += len(query_tokens & body_tokens)

    normalized_query = " ".join(sorted(query_tokens))
    title_text = " ".join(sorted(title_tokens))
    tag_text = " ".join(sorted(tag_tokens))
    if normalized_query and normalized_query in title_text:
        score += 5
    if normalized_query and normalized_query in tag_text:
        score += 4

    phrase = " ".join(re.findall(r"[a-z0-9]+", query.lower()))
    title_raw = listing.get("title", "").lower()
    combined_text = _listing_search_text(listing).lower()
    if phrase and phrase in combined_text:
        score += 6

    query_words = re.findall(r"[a-z0-9]+", query.lower())
    for first, second in zip(query_words, query_words[1:]):
        adjacent_phrase = f"{first} {second}"
        if adjacent_phrase in title_raw:
            score += 12
        if adjacent_phrase in combined_text:
            score += 4

    return score


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    query_tokens = _description_tokens(description or "")
    if not query_tokens:
        return []

    scored_listings = []
    for listing in load_listings():
        if max_price is not None and float(listing.get("price", 0)) > max_price:
            continue

        if not _size_matches(size, listing.get("size")):
            continue

        score = _score_listing(description or "", query_tokens, listing)
        if score == 0:
            continue

        scored_listings.append((score, listing))

    scored_listings.sort(key=lambda item: (-item[0], item[1].get("price", 0)))
    return [listing for _, listing in scored_listings]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    if not new_item:
        return ""

    wardrobe_items = _wardrobe_items(wardrobe)
    if wardrobe_items:
        system_prompt = (
            "You are FitFindr, a practical personal stylist. Suggest 1-2 complete "
            "outfits using the thrifted item and specific named pieces from the "
            "user's wardrobe. Keep the response concise, concrete, and easy to wear."
        )
        user_prompt = (
            "New thrifted item:\n"
            f"{_format_listing_for_prompt(new_item)}\n\n"
            "User wardrobe:\n"
            f"{_format_wardrobe_for_prompt(wardrobe)}\n\n"
            "Suggest 1-2 outfits. Mention the wardrobe pieces by name and explain "
            "the overall vibe briefly."
        )
    else:
        system_prompt = (
            "You are FitFindr, a practical personal stylist. The user has no saved "
            "wardrobe items, so provide general styling ideas instead of pretending "
            "to use pieces from their closet."
        )
        user_prompt = (
            "New thrifted item:\n"
            f"{_format_listing_for_prompt(new_item)}\n\n"
            "The user's wardrobe is empty. Start by briefly saying that no saved "
            "wardrobe items were available, then suggest 1-2 general outfit ideas "
            "for styling this item."
        )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=300,
            temperature=0.7,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception:
        return ""


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    # Replace this with your implementation
    return ""
