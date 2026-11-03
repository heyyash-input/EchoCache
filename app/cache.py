"""PostgreSQL persistence and bounded connection pooling. No SQLite fallback."""
import hashlib
import logging
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool, PoolTimeout
from pgvector import Vector
from pgvector.psycopg import register_vector

logger = logging.getLogger(__name__)


class CacheUnavailable(Exception):
    pass


def normalize(text: str) -> str:
    return " ".join(text.casefold().split())


class Cache:
    def __init__(self, database_url: str, ttl: int, maximum: int):
        if not database_url:
            raise CacheUnavailable("Set DATABASE_URL in .env and start PostgreSQL with pgvector.")
        self.ttl, self.maximum = ttl, maximum
        self.pool = None
        try:
            with psycopg.connect(database_url, connect_timeout=5) as db:
                db.execute(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))
            self.pool = ConnectionPool(
                database_url, min_size=1, max_size=5, timeout=5, open=False,
                kwargs={"connect_timeout": 5, "autocommit": True, "row_factory": dict_row},
                configure=register_vector,
            )
            self.pool.open(wait=True, timeout=10)
        except (psycopg.Error, PoolTimeout) as exc:
            self.close()
            raise CacheUnavailable("PostgreSQL is unavailable. Check DATABASE_URL and run docker compose up -d postgres.") from exc

    @contextmanager
    def connect(self):
        try:
            with self.pool.connection() as connection:
                yield connection
        except (psycopg.Error, PoolTimeout) as exc:
            logger.warning("PostgreSQL operation failed (%s)", type(exc).__name__)
            raise CacheUnavailable("The cache database is unavailable. Check PostgreSQL and try again.") from exc

    def close(self):
        if self.pool is not None:
            self.pool.close()

    def health(self):
        with self.connect() as db:
            row = db.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()
        return {"connected": row is not None, "engine": "PostgreSQL", "extension": "pgvector", "version": row["extversion"] if row else None}

    def save(self, namespace, prompt, context_key, meaning, embedding, answer, sources, variants=()):
        prompt = normalize(prompt)
        with self.connect() as db, db.transaction():
            # Serialize short writes so concurrent insertions respect the cache cap.
            db.execute("SELECT pg_advisory_xact_lock(736422510)")
            db.execute("DELETE FROM policy_cache WHERE expires_at <= now()")
            row = db.execute("""
                INSERT INTO policy_cache(namespace, prompt_hash, prompt, context_key, meaning, embedding, answer, sources, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now() + %s * interval '1 second')
                ON CONFLICT(namespace, prompt_hash, context_key) DO UPDATE SET
                    prompt=EXCLUDED.prompt, meaning=EXCLUDED.meaning, embedding=EXCLUDED.embedding,
                    answer=EXCLUDED.answer, sources=EXCLUDED.sources,
                    expires_at=EXCLUDED.expires_at, created_at=now()
                RETURNING id
                """, (namespace, hashlib.sha256(prompt.encode()).hexdigest(), prompt, context_key,
                       Jsonb(meaning), Vector(embedding), answer, Jsonb(sources), self.ttl)).fetchone()
            db.execute("DELETE FROM policy_cache_variants WHERE cache_id=%s", (row["id"],))
            for query, vector in variants:
                db.execute("INSERT INTO policy_cache_variants(cache_id, query, embedding) VALUES (%s, %s, %s)",
                           (row["id"], query, Vector(vector)))
            db.execute("""DELETE FROM policy_cache WHERE id IN (
                SELECT id FROM policy_cache ORDER BY created_at DESC, id DESC OFFSET %s
            )""", (self.maximum,))

    def count(self, namespace):
        with self.connect() as db:
            return db.execute("SELECT count(*) AS count FROM policy_cache WHERE namespace=%s AND expires_at > now()", (namespace,)).fetchone()["count"]

    def clear(self):
        with self.connect() as db, db.transaction():
            db.execute("SELECT pg_advisory_xact_lock(736422510)")
            db.execute("DELETE FROM policy_cache")
