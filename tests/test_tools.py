from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── search_listings ───────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0

def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []

def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)

def test_search_size_filter():
    results = search_listings("tee", size="XL", max_price=None)
    assert all("xl" in item["size"].lower() for item in results)

def test_search_returns_list_on_no_match():
    # must return [] not raise an exception
    results = search_listings("xyzzy not a real item", size=None, max_price=None)
    assert results == []


# ── suggest_outfit ────────────────────────────────────────────────────────────

def test_suggest_outfit_with_wardrobe():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results, "Need at least one result to test suggest_outfit"
    output = suggest_outfit(results[0], get_example_wardrobe())
    assert isinstance(output, str)
    assert len(output) > 0

def test_suggest_outfit_empty_wardrobe():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results
    output = suggest_outfit(results[0], get_empty_wardrobe())
    assert isinstance(output, str)
    assert len(output) > 0


# ── create_fit_card ───────────────────────────────────────────────────────────

def test_create_fit_card_returns_string():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results
    outfit = suggest_outfit(results[0], get_example_wardrobe())
    card = create_fit_card(outfit, results[0])
    assert isinstance(card, str)
    assert len(card) > 0

def test_create_fit_card_empty_outfit():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results
    card = create_fit_card("", results[0])
    assert card == "Error: outfit suggestion is missing — cannot generate fit card."

def test_create_fit_card_whitespace_outfit():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results
    card = create_fit_card("   ", results[0])
    assert card == "Error: outfit suggestion is missing — cannot generate fit card."
