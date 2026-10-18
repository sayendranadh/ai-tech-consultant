from task1_knowledge_brain.ingestion.chunker import chunk_article
from task1_knowledge_brain.ingestion.parser import Heading, ParsedArticle


def test_chunks_respect_headings():
    art = ParsedArticle(
        title="T",
        body_text="Intro line\nPrereq A\nPrereq B\nSteps\n1. Do X\n2. Do Y\n",
        headings=[Heading(2, "Steps")],
        content_hash="x",
    )
    chunks = chunk_article(art, max_chars=500)
    assert any(c.section_heading == "Steps" and "Do X" in c.text for c in chunks)


def test_empty_article_no_chunks():
    art = ParsedArticle(title=None, body_text="   ", content_hash="x")
    assert chunk_article(art) == []
