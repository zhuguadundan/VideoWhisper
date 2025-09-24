# Repository Guidelines

Concise contributor guide for this repo. Prefer small, focused changes and keep behavior stable.

## Project Structure & Module Organization
- `app/` Flask backend: `services/` (download, audio, STT, text, upload), `models/`, `utils/`, `config/`.
- `web/` Frontend assets: `templates/` (Jinja), `static/` (JS/CSS).
- `config/` Certificates/notes. Runtime config at root `config.yaml` (used locally and by Docker).
- `output/` processed artifacts; `temp/` working files. Entrypoint: `run.py`. Docker: `Dockerfile`, `docker-compose.yml`.

## Build, Test, and Development Commands
- Setup venv: `python -m venv .venv` then `. .venv/bin/activate` (Windows: `.venv\Scripts\activate`) and `pip install -r requirements.txt`.
- Run server: `python run.py`; open `http://localhost:5000` (self‑signed HTTPS on `5443` if enabled).
- Docker: `docker-compose up -d` (rebuild: `./build-docker.sh` or `build-docker.bat`).
- Smoke check: `curl http://localhost:5000/api/providers`.
- Run tests (if present): `pytest -q`.

## Coding Style & Naming Conventions
- Python PEP 8, 4‑space indent, UTF‑8. Prefer type hints and module‑level docstrings.
- Names: modules/functions `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE`.
- Logging: use `logging` (see `app/__init__.py`); avoid `print` in services.
- Formatting optional; if used run `black . && isort .`. Group imports: stdlib, third‑party, local.

## Testing Guidelines
- Place tests under `tests/` as `test_*.py` (pytest). Keep unit tests fast and deterministic.
- Minimum smoke: `/api/providers` and a simple UI end‑to‑end.
- Mock external APIs (SiliconFlow/OpenAI/Gemini) and the filesystem.

## Commit & Pull Request Guidelines
- Conventional Commits: `feat:`, `fix:`, `docs:`, `build:`, `security:`. Match existing history.
- PRs: clear description, linked issues, repro steps, and screenshots for UI changes. Call out config updates (e.g., `config.yaml` keys, ports).

## Security & Configuration Tips
- Never commit secrets, cookies, or real certificates. Use `.env` and `config.yaml`. Sensitive files under `config/` are ignored.
- To disable HTTPS locally: set `HTTPS_ENABLED=false` or adjust `config.yaml`.

## Agent‑Specific Instructions
- Keep edits surgical. Don’t move files without updating imports and Docker. Update docs when changing routes or config keys.
