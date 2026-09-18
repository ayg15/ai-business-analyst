# AGENTS.md

Guidance for coding agents working in this repository.

## Project Overview

This is an AI business analytics assistant with:
- FastAPI backend in `app/`
- Streamlit frontend in `frontend/`
- DuckDB persistence
- Ollama-backed natural-language-to-SQL generation
- A bundled Online Retail workbook at `data/online_retail/Online Retail.xlsx`

The backend loads the Online Retail workbook at startup when available and creates these query surfaces:
- `online_retail`
- `online_retail_sales_lines`
- `online_retail_orders`
- `online_retail_customers`

## Important Files

- `app/database.py` handles file ingestion, DuckDB access, and Online Retail views.
- `app/main.py` defines FastAPI endpoints and question handling.
- `app/llm.py` calls Ollama.
- `frontend/streamlit_app.py` provides the user interface.
- `docker-compose.yml` runs Ollama, backend, and frontend together.
- `README.md` contains user-facing setup and run instructions.
- `requirements.txt` contains Python dependencies.

## Run Commands

Docker Compose:

```powershell
docker compose up --build
```

Open the app at:

```text
http://localhost:8501
```

Local backend on Windows PowerShell:

```powershell
.\env\Scripts\Activate.ps1
$env:OLLAMA_BASE_URL="http://localhost:11434"
$env:OLLAMA_MODEL="llama3.1"
uvicorn app.main:app --reload
```

Local frontend on Windows PowerShell:

```powershell
.\env\Scripts\Activate.ps1
streamlit run frontend\streamlit_app.py
```

Quick syntax check:

```powershell
.\env\Scripts\python.exe -m py_compile app\database.py app\main.py app\llm.py frontend\streamlit_app.py
```

## Data and Runtime Notes

- Do not require users to upload `Online Retail.xlsx`; the backend should load it automatically.
- In Docker, `ONLINE_RETAIL_PATH` points to `/app/data/online_retail/Online Retail.xlsx`.
- In Docker, `DATABASE_PATH` should point outside `/app/data`, currently `/app/runtime/business_analyst.duckdb`, so the runtime volume does not hide the bundled workbook.
- Local DuckDB files such as `data/business_analyst.duckdb` are runtime artifacts and should not be committed.
- The `data/` folder may be untracked while still required locally because it contains the workbook.

## Development Guidelines

- Keep changes small and aligned with the existing simple FastAPI/Streamlit structure.
- Prefer improving `app/database.py` helpers over duplicating DuckDB logic in routes.
- Preserve CSV upload support when modifying Excel upload behavior.
- Keep Online Retail fast-path SQL in `app/main.py` simple and read-only.
- Do not remove Docker support unless explicitly requested.
- Avoid committing virtual environment contents, `__pycache__`, DuckDB files, or scratch files.

## LLM and Query Behavior

- Ollama is configured through `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, and `OLLAMA_TIMEOUT_SECONDS`.
- Docker Compose uses `http://ollama:11434`; local runs usually use `http://localhost:11434`.
- Some common Online Retail questions use predefined SQL so the app can respond without waiting for Ollama.
- Generated SQL is only lightly validated today. If improving safety, enforce single-statement read-only `SELECT` behavior before execution.

## Common Verification

After backend/data changes, verify:

```powershell
.\env\Scripts\python.exe -c "from app.database import load_default_online_retail_dataset, list_tables; load_default_online_retail_dataset(); print(list_tables())"
```

Expected tables/views include:

```text
online_retail
online_retail_sales_lines
online_retail_orders
online_retail_customers
```

For the starter business question, `/ask` should answer quickly without Ollama:

```text
Which countries generated the most revenue?
```

