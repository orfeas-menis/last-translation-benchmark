# Last Translation Benchmark (WIP 🚧)

Effort to collecting verifiable difficult-to-translate texts.
Heavily work in progress, do not use.

There are two user roles:
- **Contributor** suggests source texts, auto-translate them via [MyMemory](https://mymemory.translated.net/), define a verification method (an LLM prompt, or fallback to regex if starting with `#!regex`), and submit submissions. Each contributor has a daily inference quota.
- **Reviewer** browses pending submissions and awards points (0, 1, or 2) per submission.

## Quick start

```bash
npm install --prefix web
npm run build --prefix web/
pip install -e .
python3 server
```

<!-- TODO: print this link instead -->
Then open <http://localhost:8000>.

### Default accounts

| Username | Password | Role        |
|----------|----------|-------------|
| `r1`     | `r1`     | Reviewer    |
| `c1`     | `c1`     | Contributor |
| `c2`     | `c2`     | Contributor |

### Environment variables

- `OPENAI_API_KEY`: enables real LLM verification via GPT-4o-mini
- `GEMINI_API_KEY`: enables real LLM verification via Gemini