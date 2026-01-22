# AGENTS.md (VideoWhisper)

This file is for agentic coding tools operating in this repository.
Goal: ship small, safe diffs that keep behavior stable.

## Repo layout (where things live)
- `run.py`: local entrypoint.
- `app/`: Flask backend.
  - `services/`: download/audio/STT/text/upload/task pipeline.
  - `models/`: dataclasses + JSON serialization.
  - `utils/`, `config/`: helpers + settings.
- `web/`: UI assets.
  - `templates/`: Jinja templates.
  - `static/`: JS/CSS.
- `config.yaml`: runtime config (also used by Docker). Docker variant: `config.docker.yaml`.
- `output/`: processed artifacts. `temp/`: working files.
- `Dockerfile`, `docker-compose.yml`, `build-docker.{bat,sh}`: container workflow.

## Supported environment
- Primary dev OS: Windows (cmd/PowerShell). Provide POSIX equivalents when easy.
- Python: project deps require Python >= 3.10 (yt-dlp). Repo currently runs fine on newer Python (3.13 on this machine).

## Build / run / lint / test commands

### Install
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

python -m pip install -U pip
pip install -r requirements.txt

# optional (only if you intend to run tests locally)
pip install pytest
```

### Run the app (local)
```bash
python run.py
# then open http://localhost:5000
```

### Smoke check (minimal)
```bash
curl http://localhost:5000/api/providers
```

### Docker
```bash
# Build image
build-docker.bat          # Windows
./build-docker.sh         # macOS/Linux

# Run
docker-compose up -d

# Logs / stop
docker-compose logs -f
docker-compose down
```

### Tests (pytest)
This repo uses pytest if tests are present.

Run all tests:
```bash
pytest -q
```

Run a single test file:
```bash
pytest -q tests/test_something.py
```

Run a single test function (node id):
```bash
pytest -q tests/test_something.py::test_name
```

Run tests matching a substring:
```bash
pytest -q -k "keyword"
```

Stop on first failure:
```bash
pytest -q -x
```

### Lint/format
No enforced linter config found in repo root (no `pyproject.toml` / `ruff.toml` / `setup.cfg` detected during this pass).
If you choose to format, prefer:
```bash
python -m pip install black isort
black .
isort .
```
Do not reformat unrelated files during bugfixes.

## Code style & conventions

### General philosophy
- Keep edits surgical. Don’t refactor while fixing a bug.
- Match existing local patterns first; only introduce new patterns when necessary.
- Avoid behavior changes unless explicitly requested.

### Python style
- PEP 8, 4-space indent, UTF-8.
- Prefer type hints for new/modified code.
- Prefer module-level docstrings when adding new modules.

### Imports
- Group imports: standard library, third-party, local.
- Keep imports explicit; avoid wildcard imports.
- If using isort, keep default section ordering.

### Naming
- Modules/functions/variables: `snake_case`.
- Classes: `PascalCase`.
- Constants: `UPPER_SNAKE`.

### Types
- Add types where it improves clarity at boundaries (service interfaces, API payloads, return types).
- Avoid type-suppression patterns.
- Prefer `Optional[T]` / `T | None` (depending on project style in that file) consistently within the file.

### Error handling
- Do not use empty `except` blocks.
- Catch narrow exceptions when possible.
- Preserve existing user-facing error message style (often Chinese, sometimes bilingual).
- When raising/returning errors:
  - include actionable context (what failed, which provider/step),
  - avoid leaking secrets (API keys, tokens, Authorization headers).

### Logging
- Use the `logging` module (see `app/__init__.py` for app-wide configuration).
- Avoid `print` in service code.
- Treat logs as user-visible: redact secrets and sensitive headers.

### Security / safety constraints (do not regress)
- File operations must remain constrained to `temp/` and `output/` as implemented (path traversal protections).
- Preserve SSRF-related guardrails for custom base URLs / hosts.
- Do not commit secrets, cookies, or real certificates.

### Config
- Runtime config is YAML (`config.yaml`). Docker may use `config.docker.yaml`.
- When adding config keys:
  - provide safe defaults,
  - keep backward compatibility,
  - update any relevant docs/comments.

## Frontend (web/)
- Templates: Jinja in `web/templates/`.
- Static assets: `web/static/` (Bootstrap 5 + custom JS/CSS).
- Prefer minimal DOM/JS changes; keep UI behavior stable.

## Tests
- Tests live under `tests/` as `test_*.py`.
- Keep tests deterministic and fast.
- Mock external APIs (SiliconFlow/OpenAI/Gemini) and filesystem where feasible.

## Commit / PR guidance
- Conventional commits: `feat:`, `fix:`, `docs:`, `build:`, `security:`.
- PRs should include: what changed + why, repro steps, and screenshots for UI changes.

## Editor/agent rules discovery
- Cursor rules: none found (`.cursor/rules/` and `.cursorrules` not present).
- Copilot rules: none found (`.github/copilot-instructions.md` not present).
