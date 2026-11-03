import hashlib
import json
import logging
import threading
import time
from app.cache import Cache, normalize
from app.embeddings import Embeddings
from app.guardrails import needs_history, reusable_request, meaning_signature
from app.llm import Groq, PROMPT_VERSION, ProviderError
from app.models import ChatRequest, ChatResponse
from app.policies import load_policies
from app.semantic_search import search

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, settings, provider=None, embeddings=None):
        self.settings = settings
        self.provider = provider or Groq(settings.groq_api_key, settings.groq_model)
        self.embeddings = embeddings or Embeddings(settings.embedding_model, settings.data_dir / "models")
        self.cache = Cache(settings.database_url, settings.cache_ttl_seconds, settings.cache_max_entries)
        self._lock = threading.Lock()
        self.metrics = {"requests": 0, "cache_hits": 0, "llm_calls": 0, "tokens_used": 0}

    def close(self):
        self.provider.close()
        self.cache.close()

    def context(self):
        policies, version, sections = load_policies(self.settings.policies_path)
        key = f"{version}|{self.settings.groq_model}|{self.settings.embedding_model}|{PROMPT_VERSION}"
        return policies, hashlib.sha256(key.encode()).hexdigest(), sections

    def stats(self):
        _, namespace, _ = self.context()
        with self._lock:
            metrics = self.metrics.copy()
        return {**metrics, "entries": self.cache.count(namespace), "threshold": self.settings.similarity_threshold, "database": "PostgreSQL + pgvector"}

    def chat(self, request: ChatRequest) -> ChatResponse:
        start = time.perf_counter()
        policies, namespace, sections = self.context()
        with self._lock:
            self.metrics["requests"] += 1

        # Complete questions work across chats and within the current chat.
        # Referential follow-ups are scoped to the exact supplied history.
        history = request.history if needs_history(request.message) else []
        context_key = "standalone"
        if history:
            serialized = json.dumps([message.model_dump() for message in history], sort_keys=True)
            context_key = hashlib.sha256(serialized.encode()).hexdigest()
        permitted = reusable_request(request.message)
        if history:
            permitted = permitted and all(reusable_request(message.content) for message in history)
        threshold = self.settings.similarity_threshold
        vector, nearest = None, None
        candidates = 0
        note = "Cache disabled for this message."

        if request.use_cache:
            try:
                vector = self.embeddings.encode(request.message)
            except Exception as exc:
                logger.warning("Embedding failed (%s)", type(exc).__name__)
                raise ProviderError("The local embedding model could not run. Check the server log and model download, then retry. No model API call was made.", 503) from exc
            if len(vector) != 384:
                raise ProviderError("The configured embedding model must produce 384-dimensional vectors for this database.", 503)
            match, nearest, candidates, note = search(self.cache, namespace, vector, request.message, context_key, threshold)
            if not permitted:
                match = None
                note = "Embedding compared; request details prevent shared answer reuse."
            if match is not None:
                similarity = match["similarity"]
                with self._lock:
                    self.metrics["cache_hits"] += 1
                source = "exact_cache" if match["prompt"] == normalize(request.message) else "semantic_cache"
                return ChatResponse(
                    answer=match["answer"], category="policy", source=source, sources=match["sources"],
                    similarity=round(similarity, 4), latency_ms=round((time.perf_counter() - start) * 1000),
                    cached=False, cache_note="Embedding matched a compatible saved answer. No model API call was made.",
                    embedding_compared=True, candidates_checked=candidates,
                    nearest_similarity=round(nearest, 4) if nearest is not None else None, threshold=threshold,
                    matched_prompt=match["prompt"], matched_query=match["matched_query"],
                )
        with self._lock:
            self.metrics["llm_calls"] += 1
        answer, tokens = self.provider.generate(request.message, history, policies, sections)
        stored = bool(permitted and vector is not None and answer.cacheable and answer.category == "policy")
        variants = []
        if stored:
            meaning = meaning_signature(request.message)
            # Only standalone, condition-preserving alternatives are indexed.
            # They come from the same generation call, never from a preset list.
            seen = {normalize(request.message)}
            if not history and not needs_history(request.message):
                for query in answer.cache_queries:
                    query = normalize(query)
                    if query in seen or not reusable_request(query) or needs_history(query) or meaning_signature(query) != meaning:
                        continue
                    seen.add(query)
                    try:
                        alternate_vector = self.embeddings.encode(query)
                        if len(alternate_vector) != 384:
                            raise ValueError("Invalid embedding dimensions")
                    except Exception as exc:
                        # The answer has already been paid for. Keep its original
                        # vector and return it instead of losing a valid response.
                        logger.warning("Alternative embedding failed (%s)", type(exc).__name__)
                        continue
                    variants.append((query, alternate_vector))
            self.cache.save(namespace, request.message, context_key, meaning, vector, answer.answer, answer.sources, variants)
            note += f" Saved the fresh answer, original embedding, and {len(variants)} alternative wordings."
        elif vector is not None:
            note += " Response was not suitable for shared storage."
        with self._lock:
            self.metrics["tokens_used"] += tokens
        return ChatResponse(
            answer=answer.answer, category=answer.category, source="groq", sources=answer.sources,
            latency_ms=round((time.perf_counter() - start) * 1000), cached=stored, cache_note=note, tokens_used=tokens,
            embedding_compared=vector is not None, candidates_checked=candidates,
            nearest_similarity=round(nearest, 4) if nearest is not None else None, threshold=threshold,
            cache_variants=len(variants),
        )
