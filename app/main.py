from fastapi import FastAPI, UploadFile, HTTPException
import re

from app.database import describe_tables, list_tables, run_query, upload_csv as save_csv
from app.llm import ask_llm

app = FastAPI()


# -----------------------------
# HELPER: CLEAN SQL OUTPUT
# -----------------------------
def extract_sql(text: str) -> str:
    """
    Extract only SQL starting from SELECT.
    Removes explanations, markdown, etc.
    """

    if not text:
        return ""

    # Remove code blocks
    text = text.replace("```sql", "").replace("```", "")

    # Extract SELECT query
    match = re.search(r"(SELECT[\s\S]*)", text, re.IGNORECASE)

    if match:
        return match.group(1).strip()

    return text.strip()


# -----------------------------
# UPLOAD CSV
# -----------------------------
@app.post("/upload")
async def upload_csv(file: UploadFile):

    try:
        return save_csv(file.file, file.filename)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------
# LIST TABLES
# -----------------------------
@app.get("/tables")
async def get_tables():

    try:
        return {"tables": list_tables()}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------
# ASK QUESTION (LLM → SQL → EXECUTE)
# -----------------------------
@app.get("/ask")
async def ask(question: str):

    try:
        # -----------------------------
        # STEP 1: GET SCHEMA
        # -----------------------------
        schema_info = describe_tables()

        if not schema_info:
            raise ValueError("Upload at least one CSV before asking a question.")

        # -----------------------------
        # STEP 2: PROMPT LLM
        # -----------------------------
        prompt = f"""
You are a senior data engineer.

IMPORTANT RULES:
- Output ONLY SQL
- No explanations
- No markdown
- No backticks
- Must start with SELECT
- Use only these tables

Schema:
{schema_info}

Question:
{question}
"""

        raw_sql = ask_llm(prompt)

        print("\nRAW LLM OUTPUT:\n", raw_sql)

        # -----------------------------
        # STEP 3: CLEAN SQL
        # -----------------------------
        sql_query = extract_sql(raw_sql)

        print("\nCLEAN SQL:\n", sql_query)

        # -----------------------------
        # STEP 4: VALIDATE SQL
        # -----------------------------
        if not sql_query.lower().strip().startswith("select"):
            raise ValueError(f"Invalid SQL generated: {sql_query}")

        # -----------------------------
        # STEP 5: EXECUTE SQL
        # -----------------------------
        result_df = run_query(sql_query)

        # -----------------------------
        # STEP 6: RETURN RESPONSE
        # -----------------------------
        return {
            "question": question,
            "sql": sql_query,
            "rows": len(result_df),
            "data": result_df.to_dict(orient="records")
        }

    except Exception as e:
        print("ERROR:", str(e))
        raise HTTPException(status_code=500, detail=str(e))
