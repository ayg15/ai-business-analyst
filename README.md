# AI Business Analyst

## Overview

This repository contains an AI-powered business analytics assistant that:
- loads the bundled Online Retail Excel workbook into DuckDB
- uploads CSV or Excel data into DuckDB
- generates SQL queries from natural language questions using an LLM service
- executes the queries and returns results
- provides a Streamlit frontend for interactive analysis

## Architecture

- `app/database.py`
  - loads `data/online_retail/Online Retail.xlsx` at startup when available
  - creates Online Retail analysis views for sales lines, orders, and customers
  - registers each uploaded CSV or Excel worksheet as a SQL table
  - lists tables, and describes table schemas

- `app/llm.py`
  - sends prompts to a local LLM endpoint
  - expects the LLM response to contain a SQL query

- `app/main.py`
  - exposes a FastAPI backend with endpoints for uploading files, listing tables, and asking business questions
  - uses the LLM to generate SQL from natural language, validates it, executes it against DuckDB, and returns the result

- `frontend/streamlit_app.py`
  - provides a Streamlit UI to upload CSV or Excel files
  - sends questions to the FastAPI backend
  - displays the generated SQL and query results

## Dataset

The default dataset is the UCI Online Retail workbook:

```bash
data/online_retail/Online Retail.xlsx
```

On startup, the backend loads the workbook into the `online_retail` table when it is available. It also creates these analysis views:

- `online_retail_sales_lines`
- `online_retail_orders`
- `online_retail_customers`

Override the workbook path with `ONLINE_RETAIL_PATH`.

## Requirements

Install dependencies from the repository:

```bash
pip install -r requirements.txt
```

An LLM provider must be available for open-ended questions. Docker Compose defaults to Ollama and pulls `llama3.1` automatically. For local runs, install Ollama and pull the model:

```bash
ollama pull llama3.1
```

The backend supports these LLM provider values:

- `ollama`
- `groq`
- `openai`
- `openai_compatible`

Use `LLM_PROVIDER` to choose the provider. Ollama is the default. Optional hosted providers require an API key and model.

The repository includes `.env.example` with non-secret defaults. Create your local `.env` before changing provider settings or adding API keys:

```powershell
Copy-Item .env.example .env
```

The local `.env` file is ignored by Git.

Default Ollama configuration:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.1
```

For a local non-Docker backend, use `localhost` instead of the Docker service name:

```powershell
$env:LLM_PROVIDER="ollama"
$env:OLLAMA_BASE_URL="http://localhost:11434"
$env:OLLAMA_MODEL="llama3.1"
```

## Running with Docker Compose

Start the full app from the repository root:

```bash
docker compose up --build
```

Then open the Streamlit app:

```text
http://localhost:8501
```

Docker Compose starts:
- Ollama on `http://localhost:11434`
- FastAPI on `http://localhost:8000`
- Streamlit on `http://localhost:8501`

The backend loads the Online Retail workbook from the image at `/app/data/online_retail/Online Retail.xlsx` and stores the DuckDB database in the `backend-data` volume at `/app/runtime`.

To use a hosted provider with Docker Compose instead, change `.env`, for example:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_api_key
LLM_MODEL=gpt-4.1-mini
```

## Running the Backend

Start the FastAPI server from the repository root:

```bash
uvicorn app.main:app --reload
```

For a local Windows PowerShell run with the included virtual environment:

```powershell
.\env\Scripts\Activate.ps1
$env:LLM_PROVIDER="ollama"
$env:OLLAMA_BASE_URL="http://localhost:11434"
$env:OLLAMA_MODEL="llama3.1"
uvicorn app.main:app --reload
```

The backend exposes:
- `POST /upload` - upload CSV or Excel files
- `GET /tables` - list registered tables and views
- `GET /ask?question=<text>` - ask a business question

For local runs, Ollama must be running. Docker Compose starts it automatically.

## Running the Streamlit Frontend

Launch the frontend app:

```bash
streamlit run frontend/streamlit_app.py
```

For a local Windows PowerShell run:

```powershell
.\env\Scripts\Activate.ps1
streamlit run frontend\streamlit_app.py
```

The frontend connects to the backend and will:
- upload CSV or Excel files to the API
- show available tables and views
- prompt the backend for SQL generation
- display the SQL query and result table
- render a bar chart when the result set has multiple columns

## Usage

1. Start the LLM service locally.
2. Start the FastAPI backend.
3. Start the Streamlit app.
4. Ask a question using the bundled Online Retail dataset, or upload one or more CSV/Excel files to analyze different data.
5. Enter a business question in natural language.
6. Click `Analyze` to see the generated SQL and results.

Example questions for the Online Retail dataset:

- Which countries generated the most revenue?
- What are monthly sales by country?
- Which products generated the most revenue?
- Which countries have the highest average order value?
- How many orders include returns?
- Who are the top customers by gross revenue?

## Notes

- The backend enforces that generated SQL starts with `SELECT`.
- The LLM prompt includes only the current table schema.
- `LLM_PROVIDER` controls which LLM backend is used for generated SQL.
- DuckDB data is persisted at `DATABASE_PATH`.
- Uploaded files replace tables with the same sanitized file or worksheet name.
- A few common Online Retail questions use predefined SQL so they return quickly without waiting for Ollama.
- Generated SQL is retried once with the DuckDB error when the first query fails.

Run the focused query-generation tests with:

```powershell
.\env\Scripts\python.exe -m unittest discover -s tests -v
```
