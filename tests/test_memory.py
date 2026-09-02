from nimbus_support.memory import WindowBufferStore


def test_window_keeps_last_k_interactions(tmp_path) -> None:
    store = WindowBufferStore(tmp_path / "sessions.json", k=2)
    store.append("s", "q1", "a1")
    store.append("s", "q2", "a2")
    store.append("s", "q3", "a3")
    messages = store.load("s")
    assert [m["content"] for m in messages] == ["q2", "a2", "q3", "a3"]


def test_sessions_are_isolated(tmp_path) -> None:
    store = WindowBufferStore(tmp_path / "sessions.json", k=5)
    store.append("a", "hello", "hi")
    assert store.load("b") == []
    assert store.search_query("a", "and refunds?") == "hello and refunds?"
    assert store.search_query("b", "and refunds?") == "and refunds?"
