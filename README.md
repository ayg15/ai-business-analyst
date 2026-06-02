# AI Business Analyst

## Overview

This repository contains an AI-powered business analytics assistant that:
- uploads CSV data into an in-memory DuckDB database
- generates SQL queries from natural language questions using an LLM service
- executes the queries and returns results
- provides a Streamlit frontend for interactive analysis

## Architecture

- `app/database.py`
  - loads CSV files into an in-memory DuckDB instance
  - registers each uploaded CSV as a SQL table
  - lists tables, and describes table schemas

- `app/llm.py`
  - sends prompts to a local LLM endpoint
  - expects the LLM response to contain a SQL query

- `app/main.py`
  - exposes a FastAPI backend with endpoints for uploading CSVs, listing tables, and asking business questions
  - uses the LLM to generate SQL from natural language, validates it, executes it against DuckDB, and returns the result

- `frontend/streamlit_app.py`
  - provides a Streamlit UI to upload CSV files
  - sends questions to the FastAPI backend
  - displays the generated SQL and query results

## Requirements

Install dependencies from the repository:

```bash
pip install -r requirements.txt
```

## Running the Backend

Start the FastAPI server from the repository root:

```bash
uvicorn app.main:app --reload
```

The backend exposes:
- `POST /upload` — upload CSV files
- `GET /tables` — list registered tables
- `GET /ask?question=<text>` — ask a business question

> The LLM service must also be running locally

## Running the Streamlit Frontend

Launch the frontend app:

```bash
streamlit run frontend/streamlit_app.py
```

The frontend connects to the backend and will:
- upload CSV files to the API,
- prompt the backend for SQL generation,
- display the SQL query and result table,
- render a bar chart when the result set has multiple columns.

## Usage

1. Start the LLM service locally.
2. Start the FastAPI backend.
3. Start the Streamlit app.
4. Upload one or more CSV files.
5. Enter a business question in natural language.
6. Click `Analyze` to see the generated SQL and results.

## Notes

- The backend enforces that generated SQL starts with `SELECT`.
- The LLM prompt includes only the current table schema.
- Uploaded CSV files are stored in memory and available only while the backend is running.
