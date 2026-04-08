"""
Unit tests for the structural RAG chunker (memvid-inspired).

Tests run without any database or API key — pure Python logic.
"""

from app.application.services.knowledge_service import (
    StructuredChunk,
    _context_enriched_text,
    structural_chunk,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _types(chunks: list[StructuredChunk]) -> list[str]:
    return [c.chunk_type for c in chunks]


def _contents(chunks: list[StructuredChunk]) -> list[str]:
    return [c.content for c in chunks]


# ---------------------------------------------------------------------------
# Empty / trivial inputs
# ---------------------------------------------------------------------------


def test_empty_text_returns_no_chunks():
    assert structural_chunk("") == []
    assert structural_chunk("   ") == []


def test_short_text_single_paragraph():
    chunks = structural_chunk("Hello world")
    assert len(chunks) == 1
    assert chunks[0].chunk_type == "paragraph"
    assert chunks[0].content == "Hello world"
    assert chunks[0].heading_context == ""


# ---------------------------------------------------------------------------
# Heading detection and context propagation
# ---------------------------------------------------------------------------


def test_heading_is_detected():
    chunks = structural_chunk("# Introduction\n\nThis is the intro.")
    types = _types(chunks)
    assert "heading" in types
    assert "paragraph" in types


def test_heading_context_propagates_to_following_paragraph():
    text = "# Methods\n\nWe used Python."
    chunks = structural_chunk(text)
    para = next(c for c in chunks if c.chunk_type == "paragraph")
    assert para.heading_context == "Methods"


def test_heading_context_updates_on_new_heading():
    text = "# Intro\n\nFirst section.\n\n## Details\n\nSecond section."
    chunks = structural_chunk(text)
    paras = [c for c in chunks if c.chunk_type == "paragraph"]
    assert paras[0].heading_context == "Intro"
    assert paras[1].heading_context == "Details"


def test_multiple_heading_levels():
    text = "## Section A\n\nContent A.\n\n### Subsection B\n\nContent B."
    chunks = structural_chunk(text)
    paras = [c for c in chunks if c.chunk_type == "paragraph"]
    assert paras[0].heading_context == "Section A"
    assert paras[1].heading_context == "Subsection B"


# ---------------------------------------------------------------------------
# Fenced code block detection
# ---------------------------------------------------------------------------


def test_fenced_code_block_detected():
    text = "Some intro.\n\n```python\nprint('hello')\n```\n\nSome outro."
    chunks = structural_chunk(text)
    assert any(c.chunk_type == "code" for c in chunks)
    code = next(c for c in chunks if c.chunk_type == "code")
    assert "print" in code.content


def test_code_block_preserves_heading_context():
    text = "# Usage\n\n```bash\necho hello\n```"
    chunks = structural_chunk(text)
    code = next(c for c in chunks if c.chunk_type == "code")
    assert code.heading_context == "Usage"


def test_code_block_not_split_on_paragraph_boundary():
    # The \n\n inside the code block must not trigger paragraph splitting
    text = "```python\ndef foo():\n\n    pass\n```"
    chunks = structural_chunk(text)
    code_chunks = [c for c in chunks if c.chunk_type == "code"]
    assert len(code_chunks) == 1
    assert "def foo" in code_chunks[0].content


# ---------------------------------------------------------------------------
# Table detection
# ---------------------------------------------------------------------------


def test_table_detected():
    text = "| Name | Value |\n|------|-------|\n| A    | 1     |"
    chunks = structural_chunk(text)
    assert any(c.chunk_type == "table" for c in chunks)


def test_table_with_preceding_heading():
    text = "## Results\n\n| Col1 | Col2 |\n|------|------|\n| a    | b    |"
    chunks = structural_chunk(text)
    table = next(c for c in chunks if c.chunk_type == "table")
    assert table.heading_context == "Results"


def test_table_header_propagated_on_split():
    # Table with header + many rows that exceed max_chars
    header = "| A | B |\n|---|---|"
    rows = "\n".join(f"| row{i} | val{i} |" for i in range(100))
    text = header + "\n" + rows
    chunks = structural_chunk(text, max_chars=200)
    table_chunks = [c for c in chunks if c.chunk_type == "table"]
    assert len(table_chunks) > 1
    # Every table chunk must contain the header
    for tc in table_chunks:
        assert "| A | B |" in tc.content


# ---------------------------------------------------------------------------
# Oversized paragraph — sentence boundary splitting
# ---------------------------------------------------------------------------


def test_oversized_paragraph_split_on_sentences():
    long = " ".join([f"This is sentence number {i}." for i in range(50)])
    chunks = structural_chunk(long, max_chars=200)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c.content) <= 200 or " " not in c.content  # hard-split only for single word


def test_sentence_split_preserves_heading_context():
    heading = "# Big Section\n\n"
    body = " ".join([f"Sentence {i} ends here." for i in range(30)])
    chunks = structural_chunk(heading + body, max_chars=150)
    paras = [c for c in chunks if c.chunk_type == "paragraph"]
    assert all(p.heading_context == "Big Section" for p in paras)


# ---------------------------------------------------------------------------
# Context-enriched embedding text
# ---------------------------------------------------------------------------


def test_context_enriched_text_includes_source():
    chunk = StructuredChunk("Some content.", "paragraph", "")
    enriched = _context_enriched_text("my_doc", chunk)
    assert "[Source: my_doc]" in enriched
    assert "Some content." in enriched


def test_context_enriched_text_includes_heading_when_present():
    chunk = StructuredChunk("Some content.", "paragraph", "Introduction")
    enriched = _context_enriched_text("my_doc", chunk)
    assert "[Section: Introduction]" in enriched


def test_context_enriched_text_no_section_when_no_heading():
    chunk = StructuredChunk("Content.", "paragraph", "")
    enriched = _context_enriched_text("doc", chunk)
    assert "[Section:" not in enriched


# ---------------------------------------------------------------------------
# Mixed document (realistic end-to-end)
# ---------------------------------------------------------------------------


def test_mixed_document_produces_correct_types():
    doc = """# Overview

This is the overview paragraph.

## Code Example

```python
x = 1 + 1
```

## Data Table

| Metric | Value |
|--------|-------|
| Acc    | 0.95  |
| Loss   | 0.05  |

## Conclusion

Final thoughts here.
"""
    chunks = structural_chunk(doc)
    types_seen = set(_types(chunks))
    assert "heading" in types_seen
    assert "paragraph" in types_seen
    assert "code" in types_seen
    assert "table" in types_seen


def test_mixed_document_heading_context_is_correct():
    doc = "# A\n\nPara A.\n\n# B\n\nPara B."
    chunks = structural_chunk(doc)
    paras = [c for c in chunks if c.chunk_type == "paragraph"]
    assert paras[0].heading_context == "A"
    assert paras[1].heading_context == "B"
