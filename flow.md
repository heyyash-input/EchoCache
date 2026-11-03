# Semantic cache request flow

```mermaid
flowchart TD
    A[Receive and validate message] --> B{Cache enabled?}
    B -- Yes --> C[Embed every new message locally]
    C -- Model failure --> E[Return clear error without an API call]
    C --> D[PostgreSQL pgvector cosine search over active vectors]
    D --> F{Similarity, meaning conditions, and context compatible?}
    F -- Yes --> G[Return the saved answer with zero API tokens]
    F -- No --> H[Call Groq with policies and relevant history]
    B -- No --> H
    H --> I[Validate response and policy citations]
    I --> J{Reusable policy answer and cache enabled?}
    J -- Yes --> K[Save prompt, vector384, answer, context, and expiry in PostgreSQL]
    J -- No --> L[Return fresh response]
    K --> L
```

- No predefined question list or topic-keyword requirement controls embedding lookup.
- Every cache-enabled question is compared, including follow-ups and first-person wording.
- Complete questions can share answers within the same chat; referring follow-ups require matching history.
- Numbers and explicit conditions are checked because opposite questions can have high cosine similarity.
- A failed embedding never silently spends model tokens.
- Scope, similarity, and model decisions remain imperfect; inspect real queries before production use.

PostgreSQL runs through `compose.yaml` with a persistent Docker volume. Similarity is computed by pgvector in SQL; Python receives the best compatible answer and diagnostics. Time units and normalized number wording are also checked.
