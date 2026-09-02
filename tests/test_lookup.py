from nimbus_support.config import PROJECT_ROOT
from nimbus_support.graph.lookup import lookup_order_node
from nimbus_support.orders import OrderStore, extract_order_id


def test_extract_order_id() -> None:
    assert extract_order_id("Where is order #1042?") == "1042"
    assert extract_order_id("order number 1099 is late") == "1099"
    assert extract_order_id("How do I reset my password?") is None


def test_lookup_appends_found_chunk() -> None:
    store = OrderStore(PROJECT_ROOT / "data" / "orders.json")
    result = lookup_order_node({"query": "status of order #1042", "chunks": []}, store)
    assert result["order"]["found"] is True
    assert result["chunks"][0]["slug"] == "order-1042"


def test_unknown_order_still_grounds_in_lookup() -> None:
    store = OrderStore(PROJECT_ROOT / "data" / "orders.json")
    result = lookup_order_node({"query": "where is #8888", "chunks": []}, store)
    assert result["order"]["found"] is False
    assert "8888" in result["chunks"][0]["content"]
