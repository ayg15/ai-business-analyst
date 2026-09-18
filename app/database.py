import logging
import os
import re
from pathlib import Path
from typing import BinaryIO

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)

DATABASE_PATH = os.getenv("DATABASE_PATH", "data/business_analyst.duckdb")
ONLINE_RETAIL_PATH = os.getenv(
    "ONLINE_RETAIL_PATH", "data/online_retail/Online Retail.xlsx"
)
Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)

db = duckdb.connect(database=DATABASE_PATH)
logger.info("Connected to DuckDB database: %s", DATABASE_PATH)


def table_name_from_filename(filename: str) -> str:
    name = Path(filename).stem
    name = re.sub(r"\W+", "_", name).strip("_").lower()
    return name or "uploaded_data"


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def table_exists(table_name: str) -> bool:
    result = db.sql(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
        params=[table_name],
    ).fetchone()
    return bool(result and result[0])


def save_dataframe(df: pd.DataFrame, table_name: str) -> dict:
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
        "Saved table '%s' with %s rows and %s columns",
        table_name,
        len(df),
        len(df.columns),
    )

    return {
        "message": f"{table_name} uploaded successfully",
        "table": table_name,
        "rows": len(df),
        "columns": list(df.columns),
    }


def create_online_retail_views() -> None:
    if not table_exists("online_retail"):
        return

    db.sql(
        """
        CREATE OR REPLACE VIEW online_retail_sales_lines AS
        SELECT
            CAST("InvoiceNo" AS VARCHAR) AS invoice_no,
            CAST("StockCode" AS VARCHAR) AS stock_code,
            CAST("Description" AS VARCHAR) AS description,
            CAST("Quantity" AS INTEGER) AS quantity,
            CAST("InvoiceDate" AS TIMESTAMP) AS invoice_date,
            CAST("UnitPrice" AS DOUBLE) AS unit_price,
            CASE
                WHEN "CustomerID" IS NULL THEN NULL
                ELSE CAST("CustomerID" AS BIGINT)
            END AS customer_id,
            CAST("Country" AS VARCHAR) AS country,
            CAST("Quantity" AS DOUBLE) * CAST("UnitPrice" AS DOUBLE) AS line_revenue,
            CAST("Quantity" AS INTEGER) < 0
                OR starts_with(CAST("InvoiceNo" AS VARCHAR), 'C') AS is_return
        FROM online_retail
        """
    )

    db.sql(
        """
        CREATE OR REPLACE VIEW online_retail_orders AS
        SELECT
            invoice_no,
            customer_id,
            country,
            MIN(invoice_date) AS invoice_date,
            COUNT(*) AS line_count,
            SUM(quantity) AS total_quantity,
            SUM(line_revenue) AS order_value,
            bool_or(is_return) AS has_return
        FROM online_retail_sales_lines
        GROUP BY invoice_no, customer_id, country
        """
    )

    db.sql(
        """
        CREATE OR REPLACE VIEW online_retail_customers AS
        SELECT
            customer_id,
            mode(country) AS country,
            MIN(invoice_date) AS first_order_date,
            MAX(invoice_date) AS last_order_date,
            COUNT(DISTINCT invoice_no) AS order_count,
            SUM(line_revenue) AS gross_revenue
        FROM online_retail_sales_lines
        WHERE customer_id IS NOT NULL
        GROUP BY customer_id
        """
    )


def save_csv(file: BinaryIO, filename: str) -> list[dict]:
    logger.info("Uploading CSV file: %s", filename)
    table_name = table_name_from_filename(filename)
    df = pd.read_csv(file)
    return [save_dataframe(df, table_name)]


def save_excel(file: BinaryIO | str | Path, filename: str) -> list[dict]:
    logger.info("Uploading Excel workbook: %s", filename)
    sheets = pd.read_excel(file, sheet_name=None)
    base_table_name = table_name_from_filename(filename)
    saved_tables = []

    for sheet_name, df in sheets.items():
        if len(sheets) == 1:
            table_name = base_table_name
        else:
            table_name = f"{base_table_name}_{table_name_from_filename(sheet_name)}"
        saved_tables.append(save_dataframe(df, table_name))

    if base_table_name == "online_retail":
        create_online_retail_views()

    return saved_tables


def upload_and_save_file(file: BinaryIO, filename: str) -> dict:
    suffix = Path(filename).suffix.lower()

    if suffix == ".csv":
        saved_tables = save_csv(file, filename)
    elif suffix in {".xlsx", ".xls"}:
        saved_tables = save_excel(file, filename)
    else:
        raise ValueError("Unsupported file type. Upload a CSV or Excel workbook.")

    return {
        "message": f"Loaded {len(saved_tables)} table(s) from {filename}",
        "tables": saved_tables,
    }


def upload_and_save_csv(file: BinaryIO, filename: str) -> dict:
    return upload_and_save_file(file, filename)


def load_default_online_retail_dataset() -> None:
    dataset_path = Path(ONLINE_RETAIL_PATH)

    if table_exists("online_retail"):
        create_online_retail_views()
        logger.info("Online Retail dataset already loaded")
        return

    if not dataset_path.exists():
        logger.info("Online Retail dataset not found at %s", dataset_path)
        return

    save_excel(dataset_path, dataset_path.name)
    logger.info("Loaded default Online Retail dataset from %s", dataset_path)


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
