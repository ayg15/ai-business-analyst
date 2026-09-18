import json
import logging
import re

from fastapi import FastAPI, UploadFile, HTTPException

from app.database import (
    describe_tables,
    load_default_online_retail_dataset,
    list_tables,
    run_query,
    upload_and_save_file,
)
from app.llm import OllamaError, ask_llm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()


@app.on_event("startup")
async def startup() -> None:
    load_default_online_retail_dataset()


@app.get("/health")
async def health():
    return {"status": "ok"}


def extract_sql(text: str) -> str:
    """
    Extract only SQL starting from SELECT.
    Removes explanations, markdown, and normalizes SQL for DuckDB.
    """
    if not text:
        return ""

    # Remove code blocks
    text = text.replace("```sql", "").replace("```", "")

    # Extract the first SELECT statement and discard explanations after it.
    match = re.search(r"(SELECT[\s\S]*?)(?:;|$)", text, re.IGNORECASE)

    if match:
        text = match.group(1)

    # DuckDB does not use MySQL-style backticks for quoted identifiers.
    # Convert `column_name` to "column_name" before execution.
    text = re.sub(r"`([^`]+)`", r'"\1"', text)

    return text.strip()


def predefined_sql_for_question(question: str) -> str | None:
    normalized = re.sub(r"\s+", " ", question.lower()).strip()

    if (
        "countr" in normalized
        and "revenue" in normalized
        and any(word in normalized for word in ["most", "highest", "top", "generated"])
    ):
        return """
SELECT
    country,
    ROUND(SUM(line_revenue), 2) AS revenue
FROM online_retail_sales_lines
WHERE NOT is_return
GROUP BY country
ORDER BY revenue DESC
LIMIT 10
"""

    if "monthly" in normalized and any(word in normalized for word in ["sales", "revenue"]):
        return """
SELECT
    DATE_TRUNC('month', invoice_date) AS month,
    ROUND(SUM(line_revenue), 2) AS revenue
FROM online_retail_sales_lines
WHERE NOT is_return
GROUP BY month
ORDER BY month
"""

    if "product" in normalized and "revenue" in normalized:
        return """
SELECT
    description,
    ROUND(SUM(line_revenue), 2) AS revenue
FROM online_retail_sales_lines
WHERE NOT is_return
GROUP BY description
ORDER BY revenue DESC
LIMIT 20
"""

    if "customer" in normalized and "revenue" in normalized:
        return """
SELECT
    customer_id,
    country,
    ROUND(gross_revenue, 2) AS gross_revenue,
    order_count
FROM online_retail_customers
ORDER BY gross_revenue DESC
LIMIT 20
"""

    return None


@app.post("/upload")
async def upload_file(file: UploadFile):
    try:
        return upload_and_save_file(file.file, file.filename)
    except Exception as e:
        logger.exception("File upload failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tables")
async def get_tables():
    try:
        return {"tables": list_tables()}
    except Exception as e:
        logger.exception("Could not list tables")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ask")
async def ask(question: str):
    try:
        # get current database schema to provide context to LLM
        schema_info = describe_tables()

        if not schema_info:
            raise HTTPException(
                status_code=400,
                detail="Upload at least one CSV before asking a question.",
            )

        sql_query = predefined_sql_for_question(question)

        if sql_query:
            logger.info("Using predefined SQL for question: %s", question)
        else:
            # prompt for LLM to generate SQL based on question and current database schema
            prompt = f"""
You are a senior data engineer.

IMPORTANT RULES:
- Output ONLY SQL
- No explanations
- No markdown
- Generate DuckDB SQL
- Do not use MySQL backticks
- Use double quotes for identifiers only when needed
- Must start with SELECT
- Use only these tables

Schema:
{schema_info}

Question:
{question}
"""

            raw_sql = ask_llm(prompt)

            logger.info("Raw LLM output: %s", raw_sql)
            sql_query = extract_sql(raw_sql)

        logger.info("Clean SQL: %s", sql_query)

        # Basic validation to ensure we have a SELECT query before running it
        if not sql_query.lower().strip().startswith("select"):
            raise ValueError(f"Invalid SQL generated: {sql_query}")
        result_df = run_query(sql_query)

        return {
            "question": question,
            "sql": sql_query,
            "rows": len(result_df),
            "data": json.loads(result_df.to_json(orient="records", date_format="iso")),
        }

    except HTTPException:
        raise
    except OllamaError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Error while answering question")
        raise HTTPException(status_code=500, detail=str(e))
