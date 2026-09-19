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
from app.llm import LLMError, ask_llm

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
    asks_for_ranking = any(
        word in normalized for word in ["most", "highest", "top", "generated"]
    )
    asks_for_time_by_month = "monthly" in normalized or "month" in normalized
    asks_for_sales = "sales" in normalized or "revenue" in normalized

    if asks_for_time_by_month and "countr" in normalized and asks_for_sales:
        return """
SELECT
    DATE_TRUNC('month', invoice_date) AS month,
    country,
    ROUND(SUM(line_revenue), 2) AS revenue
FROM online_retail_sales_lines
WHERE NOT is_return AND quantity > 0 AND unit_price > 0
GROUP BY month, country
ORDER BY month, revenue DESC
"""

    if (
        "countr" in normalized
        and asks_for_sales
        and asks_for_ranking
    ):
        return """
SELECT
    country,
    ROUND(SUM(line_revenue), 2) AS revenue
FROM online_retail_sales_lines
WHERE NOT is_return AND quantity > 0 AND unit_price > 0
GROUP BY country
ORDER BY revenue DESC
LIMIT 10
"""

    if asks_for_time_by_month and asks_for_sales:
        return """
SELECT
    DATE_TRUNC('month', invoice_date) AS month,
    ROUND(SUM(line_revenue), 2) AS revenue
FROM online_retail_sales_lines
WHERE NOT is_return AND quantity > 0 AND unit_price > 0
GROUP BY month
ORDER BY month
"""

    if "product" in normalized and "revenue" in normalized and asks_for_ranking:
        return """
SELECT
    description,
    ROUND(SUM(line_revenue), 2) AS revenue
FROM online_retail_sales_lines
WHERE
    NOT is_return
    AND quantity > 0
    AND unit_price > 0
    AND description IS NOT NULL
GROUP BY description
ORDER BY revenue DESC
LIMIT 20
"""

    if "customer" in normalized and "revenue" in normalized and asks_for_ranking:
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

    if (
        "return" in normalized
        and "order" in normalized
        and ("how many" in normalized or "count" in normalized)
    ):
        return """
SELECT COUNT(*) AS returned_order_count
FROM online_retail_orders
WHERE has_return
"""

    return None


def build_sql_prompt(
    question: str,
    schema_info: str,
    previous_sql: str | None = None,
    query_error: str | None = None,
) -> str:
    correction = ""
    if query_error is not None:
        correction = f"""

The previous SQL failed.
Previous SQL:
{previous_sql or "<no valid SQL was produced>"}

DuckDB error:
{query_error}

Correct the query and return only the corrected SQL.
"""

    return f"""
You are a senior analytics engineer generating one DuckDB query.

OUTPUT RULES:
- Output only SQL, with no markdown or explanation.
- Return exactly one read-only SELECT statement.
- Use only tables and columns listed in the schema.
- Do not mix the raw online_retail table with its derived views in one query.
- Add LIMIT 200 to non-aggregate detail queries.

ONLINE RETAIL BUSINESS RULES:
- Prefer online_retail_sales_lines for sales, product, country, and return analysis.
- A completed sale has is_return = FALSE, quantity > 0, and unit_price > 0.
- Sales revenue is SUM(line_revenue) over completed sales unless the question explicitly asks for net revenue.
- Net revenue includes returns and is SUM(line_revenue).
- Return value is reported as a positive amount using ABS(line_revenue) where is_return = TRUE.
- Prefer online_retail_orders for order counts, order values, and basket analysis.
- Prefer online_retail_customers for customer-level summaries.
- Never sum a customer or order summary view after joining it to sales lines because that duplicates values.
- Use DATE_TRUNC for monthly, quarterly, or yearly analysis.

Schema:
{schema_info}

Question:
{question}
{correction}
"""


def validate_generated_sql(sql_query: str) -> None:
    if not sql_query.lower().strip().startswith("select"):
        raise ValueError(f"Invalid SQL generated: {sql_query}")


def answer_question(question: str, schema_info: str):
    predefined_sql = predefined_sql_for_question(question)
    if predefined_sql:
        logger.info("Using predefined SQL for question: %s", question)
        return predefined_sql.strip(), run_query(predefined_sql)

    previous_sql = None
    query_error = None

    for attempt in range(2):
        prompt = build_sql_prompt(
            question,
            schema_info,
            previous_sql=previous_sql,
            query_error=query_error,
        )
        raw_sql = ask_llm(prompt)
        logger.info("Raw LLM output (attempt %s): %s", attempt + 1, raw_sql)
        sql_query = extract_sql(raw_sql)

        try:
            validate_generated_sql(sql_query)
            return sql_query, run_query(sql_query)
        except Exception as exc:
            if attempt == 1:
                raise
            previous_sql = sql_query
            query_error = str(exc)
            logger.warning("Generated SQL failed; requesting one correction: %s", exc)

    raise RuntimeError("SQL generation failed after retry")


@app.post("/upload")
async def upload_file(file: UploadFile):
    try:
        if not file.filename:
            raise ValueError("Uploaded file must have a filename.")
        return upload_and_save_file(file.file, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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

        sql_query, result_df = answer_question(question, schema_info)
        logger.info("Clean SQL: %s", sql_query)

        return {
            "question": question,
            "sql": sql_query,
            "rows": len(result_df),
            "data": json.loads(result_df.to_json(orient="records", date_format="iso")),
        }

    except HTTPException:
        raise
    except LLMError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Error while answering question")
        raise HTTPException(status_code=500, detail=str(e))
