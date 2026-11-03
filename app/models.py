from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    role: Literal["user", "assistant"]
    content: Text


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    message: Text
    history: list[Message] = Field(default_factory=list, max_length=12)
    use_cache: bool = True


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    answer: Text
    category: Literal["policy", "clarification", "out_of_scope", "personal"]
    cacheable: bool
    sources: list[str] = Field(max_length=6)
    cache_queries: list[Text] = Field(default_factory=list, max_length=5)


class ChatResponse(BaseModel):
    answer: str
    category: str
    source: Literal["groq", "exact_cache", "semantic_cache"]
    sources: list[str]
    similarity: float | None = None
    latency_ms: int
    cached: bool
    cache_note: str
    tokens_used: int = 0
    embedding_compared: bool = False
    candidates_checked: int = 0
    nearest_similarity: float | None = None
    threshold: float = 0.88
    matched_prompt: str | None = None
    matched_query: str | None = None
    cache_variants: int = 0
