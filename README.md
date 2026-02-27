# last-translation-benchmark

A Humanity's Last Exam–style interface for collecting difficult-to-translate texts.

## Features

- **Annotator** — suggest source texts, auto-translate them via [MyMemory](https://mymemory.translated.net/), define a verification method (regex or LLM prompt), and submit suggestions. Each annotator has a configurable daily inference quota.
- **Senior reviewer** — browse pending suggestions and award 0–3 points per suggestion.

## Quick start

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Then open <http://localhost:8000>.

### Default accounts

| Username     | Password    | Role       |
|-------------|-------------|------------|
| `senior1`   | `senior123` | Senior     |
| `annotator1`| `ann123`    | Annotator  |
| `annotator2`| `ann456`    | Annotator  |

### Environment variables

| Variable        | Default | Description                          |
|----------------|---------|--------------------------------------|
| `DAILY_QUOTA`  | `10`    | Max translation API calls per user per day |
| `OPENAI_API_KEY` | _(empty)_ | Optional — enables real LLM verification via GPT-4o-mini |

## Stack

- **Backend**: FastAPI + SQLite (`main.py`)
- **Frontend**: TypeScript + jQuery, compiled by webpack into `static/`
  - `web/src/index.ts` — login page (auto-redirects by role)
  - `web/src/annotator.ts` — annotator view
  - `web/src/senior.ts` — senior reviewer view
  - `web/src/api.ts` — typed API connector (shared)