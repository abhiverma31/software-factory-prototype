# Software Factory Prototype

Local Django prototype for a calculator app that can fail, accept a natural-language repair request, and hand it to a local factory worker.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py test
python manage.py runserver
```

Open `http://127.0.0.1:8000`.

To let the local worker invoke Codex CLI, install and authenticate Codex. The factory button will call `codex exec` when `codex` is available on PATH.
