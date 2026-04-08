import re
import uuid
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx

from app.application.services.secrets_service import SecretsService
from app.config import Settings
from app.domain.ports.knowledge_repository import KnowledgeRepository, KnowledgeSourceSummary

# ---------------------------------------------------------------------------
# Structural chunker — inspired by memvid's structure-aware pipeline
# Pipeline: Raw Text → detect elements → emit typed chunks with heading context
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_FENCED_CODE_RE = re.compile(r"(```[\w]*\n[\s\S]*?```)", re.DOTALL)
_TABLE_LINE_RE = re.compile(r"^\|.+\|", re.MULTILINE)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class StructuredChunk:
    content: str
    chunk_type: str  # 'paragraph' | 'code' | 'table' | 'heading'
    heading_context: str  # nearest ancestor heading, empty string if none


def _split_sentences(text: str, max_chars: int) -> list[str]:
    """Split oversized paragraph at sentence boundaries, no hard char-cut mid-word."""
    sentences = _SENTENCE_SPLIT_RE.split(text)
    parts: list[str] = []
    current = ""
    for s in sentences:
        candidate = f"{current} {s}".strip() if current else s
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                parts.append(current)
            while len(s) > max_chars:
                parts.append(s[:max_chars])
                s = s[max_chars:]
            current = s
    if current:
        parts.append(current)
    return parts


def _emit_prose_block(
    blob: str,
    chunks: list[StructuredChunk],
    current_heading: list[str],  # mutable single-element container
    max_chars: int,
) -> None:
    """Parse a prose blob (no code/table), emit heading + paragraph chunks."""
    for para in re.split(r"\n{2,}", blob):
        para = para.strip()
        if not para:
            continue
        m = _HEADING_RE.match(para)
        if m:
            current_heading[0] = m.group(2).strip()
            chunks.append(StructuredChunk(para, "heading", current_heading[0]))
        elif len(para) <= max_chars:
            chunks.append(StructuredChunk(para, "paragraph", current_heading[0]))
        else:
            for part in _split_sentences(para, max_chars):
                chunks.append(StructuredChunk(part, "paragraph", current_heading[0]))


def _emit_table_block(
    table_lines: list[str],
    chunks: list[StructuredChunk],
    current_heading: str,
    max_chars: int,
) -> None:
    """Emit table block, splitting at row boundaries while propagating header."""
    block = "\n".join(table_lines).strip()
    if not block:
        return
    if len(block) <= max_chars:
        chunks.append(StructuredChunk(block, "table", current_heading))
        return
    header = "\n".join(table_lines[:2]) if len(table_lines) >= 2 else ""
    part_rows: list[str] = []
    for row in table_lines[2:]:
        rows_str = "\n".join(part_rows + [row])
        candidate = (header + "\n" + rows_str) if header else rows_str
        if len(candidate) > max_chars and part_rows:
            emit = header + "\n" + "\n".join(part_rows) if header else "\n".join(part_rows)
            chunks.append(StructuredChunk(emit, "table", current_heading))
            part_rows = [row]
        else:
            part_rows.append(row)
    if part_rows:
        emit = header + "\n" + "\n".join(part_rows) if header else "\n".join(part_rows)
        chunks.append(StructuredChunk(emit, "table", current_heading))


def structural_chunk(
    text: str,
    *,
    max_chars: int = 1000,
) -> list[StructuredChunk]:
    """
    Structure-aware chunker modelled after memvid's StructuralChunker.

    Pipeline:
        Raw Text
          → split out fenced code blocks (protected from paragraph splitting)
          → within prose: split out markdown tables (header propagation)
          → within prose: detect headings (track context)
          → split paragraphs on \\n\\n, then on sentence boundaries if oversized
    """
    t = (text or "").strip()
    if not t:
        return []

    chunks: list[StructuredChunk] = []
    current_heading: list[str] = [""]  # mutable so nested helpers can update it

    # Split on fenced code blocks first (these must not be touched by prose logic)
    segments = _FENCED_CODE_RE.split(t)

    for segment in segments:
        if not segment.strip():
            continue

        if _FENCED_CODE_RE.fullmatch(segment.strip()):
            code = segment.strip()
            if len(code) <= max_chars:
                chunks.append(StructuredChunk(code, "code", current_heading[0]))
            else:
                lines = code.splitlines(keepends=True)
                part = ""
                for line in lines:
                    if len(part) + len(line) > max_chars and part:
                        chunks.append(StructuredChunk(part.rstrip(), "code", current_heading[0]))
                        part = line
                    else:
                        part += line
                if part.strip():
                    chunks.append(StructuredChunk(part.rstrip(), "code", current_heading[0]))
            continue

        # Prose segment: separate table rows from text
        lines = segment.splitlines()
        text_buf: list[str] = []
        table_buf: list[str] = []
        in_table = False

        for line in lines:
            if _TABLE_LINE_RE.match(line):
                if not in_table:
                    _emit_prose_block("\n".join(text_buf), chunks, current_heading, max_chars)
                    text_buf = []
                    in_table = True
                table_buf.append(line)
            else:
                if in_table:
                    _emit_table_block(table_buf, chunks, current_heading[0], max_chars)
                    table_buf = []
                    in_table = False
                text_buf.append(line)

        if in_table:
            _emit_table_block(table_buf, chunks, current_heading[0], max_chars)
        elif text_buf:
            _emit_prose_block("\n".join(text_buf), chunks, current_heading, max_chars)

    return chunks


async def _embed_batch(texts: list[str], api_key: str) -> list[list[float]]:
    if not texts:
        return []
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": "text-embedding-3-small", "input": texts},
            timeout=120.0,
        )
        r.raise_for_status()
        data = r.json()
    out: list[list[float]] = []
    for item in sorted(data["data"], key=lambda x: x["index"]):
        out.append(list(item["embedding"]))
    return out


async def _embed_one(text: str, api_key: str) -> list[float]:
    vecs = await _embed_batch([text], api_key)
    return vecs[0]


# Minimum RRF score to include a result (filters out near-zero relevance noise)
_MIN_RRF_SCORE = 0.005


def _context_enriched_text(title: str, chunk: StructuredChunk) -> str:
    """
    Build the text that gets embedded (not stored).

    Inspired by memvid's contextual frame metadata: prepend source + heading
    so the embedding vector captures positional/topical context, not just
    the raw content. This is NOT stored — only used for the embedding call.
    """
    parts = [f"[Source: {title}]"]
    if chunk.heading_context:
        parts.append(f"[Section: {chunk.heading_context}]")
    parts.append(chunk.content)
    return "\n".join(parts)


class KnowledgeService:
    def __init__(
        self, repo: KnowledgeRepository, settings: Settings, secrets: SecretsService
    ) -> None:
        self._repo = repo
        self._settings = settings
        self._secrets = secrets

    async def ingest_text(self, user_id: UUID, title: str, text: str) -> dict[str, Any]:
        user_secrets = await self._secrets.get_decrypted_secrets(user_id)
        key = user_secrets.get("openai_key") or self._settings.openai_api_key
        if not key:
            raise ValueError("OPENAI_API_KEY is required to index knowledge. Set it in Settings.")
        title = (title or "untitled").strip()[:512]

        # Structure-aware chunking (memvid-inspired pipeline)
        structured = structural_chunk(text)
        if not structured:
            await self._repo.delete_by_title(user_id, title)
            return {"title": title, "chunks": 0}

        # Build context-enriched texts for embedding (source + heading prepended)
        embed_texts = [_context_enriched_text(title, c) for c in structured]

        await self._repo.delete_by_title(user_id, title)
        embeddings = await _embed_batch(embed_texts, key)

        for i, (chunk, emb) in enumerate(zip(structured, embeddings, strict=True)):
            await self._repo.insert_chunk(
                user_id,
                uuid.uuid4(),
                title,
                i,
                chunk.content,  # store raw content, not enriched text
                emb,
                chunk_type=chunk.chunk_type,
                heading_context=chunk.heading_context,
            )
        return {"title": title, "chunks": len(structured)}

    async def list_sources(self, user_id: UUID) -> list[KnowledgeSourceSummary]:
        return await self._repo.list_sources(user_id)

    async def delete_source(self, user_id: UUID, title: str) -> int:
        return await self._repo.delete_by_title(user_id, title)

    async def ingest_url(self, user_id: UUID, url: str) -> dict[str, Any]:
        """Fetch a URL, strip HTML, and ingest as a knowledge source."""
        import re as _re
        from urllib.parse import urlparse

        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must use http or https scheme")

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={"User-Agent": "AgentForge-Crawler/1.0"},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        raw_text: str
        if "text/html" in content_type:
            try:
                from bs4 import BeautifulSoup  # optional dep

                soup = BeautifulSoup(resp.text, "html.parser")
                # Remove script/style noise
                for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    tag.decompose()
                raw_text = soup.get_text(separator="\n", strip=True)
            except ImportError:
                # Fallback: strip HTML tags with regex
                raw_text = _re.sub(r"<[^>]+>", " ", resp.text)
                raw_text = _re.sub(r"\s{2,}", "\n", raw_text).strip()
        else:
            raw_text = resp.text

        # Derive a title from the URL path
        path_part = parsed.path.rstrip("/").split("/")[-1] or parsed.netloc
        title = path_part.replace("-", " ").replace("_", " ").strip() or url[:80]

        return await self.ingest_text(user_id, title, raw_text)

    async def search_context(self, user_id: UUID, query: str, top_k: int = 5) -> str:
        user_secrets = await self._secrets.get_decrypted_secrets(user_id)
        key = user_secrets.get("openai_key") or self._settings.openai_api_key
        if not key:
            return "(Knowledge search unavailable: OPENAI_API_KEY not set.)"
        q = (query or "").strip()
        if not q:
            return "(empty query)"
        emb = await _embed_one(q, key)
        results = await self._repo.search_hybrid(user_id, q, emb, top_k=top_k)

        # Filter out near-zero relevance (noise gate)
        relevant = [r for r in results if r.rrf_score >= _MIN_RRF_SCORE]
        if not relevant:
            return "(no matching documents in your knowledge base; ingest text under Knowledge.)"

        # Format with source attribution so the LLM can cite
        sections: list[str] = []
        for r in relevant:
            header_parts = [f"[{r.source_title}]"]
            if r.heading_context:
                header_parts.append(f" › {r.heading_context}")
            sections.append("".join(header_parts) + "\n" + r.content)
        return "\n\n---\n\n".join(sections)
