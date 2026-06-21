# Install

Install dependencies and start the local development environment.

## Input

Use the user's message after invoking this command as context. If there is no extra
input, install and run the default local backend setup.

## Process

1. Inspect `pyproject.toml`, `README.md`, the root `AGENTS.md`, and any relevant nested `AGENTS.md` for current setup rules.
2. Ensure a Python 3.11+ virtual environment exists.
3. Install the project with development dependencies:

   ```bash
   pip install -e ".[dev]"
   ```

4. Apply database migrations when needed:

   ```bash
   alembic upgrade head
   ```

5. Start or describe how to start the API:

   ```bash
   fastapi dev
   ```

6. Start or describe how to start the worker:

   ```bash
   mentioned-worker
   ```

   If the console script is unavailable, use `python -m src.worker`.

7. Never print secrets from `.env`.

## Output

Report:

- Dependencies: installed or already current
- Database: migration status
- API: local URL or command to run
- Worker: command to run
- Issues encountered
