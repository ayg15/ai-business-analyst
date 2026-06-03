import re
import logging
from fastapi import FastAPI, UploadFile, HTTPException
from app.database import (
    describe_tables, 
    list_tables, 
    run_query, 
    upload_and_save_csv
)
from app.llm import ask_llm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()


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

    # Extract SELECT query
    match = re.search(r"(SELECT[\s\S]*)", text, re.IGNORECASE)

    if match:
        text = match.group(1)

    # DuckDB does not use MySQL-style backticks for quoted identifiers.
    # Convert `column_name` to "column_name" before execution.
    text = re.sub(r"`([^`]+)`", r'"\1"', text)

    return text.strip()


@app.post("/upload")
async def upload_csv(file: UploadFile):
    try:
        return upload_and_save_csv(file.file, file.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tables")
async def get_tables():
    try:
        return {"tables": list_tables()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ask")
async def ask(question: str):

    try:
        # get current database schema to provide context to LLM
        schema_info = describe_tables()

        if not schema_info:
            raise ValueError("Upload at least one CSV before asking a question.")

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
            "data": result_df.to_dict(orient="records")
        }

    except Exception as e:
        logger.exception("Error while answering question")
        raise HTTPException(status_code=500, detail=str(e))
