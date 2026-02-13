from src.fallback_router import route_with_rules


def test_price_plus_portion():
    out = route_with_rules("What is the price of a small NUTTY BOWL?")
    assert out.intent == "get_price"
    assert out.portion == "small"
    assert out.item is None or "nutty" in out.item.lower()


def test_calories():
    out = route_with_rules("How many calories does the GO GREEN smoothie have?")
    assert out.intent == "get_calories"
    assert out.item is None or len(out.item) > 0


def test_category_listing():
    out = route_with_rules("Which salads do you have?")
    assert out.intent == "list_category_items"
    assert out.category == "salads"


def test_discount_listing():
    out = route_with_rules("What discounts are available today?")
    assert out.intent == "list_discounts"


def test_discount_triggers():
    out = route_with_rules("What items trigger a BOGO Any Smoothie discount?")
    assert out.intent == "discount_triggers"
    assert out.discount is None or len(out.discount) > 0


def test_unknown():
    out = route_with_rules("Tell me a joke")
    assert out.intent == "unknown"

