"""Environment settings. Secrets stay on the server."""
import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from psycopg.conninfo import make_conninfo

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseModel):
    database_url: str = Field(default="", repr=False)
    groq_api_key: str = Field(default="", repr=False)
    groq_model: str = "openai/gpt-oss-120b"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    similarity_threshold: float = Field(default=0.88, ge=0.80, le=1.0)
    cache_ttl_seconds: int = Field(default=86400, ge=1)
    cache_max_entries: int = Field(default=500, ge=1, le=10000)
    data_dir: Path = ROOT / "data"
    policies_path: Path = ROOT / "policies.md"

    @classmethod
    def from_env(cls):
        load_dotenv(ROOT / ".env")
        database_url = os.getenv("DATABASE_URL", "").strip()
        if database_url and os.getenv("DATABASE_HOST"):
            database_url = make_conninfo(database_url, host=os.environ["DATABASE_HOST"], port=os.getenv("DATABASE_PORT", "5432"))
        return cls(
            database_url=database_url,
            groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
            groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"),
            similarity_threshold=os.getenv("SIMILARITY_THRESHOLD", "0.88"),
            cache_ttl_seconds=os.getenv("CACHE_TTL_SECONDS", "86400"),
            cache_max_entries=os.getenv("CACHE_MAX_ENTRIES", "500"),
        )
