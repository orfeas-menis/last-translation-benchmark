# Last Translation Benchmark (WIP 🚧)

This platform gathers inputs (text, video, audio, images, documents) that are challenging for modern machine translation systems.
Contributors submit these inputs alongside machine translation outputs and a verification rule.
With 10 approved submissions, contributors are eligible for inclusion in the upcoming research publication.

There are three user roles:
- **Contributor** suggests inputs (text,s video, images, and speech), auto-translate them, defines a verification method (e.g. an LLM prompt), and submits.
- **Reviewer** browses pending submissions and rejects, accepts, or comments.
- **Admin** with the ability to create and modify users.
Each account is associated with a magic link that can be used to login from anywhere.

## Development

```bash
# requires python >=3.12, node >= 20
npm install --prefix web
npm run build --prefix web/
# dev: includes linting hooks
pip install -e ".[dev]" && pre-commit install -c .github/.pre-commit-config.yaml
# use this one when not developing
pip install -e .
# prints login URLs
python3 server
```

The `server/` contains source code for the server.
The `web/` is the frontend code (TypeScript) which, when built, goes to `server/static/` to be served by the server.

You can specify the `--host`, `--port` and `--host-public` arguments when starting the server. 
The last is used to show the login URLs.

### Environment variables

Create `config.toml` based on `config.template.toml`
- `OPENROUTER_API_KEY`: enables real LLM translation and verification
- `LARA_API_ID` and `LARA_API_SECRET`: enables Lara API-based translation

## Contributing

We welcome bugreports and hands-on contributions.
AI-generated PRs are fine as long as you verify everything and take ownership of the changes.
Reach out to [vzouhar+ltb@ethz.ch](mailto:vzouhar+ltb@ethz.ch) with inquiries.