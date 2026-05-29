# Cohérence — API UI kit

A documentation-style reference for the single backend endpoint. The brief states there's no admin UI — the operator surface is the FastAPI Swagger at `/docs`. Rather than recreate Swagger verbatim, we present the endpoint in the brand's editorial register.

## Surface

A single page with:

1. **Header** — Cohérence wordmark + "API · v1" eyebrow + base URL chip
2. **Endpoint card** — `POST /analyze` with method pill, path, description
3. **Request panel** — request body schema, with a try-it textarea and "Envoyer" CTA
4. **Response panel** — the JSON response from the mock backend, in monospaced form
5. **Side rail** — environment variables, scoring rubric, scope reminders

## Components

- `MethodPill.jsx` — the colored method tag (POST = brick)
- `EndpointHeader.jsx` — method + path + description
- `JsonBlock.jsx` — syntax-flavored JSON with brand colors
- `SchemaTable.jsx` — request/response field table
- `EnvList.jsx` — environment variable list with chip status
- `RubricCard.jsx` — the scoring rubric breakdown
- `App.jsx` — composes the page
