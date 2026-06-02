import re
from pathlib import Path

import duckdb
import pandas as pd


db = duckdb.connect(database=":memory:")


def table_name_from_filename(filename: str) -> str:
    name = Path(filename).stem
    name = re.sub(r"\W+", "_", name).strip("_").lower()
    return name or "uploaded_data"


def upload_csv(file, filename: str) -> dict:
    df = pd.read_csv(file)
    table_name = table_name_from_filename(filename)

    db.register(table_name, df)

    return {
        "message": f"{table_name} uploaded successfully",
        "table": table_name,
        "columns": list(df.columns),
    }


def list_tables() -> list[str]:
    return [table[0] for table in db.sql("SHOW TABLES").fetchall()]


def describe_tables() -> str:
    schema_info = ""

    for table_name in list_tables():
        columns = db.sql(f"DESCRIBE {table_name}").df()
        schema_info += f"\nTable: {table_name}\n"
        schema_info += columns.to_string()
        schema_info += "\n"

    return schema_info


def run_query(sql_query: str) -> pd.DataFrame:
    return db.sql(sql_query).df()
