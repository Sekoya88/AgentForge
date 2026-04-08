from pydantic import BaseModel, Field, HttpUrl


class KnowledgeIngestRequest(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    text: str = Field(min_length=1, max_length=500_000)


class KnowledgeIngestUrlRequest(BaseModel):
    url: HttpUrl


class KnowledgeIngestResponse(BaseModel):
    title: str
    chunks: int
    source_type: str = "text"


class KnowledgeSourceOut(BaseModel):
    title: str
    chunk_count: int
