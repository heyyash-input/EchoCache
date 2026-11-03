<p align="center">
  <img src="static/logo.svg" width="88" alt="EchoCache Echo Fold logo">
</p>

<h1 align="center">EchoCache</h1>
<p align="center"><strong>Different words. Shared meaning. Fewer repeat API calls.</strong></p>
<p align="center">A policy assistant that remembers reusable answers through semantic search.</p>
<p align="center">Python · FastAPI · FastEmbed · PostgreSQL + pgvector · Groq · Docker</p>

![EchoCache interface with the Echo Fold logo, policy chat, and semantic cache controls](docs/images/echocache-preview.jpg)

## Why EchoCache?

“How long do refunds usually take?” and “What is the usual refund processing time?” can ask for the same information. EchoCache embeds each incoming question, searches saved answers in PostgreSQL, and reuses a compatible response. A cache hit makes **zero Groq calls** and consumes **zero generation tokens**. Embedding and database work still use local CPU and memory.

This repository is a working **single-store, local demo** using fictional policies. It cannot look up an actual order, track a personal refund, or perform cancellations.

## What you can explore

- **Meaning-based lookup:** local, 384-dimensional embeddings with pgvector cosine search.
- **Learning from fresh questions:** one Groq response supplies the answer and up to five alternative wordings. Compatible alternatives are embedded and stored alongside the original question.
- **Matching safeguards:** explicit quantities, time units, negation, selected conditions, and conversation context must agree.
- **Visible decisions:** each reply exposes its source, similarity, token usage, and cache diagnostics.
- **Policy grounding:** answers cite sections of the editable policy document; unrelated requests are redirected.
- **Persistent storage:** Docker volumes retain saved answers and downloaded models across container recreation.

## Run it locally

**You need:** Docker Desktop running (or Docker Engine with Compose), Git, [uv](https://docs.astral.sh/uv/), and a Groq API key with access to the configured model. Initial setup requires internet access to download images, dependencies, and the embedding model.

### 1. Get the project

Clone this repository and open a terminal in its root folder.

### 2. Create one private `.env`

Create `.env` beside `compose.yaml`, using the following settings. Replace both password placeholders with the **same strong password** and add your own API key. A URL-safe password avoids escaping; otherwise URL-encode the password inside `DATABASE_URL`.

```dotenv
GROQ_API_KEY=YOUR_GROQ_API_KEY
GROQ_MODEL=openai/gpt-oss-120b
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
SIMILARITY_THRESHOLD=0.88
CACHE_TTL_SECONDS=86400
CACHE_MAX_ENTRIES=500
POSTGRES_PASSWORD=YOUR_DATABASE_PASSWORD
POSTGRES_PORT=5433
DATABASE_URL=postgresql://policy_desk:YOUR_DATABASE_PASSWORD@127.0.0.1:5433/policy_desk
APP_PORT=8000
```

`.env` stays on your machine. Git ignores it and Docker excludes it from the image. Compose injects settings at runtime and switches the database host to `postgres:5432` inside the Docker network. Existing installations can keep their configured `.env`.

### 3. Start the complete stack

```powershell
uv --cache-dir .uv-cache run docker compose up -d --build --wait
```

Open **[EchoCache](http://127.0.0.1:8000)** or the **[interactive API docs](http://127.0.0.1:8000/docs)**. The first cache-enabled question may take longer while the embedding model downloads. `API configured` indicates that a key is present; it does not validate provider access.

### 4. Try a semantic hit

Ask **“How long do refunds usually take?”**, then **“What is the usual refund processing time?”**. Open *How this answer was found* to inspect the match. A fresh installation needs a reusable answer before a cache hit is possible.

A Docker smoke check of this pair returned a semantic hit at **0.9841 similarity with zero generation tokens**, including after recreating the app container. This is one observed example, not a benchmark or a guarantee for other wording.

## The request journey

```mermaid
flowchart TD
    A[Browser sends a question] --> B[FastAPI validates input]
    B --> C{Cache enabled?}
    C -- Yes --> D[Create local embedding]
    D --> E[pgvector searches original and alternative questions]
    E --> F{Similarity, conditions and context match?}
    F -- Yes --> G[Return saved answer: zero Groq calls]
    F -- No --> H[Groq answers from policies]
    C -- No --> H
    H --> I{Reusable policy answer with cache enabled?}
    I -- Yes --> J[Validate alternative wordings and embed locally]
    J --> K[Save answer, vectors, context and expiry]
    I -- No --> L[Return fresh response]
    K --> L
```

The app performs exact cosine search in PostgreSQL over a bounded cache. A fresh answer may include extra tokens for alternative wordings, which can improve later reuse. General questions can share answers across chats; referential follow-ups use a fingerprint of supplied history. Policy, model, and prompt-version changes isolate old entries. Defaults are **24-hour expiry** and **500 saved answers**, each with up to five alternative vectors.

Similarity does not prove equivalence. The safeguards and context detector are heuristics; the system can miss paraphrases or accept an incorrect match. Higher `SIMILARITY_THRESHOLD` values generally make reuse stricter. Validate against your own policies and questions before customer use.

## Customize the policies

Edit [policies.md](policies.md), keeping the `## Section title` format. It is mounted read-only into the app container, so the service reads host-file updates on subsequent requests. Changing its contents changes the cache namespace. The shipped interface explicitly labels these policies as samples.

## Project map

```text
app/
  main.py             FastAPI routes and lifecycle
  config.py           Private runtime configuration
  models.py           Request and response validation
  embeddings.py       Local FastEmbed inference
  semantic_search.py  SQL cosine search and candidate selection
  cache.py            PostgreSQL storage, pooling and eviction
  schema.sql          Answer and alternative-vector tables
  guardrails.py       Context and explicit-condition checks
  llm.py              Groq instructions and output validation
  policies.py         Policy loading and fingerprinting
  service.py          Request orchestration and metrics
static/               Chat interface and Echo Fold SVG
policies.md           Sample store policies
Dockerfile            App image with a uv environment
compose.yaml          App, PostgreSQL and persistent volumes
docs/images/          README screenshot
```

## API at a glance

- `POST /api/chat` — ask a question; accepts `message`, `history`, and `use_cache`.
- `GET /health` — application and database health, plus key-presence status.
- `GET /api/policies` — available policy sections.
- `GET /api/stats` — requests, cache hits, model calls, tokens, and saved-answer count.
- `DELETE /api/cache` — clear saved answers and their alternative vectors.

Example request body:

```json
{"message":"How long do refunds usually take?","history":[],"use_cache":true}
```

## Everyday Docker commands

```powershell
# Check health
uv --cache-dir .uv-cache run docker compose ps
# Follow app logs; Ctrl+C exits the log viewer
uv --cache-dir .uv-cache run docker compose logs -f app
# Rebuild after code edits or recreate after .env changes
uv --cache-dir .uv-cache run docker compose up -d --build --wait
# Stop the stack and preserve its volumes
uv --cache-dir .uv-cache run docker compose down
```

Set `APP_PORT=8001` in `.env` if port 8000 is occupied, then use port 8001 in your browser. Do not use `down --volumes` unless you intend to delete stored database and model data. PostgreSQL passwords are initialized when its data volume is first created; changing `.env` alone does not rotate an existing database password.

The Compose project retains the name `policy-desk` to preserve existing volumes: `policy-desk_postgres_data` and `policy-desk_model_data`. Containers run on your computer; this setup does not publish a website to the internet.

<details>
<summary><strong>Optional: run Python locally while keeping PostgreSQL in Docker</strong></summary>

Requires Python 3.12 or newer through uv. Stop the Docker app first to free port 8000.

```powershell
uv --cache-dir .uv-cache run docker compose stop app
uv --cache-dir .uv-cache sync --locked
uv --cache-dir .uv-cache run docker compose up -d --wait postgres
uv --cache-dir .uv-cache run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

</details>

## Before public deployment

EchoCache is ready for local demos and private testing. Track these items before making it available to the public:

- [ ] Add authentication and restrict `DELETE /api/cache` to authorized operators.
- [ ] Add per-user request limits and a spending limit for Groq calls.
- [ ] Decide how private questions are handled before sending them to Groq or saving them in a shared cache.
- [ ] Evaluate cache matches against real customer questions and policies; measure incorrect reuse and missed paraphrases.
- [ ] Replace `policies.md` sample content with approved store policies.
- [ ] Put the service behind HTTPS and add error monitoring.
- [ ] Document and test PostgreSQL backup and restore.

## Sharing and deployment boundaries

Source code and documentation can be shared without your credentials. `.gitignore` excludes environment files, private-key files, local databases, downloaded models, logs, editor settings, and temporary development output. `.dockerignore` allows only the application files needed to build the image.

The app runs as a non-root user, and Compose binds exposed ports to localhost. **Authentication, per-user isolation, rate limiting, and HTTPS are not implemented.** Publishing this repository does not make the running service ready for public access; add those controls before internet deployment, including protection for the cache-clear endpoint.

On cache misses, questions, relevant history, and policies are sent to Groq. Embeddings run locally. Saved general questions and answers live in PostgreSQL; browser conversation history lasts for the current page session. Request filters reduce accidental sharing but are not a complete personal-data detector. Do not enter secrets or payment details.

---

<p align="center"><strong>Ask naturally. Reuse thoughtfully.</strong></p>
