from nimbus_support.pii import redact


def test_redact_email_and_phone() -> None:
    text = "Call me at 415-555-0199 or ada@nimbus.example"
    masked = redact(text)
    assert "ada@nimbus.example" not in masked
    assert "415-555-0199" not in masked
    assert "[email]" in masked
    assert "[phone]" in masked


def test_redact_leaves_order_ids() -> None:
    assert "1042" in redact("Where is order #1042?")
