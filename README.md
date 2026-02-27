# Last Translation Benchmark (WIP 🚧)

Effort to collecting verifiable difficult-to-translate texts.
Heavily work in progress, do not use.

## Features

- **Annotator** suggests source texts, auto-translate them via [MyMemory](https://mymemory.translated.net/), define a verification method (regex or LLM prompt), and submit suggestions. Each annotator has a daily inference quota.
- **Senior reviewer** browses pending suggestions and awards points (0 to 3) per suggestion.

## Quick start

```bash
pip install .
# TODO replace with script "last-translation-benchmark"
uvicorn main:app --reload
```

<!-- TODO: print this link instead -->
Then open <http://localhost:8000>.

### Default accounts

| Username     | Password    | Role       |
|-------------|-------------|------------|
| `senior1`   | `senior123` | Senior     |
| `annotator1`| `ann123`    | Annotator  |
| `annotator2`| `ann456`    | Annotator  |

### Environment variables

- `OPENAI_API_KEY`: enables real LLM verification via GPT-4o-mini