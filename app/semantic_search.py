"""Exact cosine search executed by the PostgreSQL pgvector extension."""
from pgvector import Vector
from psycopg.types.json import Jsonb

from app.guardrails import meaning_signature


def search(cache, namespace: str, vector: list[float], prompt: str, context_key: str, threshold: float):
    # Distances are computed in PostgreSQL. Python receives only the best answer
    # and diagnostic aggregates, never the full vector collection.
    with cache.connect() as db:
        row = db.execute("""
            WITH ranked AS MATERIALIZED (
                SELECT c.prompt, c.answer, c.sources, c.context_key, c.meaning,
                       closest.query AS matched_query, closest.similarity
                FROM policy_cache c
                CROSS JOIN LATERAL (
                    SELECT query, 1 - (embedding <=> %(vector)s) AS similarity
                    FROM (
                        SELECT c.prompt AS query, c.embedding
                        UNION ALL
                        SELECT v.query, v.embedding FROM policy_cache_variants v WHERE v.cache_id=c.id
                    ) vectors
                    ORDER BY similarity DESC, query ASC LIMIT 1
                ) closest
                WHERE c.namespace = %(namespace)s AND c.expires_at > now()
            ), best AS (
                SELECT prompt, answer, sources, similarity, matched_query
                FROM ranked
                WHERE context_key = %(context)s AND meaning = %(meaning)s
                  AND similarity >= %(threshold)s
                ORDER BY similarity DESC, prompt ASC LIMIT 1
            )
            SELECT (SELECT row_to_json(best) FROM best) AS match,
                   (SELECT max(similarity) FROM ranked) AS nearest_similarity,
                   (SELECT count(*) FROM ranked) AS candidates_checked,
                   (SELECT count(*) FROM ranked WHERE context_key=%(context)s AND meaning=%(meaning)s) AS compatible_count
            """, {"vector": Vector(vector), "namespace": namespace, "context": context_key,
                   "meaning": Jsonb(meaning_signature(prompt)), "threshold": threshold}).fetchone()
    if not row["candidates_checked"]:
        reason = "No active answers are saved for the current policies and matching version."
    elif not row["compatible_count"]:
        reason = "Saved answers differ in explicit conditions or conversation context."
    else:
        reason = "No compatible original question or alternative wording reached the similarity threshold."
    return row["match"], row["nearest_similarity"], row["candidates_checked"], reason
