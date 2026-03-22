from pydantic import BaseModel, Field


class KnowledgeIngestRequest(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    text: str = Field(min_length=1, max_length=500_000)


class KnowledgeIngestResponse(BaseModel):
    title: str
    chunks: int


class KnowledgeSourceOut(BaseModel):
    title: str
    chunk_count: int
