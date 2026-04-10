# Last Translation Benchmark (WIP 🚧)

Effort to collecting verifiable difficult-to-translate texts.
Heavily work in progress, do not use.

There are two user roles:
- **Contributor** suggests source texts, auto-translate them via [MyMemory](https://mymemory.translated.net/), define a verification method (an LLM prompt, or fallback to regex if starting with `#!regex`), and submit suggestions. Each contributor has a daily inference quota.
- **Reviewer** browses pending suggestions and awards points (0, 1, or 2) per suggestion.

## Quick start

```bash
cd web
npm install; npm run build
pip install -e .
uvicorn server:app --reload
```

<!-- TODO: print this link instead -->
Then open <http://localhost:8000>.

### Default accounts

| Username       | Password         | Role        |
|----------------|------------------|-------------|
| `reviewer1`    | `reviewer123`    | Reviewer    |
| `contributor1` | `contributor123` | Contributor |
| `contributor2` | `contributor223` | Contributor |

### Environment variables

- `OPENAI_API_KEY`: enables real LLM verification via GPT-4o-mini
- `GEMINI_API_KEY`: enables real LLM verification via Gemini