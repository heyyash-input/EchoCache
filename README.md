<p align="center"><img src="docs/images/echocache-banner.png" alt="EchoCache: Different words. Shared meaning."></p>

# EchoCache

**Ask naturally. Reuse thoughtfully.** EchoCache is a local store-policy chat app that saves reusable AI answers and finds them again when a new question has similar meaning.

> “How long do refunds usually take?” → “What is the usual refund processing time?” → one saved answer, zero Groq calls on a compatible cache hit.

Built with **FastAPI · FastEmbed · PostgreSQL + pgvector · Groq · Docker**.

## What it does

- Embeds each cache-enabled question locally and searches saved answers with pgvector.
- Reuses compatible answers across chats; matches must also agree on explicit conditions and context.
- Calls Groq on a miss, then may save the answer with alternative wordings from that same call.
- Shows the answer source, similarity, tokens, and policy citations in the interface.

The included [policies.md](policies.md) contains **fictional sample policies**. Replace it with your store's approved rules before customer use. Semantic matching is probabilistic and needs evaluation on real questions.

## Run locally with Docker

Install Docker Desktop and [uv](https://docs.astral.sh/uv/). Create one private `.env` file beside `compose.yaml`:

```dotenv
GROQ_API_KEY=YOUR_GROQ_API_KEY
GROQ_MODEL=openai/gpt-oss-120b
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
SIMILARITY_THRESHOLD=0.88
CACHE_TTL_SECONDS=86400
CACHE_MAX_ENTRIES=500
POSTGRES_PASSWORD=YOUR_URL_SAFE_DATABASE_PASSWORD
POSTGRES_PORT=5433
DATABASE_URL=postgresql://policy_desk:YOUR_URL_SAFE_DATABASE_PASSWORD@127.0.0.1:5433/policy_desk
APP_PORT=8000
```

Use the same strong password in both places. Existing installations can keep their current `.env`. Start Docker Desktop, then run from the project folder:

```powershell
uv --cache-dir .uv-cache run docker compose up -d --build --wait
```

Open **[EchoCache](http://127.0.0.1:8000)** or **[API docs](http://127.0.0.1:8000/docs)**. The first embedding request downloads the local model into a persistent Docker volume.

## How a request works

**Question → local embedding → pgvector lookup → cached answer or fresh Groq response.** General reusable answers are stored for 24 hours by default. PostgreSQL and the embedding model have separate Docker volumes, so both survive an app restart.

```powershell
uv --cache-dir .uv-cache run docker compose ps             # Check services
uv --cache-dir .uv-cache run docker compose logs -f app    # View logs
uv --cache-dir .uv-cache run docker compose down           # Stop; keep saved data
```

Code changes need `docker compose up -d --build --wait` again. Changes to `policies.md` are read from the mounted file; they also change the cache namespace.

## API

- `POST /api/chat` — ask a question with `message`, optional `history`, and `use_cache`.
- `GET /health` — app and database status.
- `GET /api/policies` — available policy sections.
- `GET /api/stats` — cache hits, model calls, tokens, and saved answers.
- `DELETE /api/cache` — clear saved answers.

The app is a **single-store local demo**. It has no login or per-user isolation; keep it on localhost. Questions and relevant history go to Groq on cache misses. Keep `.env` private. Before public access, add authentication, request limits, HTTPS, backups, and accuracy checks against real policies.
