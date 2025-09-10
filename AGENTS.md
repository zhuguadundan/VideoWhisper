# Repository Guidelines

This document helps contributors and agents work consistently across the repo. Favor small, focused changes and keep behavior stable.

## Project Structure & Module Organization
- `app/` Flask backend: `services/` (download, audio, STT, text, upload), `models/`, `utils/`, `config/`.
- `web/` Frontend assets: `templates/` (Jinja), `static/` (JS/CSS).
- `config/` Certificates and notes; runtime config is root `config.yaml` (used by local and Docker).
- `output/` processed artifacts; `temp/` working files. Entrypoint: `run.py`. Docker: `Dockerfile`, `docker-compose.yml`.

## Build, Test, and Development Commands
- Setup (venv): `python -m venv .venv && . .venv/bin/activate` (Windows: `.venv\Scripts\activate`) then `pip install -r requirements.txt`.
- Run server: `python run.py` then open `http://localhost:5000` (HTTPS uses self-signed on 5443 if enabled).
- Docker (recommended): `docker-compose up -d` or build `./build-docker.sh` / `build-docker.bat`.
- Smoke check: `curl http://localhost:5000/api/health`.

## Coding Style & Naming Conventions
- Python (PEP 8), 4-space indentation, UTF-8. Prefer type hints and module-level docstrings.
- Naming: modules/functions `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE`.
- Logging: use `logging` (see `app/__init__.py`); avoid `print` in services.
- Formatting: no enforced tool; if used, run locally (e.g., `black . && isort .`). Keep imports grouped (stdlib, third-party, local).

## Testing Guidelines
- No formal suite in repo. Add new tests under `tests/` as `test_*.py` (pytest preferred). Keep unit tests fast and deterministic.
- Minimum smoke tests: `/api/health`, `/api/providers`, and a simple end-to-end flow via the UI.
- Mock external APIs (SiliconFlow/OpenAI/Gemini) and filesystem when possible.

## Commit & Pull Request Guidelines
- Conventional Commits: `feat:`, `fix:`, `docs:`, `build:`, `security:`, etc. Match the existing history.
- PRs: clear description, linked issues, repro steps, and screenshots for UI changes. Call out config changes (e.g., `config.yaml` keys, ports).

## Security & Configuration Tips
- Never commit secrets, cookies, or real certificates. Use `.env` and `config.yaml`; `.gitignore` excludes sensitive files under `config/`.
- To disable HTTPS locally: set `HTTPS_ENABLED=false` or adjust `config.yaml`.

## Agent-Specific Instructions
- Keep edits surgical; don’t move files without updating imports/Docker. Update docs when changing routes or config keys.
