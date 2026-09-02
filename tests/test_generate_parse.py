from nimbus_support.graph.generate import _parse_generate_json


def test_parse_plain_json() -> None:
    result = _parse_generate_json(
        '{"route": "grounded", "answer": "Reset it.", "citation_slugs": ["password-reset"]}'
    )
    assert result.route == "grounded"
    assert result.citation_slugs == ["password-reset"]


def test_parse_markdown_fenced_json() -> None:
    result = _parse_generate_json(
        '```json\n{"route": "out_of_scope", "answer": "", "citation_slugs": []}\n```'
    )
    assert result.route == "out_of_scope"
