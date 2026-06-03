import logging
import os
import re
from pathlib import Path

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)

DATABASE_PATH = os.getenv("DATABASE_PATH", "/app/data/business_analyst.duckdb")
Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)

db = duckdb.connect(database=DATABASE_PATH)
logger.info("Connected to DuckDB database: %s", DATABASE_PATH)


def table_name_from_filename(filename: str) -> str:
    name = Path(filename).stem
    name = re.sub(r"\W+", "_", name).strip("_").lower()
    return name or "uploaded_data"


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def upload_and_save_csv(file, filename: str) -> dict:
    logger.info("Uploading CSV file: %s", filename)
    df = pd.read_csv(file)
    table_name = table_name_from_filename(filename)
    temp_view = f"tmp_{table_name}"
    registered = False

    try:
        db.register(temp_view, df)
        registered = True
        db.sql(
            f"CREATE OR REPLACE TABLE {quote_identifier(table_name)} AS "
            f"SELECT * FROM {quote_identifier(temp_view)}"
        )
    finally:
        if registered:
            db.unregister(temp_view)

    logger.info(
        "Registered table '%s' with %s rows and %s columns",
        table_name,
        len(df),
        len(df.columns),
    )

    return {
        "message": f"{table_name} uploaded successfully",
        "table": table_name,
        "columns": list(df.columns),
    }


def list_tables() -> list[str]:
    tables = [table[0] for table in db.sql("SHOW TABLES").fetchall()]
    logger.info("Found %s table(s)", len(tables))
    return tables


def describe_tables() -> str:
    descriptions = []
    for table_name in list_tables():
        columns = db.sql(f"DESCRIBE {quote_identifier(table_name)}").df()
        descriptions.append(f"Table: {table_name}\n{columns.to_string()}")
    return "\n\n".join(descriptions)


def run_query(sql_query: str) -> pd.DataFrame:
    logger.info("Running SQL query")
    result_df = db.sql(sql_query).df()
    logger.info("Query returned %s row(s)", len(result_df))
    return result_df
