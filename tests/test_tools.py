import tools
from tools import create_fit_card, search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe


class _MockMessage:
    def __init__(self, content):
        self.content = content


class _MockChoice:
    def __init__(self, content):
        self.message = _MockMessage(content)


class _MockResponse:
    def __init__(self, content):
        self.choices = [_MockChoice(content)]


class _MockCompletions:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _MockResponse(self.content)


class _MockChat:
    def __init__(self, completions):
        self.completions = completions


class _MockClient:
    def __init__(self, completions):
        self.chat = _MockChat(completions)


def _mock_groq(monkeypatch, content):
    completions = _MockCompletions(content)
    monkeypatch.setattr(tools, "_get_groq_client", lambda: _MockClient(completions))
    return completions


def test_search_listings_returns_relevant_results():
    results = search_listings("vintage graphic tee", size=None, max_price=30.0)

    print("\nsearch_listings graphic tee results:")
    for item in results[:5]:
        print(f"- {item['id']}: {item['title']} | size={item['size']} | price=${item['price']}")

    assert results
    assert results[0]["id"] == "lst_006"
    assert results[0]["price"] <= 30.0


def test_search_listings_normalizes_size():
    results = search_listings("platform sneakers", size="US size 8", max_price=None)

    print("\nsearch_listings normalized size results:")
    for item in results:
        print(f"- {item['id']}: {item['title']} | size={item['size']}")

    assert len(results) == 1
    assert results[0]["id"] == "lst_019"
    assert results[0]["size"] == "US 8"


def test_search_listings_no_results_returns_empty_list():
    results = search_listings("designer ballgown", size="XXS", max_price=5.0)

    print("\nsearch_listings no-results output:")
    print(results)

    assert results == []


def test_suggest_outfit_with_example_wardrobe(monkeypatch):
    expected = (
        "Style the graphic tee with baggy straight-leg jeans, chunky white sneakers, "
        "and the vintage black denim jacket."
    )
    completions = _mock_groq(monkeypatch, expected)
    item = search_listings("vintage graphic tee", size=None, max_price=30.0)[0]

    result = suggest_outfit(item, get_example_wardrobe())

    print("\nsuggest_outfit example wardrobe result:")
    print(result)
    print("Prompt system message:")
    print(completions.calls[0]["messages"][0]["content"])

    assert result == expected
    assert "specific named pieces" in completions.calls[0]["messages"][0]["content"]
    assert "Baggy straight-leg jeans" in completions.calls[0]["messages"][1]["content"]


def test_suggest_outfit_with_empty_wardrobe(monkeypatch):
    expected = "No saved wardrobe items were available, so try relaxed denim and sneakers."
    completions = _mock_groq(monkeypatch, expected)
    item = search_listings("vintage graphic tee", size=None, max_price=30.0)[0]

    result = suggest_outfit(item, get_empty_wardrobe())

    print("\nsuggest_outfit empty wardrobe result:")
    print(result)
    print("Prompt user message:")
    print(completions.calls[0]["messages"][1]["content"])

    assert result == expected
    assert "wardrobe is empty" in completions.calls[0]["messages"][1]["content"].lower()


def test_suggest_outfit_missing_item_returns_empty_string():
    result = suggest_outfit({}, get_example_wardrobe())

    print("\nsuggest_outfit missing item result:")
    print(repr(result))

    assert result == ""


def test_create_fit_card_returns_caption(monkeypatch):
    expected = (
        "Found this Graphic Tee - 2003 Tour Bootleg Style on depop for $24. "
        "Pairing it with baggy denim and chunky sneakers gives it an easy vintage streetwear vibe."
    )
    completions = _mock_groq(monkeypatch, expected)
    item = search_listings("vintage graphic tee", size=None, max_price=30.0)[0]

    result = create_fit_card("Wear it with baggy jeans and chunky sneakers.", item)

    print("\ncreate_fit_card caption result:")
    print(result)
    print("Prompt user message:")
    print(completions.calls[0]["messages"][1]["content"])

    assert result == expected
    assert "2-4 sentence" in completions.calls[0]["messages"][1]["content"]
    assert item["title"] in completions.calls[0]["messages"][1]["content"]


def test_create_fit_card_missing_inputs_return_descriptive_strings():
    item = search_listings("vintage graphic tee", size=None, max_price=30.0)[0]

    missing_outfit = create_fit_card("  ", item)
    missing_item = create_fit_card("Wear it with jeans.", {})

    print("\ncreate_fit_card missing input results:")
    print(missing_outfit)
    print(missing_item)

    assert "outfit suggestion is missing" in missing_outfit
    assert "selected item is missing required details" in missing_item
