CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS policy_cache (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    namespace text NOT NULL,
    prompt_hash text NOT NULL,
    prompt text NOT NULL,
    context_key text NOT NULL,
    meaning jsonb NOT NULL,
    embedding vector(384) NOT NULL,
    answer text NOT NULL,
    sources jsonb NOT NULL,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(namespace, prompt_hash, context_key)
);

CREATE INDEX IF NOT EXISTS policy_cache_namespace_expiry
    ON policy_cache(namespace, expires_at);
CREATE INDEX IF NOT EXISTS policy_cache_expiry ON policy_cache(expires_at);

CREATE TABLE IF NOT EXISTS policy_cache_variants (
    cache_id bigint NOT NULL REFERENCES policy_cache(id) ON DELETE CASCADE,
    query text NOT NULL,
    embedding vector(384) NOT NULL,
    PRIMARY KEY(cache_id, query)
);

-- Exact pgvector cosine search is intentional for this bounded cache.
-- An approximate index could miss a valid match after metadata filtering.
