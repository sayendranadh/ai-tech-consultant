from pathlib import Path

from task1_knowledge_brain.ingestion.parser import parse_article

FIX = Path(__file__).parent.parent / "fixtures"


def test_parse_article_fields():
    html = (FIX / "article_a.html").read_bytes()
    art = parse_article(html, "https://support.brilliantdirectories.com/article/a")
    assert art.title and "Reset" in art.title
    assert art.canonical_url == "https://support.brilliantdirectories.com/article/a"
    assert any(h.text == "Prerequisites" and h.level == 2 for h in art.headings)
    assert any("Settings" in s for s in art.steps)
    assert art.tables and art.tables[0][0][0] == "Field"
    assert any(i.src.endswith("/img/settings.png") for i in art.images)
    assert "Home | Docs | Login" not in art.body_text
    assert "© 2025" not in art.body_text
    assert art.content_hash and len(art.content_hash) == 64


def test_heading_image_association():
    html = (FIX / "article_a.html").read_bytes()
    art = parse_article(html, "https://support.brilliantdirectories.com/article/a")
    img = next(i for i in art.images if i.src.endswith("settings.png"))
    assert img.section_heading == "Steps"
