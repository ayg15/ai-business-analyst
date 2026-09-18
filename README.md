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

## Running the Backend

Start the FastAPI server from the repository root:

```bash
uvicorn app.main:app --reload
```

The backend exposes:
- `POST /upload` - upload CSV or Excel files
- `GET /tables` - list registered tables and views
- `GET /ask?question=<text>` - ask a business question

The LLM service must also be running locally.

## Running the Streamlit Frontend

Launch the frontend app:

```bash
streamlit run frontend/streamlit_app.py
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
4. Use the bundled Online Retail dataset or upload one or more CSV/Excel files.
5. Enter a business question in natural language.
6. Click `Analyze` to see the generated SQL and results.

Example questions for the Online Retail dataset:

- What are monthly sales by country?
- Which products generated the most revenue?
- Which countries have the highest average order value?
- How many orders include returns?
- Who are the top customers by gross revenue?

## Notes

- The backend enforces that generated SQL starts with `SELECT`.
- The LLM prompt includes only the current table schema.
- DuckDB data is persisted at `DATABASE_PATH`.
- Uploaded files replace tables with the same sanitized file or worksheet name.
