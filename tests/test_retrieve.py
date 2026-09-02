from nimbus_support.config import PROJECT_ROOT
from nimbus_support.kb.chunking import chunk_articles, load_help_center
from nimbus_support.kb.retrieve import TfidfRetriever


def test_help_center_loads_markdown_and_csv() -> None:
    articles = load_help_center(PROJECT_ROOT / "data" / "help-center")
    slugs = {article.slug for article in articles}
    assert "password-reset" in slugs
    assert "refund-policy" in slugs
    assert "catalog" in slugs


def test_password_query_retrieves_password_article() -> None:
    articles = load_help_center(PROJECT_ROOT / "data" / "help-center")
    retriever = TfidfRetriever.from_chunks(chunk_articles(articles))
    hits = retriever.search("How do I reset my password?")
    assert hits
    assert hits[0].chunk.article_slug == "password-reset"


def test_late_refund_retrieves_refund_policy() -> None:
    articles = load_help_center(PROJECT_ROOT / "data" / "help-center")
    retriever = TfidfRetriever.from_chunks(chunk_articles(articles))
    hits = retriever.search("Can I get a refund after 40 days?")
    assert hits
    assert hits[0].chunk.article_slug == "refund-policy"


def test_catalog_row_is_searchable() -> None:
    articles = load_help_center(PROJECT_ROOT / "data" / "help-center")
    retriever = TfidfRetriever.from_chunks(chunk_articles(articles))
    hits = retriever.search("How much is the Nimbus Hub?")
    assert hits
    assert hits[0].chunk.article_slug == "catalog"
    assert "NIM-HUB" in hits[0].chunk.content


def test_zero_overlap_query_is_dropped_by_score_floor() -> None:
    articles = load_help_center(PROJECT_ROOT / "data" / "help-center")
    retriever = TfidfRetriever.from_chunks(chunk_articles(articles))
    hits = retriever.search("asdfqwer zxcvuiop")
    assert hits == []
