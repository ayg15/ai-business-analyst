import hashlib
import os
from collections.abc import Iterable

import altair as alt
import pandas as pd
import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
ANALYSIS_TIMEOUT_SECONDS = float(os.getenv("UI_ANALYSIS_TIMEOUT_SECONDS", "330"))
DATE_COLUMN_HINTS = ("date", "time", "month", "year", "quarter", "week", "day")


def error_detail(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text or f"HTTP {response.status_code}"

    if isinstance(payload, dict) and payload.get("detail"):
        return str(payload["detail"])
    return response.text or f"HTTP {response.status_code}"


def exception_detail(exc: Exception) -> str:
    if isinstance(exc, requests.RequestException) and exc.response is not None:
        return error_detail(exc.response)
    return str(exc)


def parse_api_response(
    response: requests.Response, required_fields: Iterable[str]
) -> dict:
    try:
        payload = response.json()
    except ValueError as exc:
        raise ValueError("The backend returned an invalid JSON response.") from exc

    if not isinstance(payload, dict):
        raise ValueError("The backend returned an unexpected response format.")

    missing_fields = [field for field in required_fields if field not in payload]
    if missing_fields:
        raise ValueError(
            "The backend response is missing: " + ", ".join(missing_fields)
        )
    return payload


def fetch_tables() -> tuple[list[str], str | None]:
    try:
        response = requests.get(f"{BACKEND_URL}/tables", timeout=10)
        response.raise_for_status()
        payload = parse_api_response(response, ("tables",))
        if not isinstance(payload["tables"], list):
            raise ValueError("The backend returned an invalid table list.")
        return [str(table) for table in payload["tables"]], None
    except (requests.RequestException, ValueError) as exc:
        return [], exception_detail(exc)


def prepare_chart_data(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    chart_data = df.copy()
    temporal_columns = []

    for column in chart_data.columns:
        column_name = str(column).lower()
        if not any(hint in column_name for hint in DATE_COLUMN_HINTS):
            continue

        converted = pd.to_datetime(chart_data[column], errors="coerce")
        if converted.notna().any() and converted.notna().mean() >= 0.8:
            chart_data[column] = converted
            temporal_columns.append(column)

    return chart_data, temporal_columns


def build_chart(
    df: pd.DataFrame,
    x_column: str,
    y_column: str,
    group_column: str | None,
    chart_type: str,
) -> alt.Chart:
    x_type = (
        "temporal"
        if pd.api.types.is_datetime64_any_dtype(df[x_column])
        else "nominal"
    )
    x_encoding = alt.X(field=x_column, type=x_type, title=x_column)
    if x_type == "nominal" and chart_type == "Bar":
        x_encoding = alt.X(field=x_column, type=x_type, title=x_column, sort="-y")

    tooltip_columns = [x_column, y_column]
    encoding = {
        "x": x_encoding,
        "y": alt.Y(field=y_column, type="quantitative", title=y_column),
    }

    if group_column and group_column != x_column:
        encoding["color"] = alt.Color(
            field=group_column, type="nominal", title=group_column
        )
        tooltip_columns.append(group_column)

    encoding["tooltip"] = [
        alt.Tooltip(
            field=column,
            type=(
                "quantitative"
                if column == y_column
                else "temporal"
                if pd.api.types.is_datetime64_any_dtype(df[column])
                else "nominal"
            ),
            title=column,
        )
        for column in tooltip_columns
    ]

    chart = alt.Chart(df)
    if chart_type == "Line":
        chart = chart.mark_line(point=True)
    else:
        chart = chart.mark_bar()

    return chart.encode(**encoding).properties(height=400)


def show_chart(df: pd.DataFrame) -> None:
    chart_data, temporal_columns = prepare_chart_data(df)
    numeric_columns = chart_data.select_dtypes(include="number").columns.tolist()
    dimension_columns = [
        column for column in chart_data.columns if column not in numeric_columns
    ]

    if not numeric_columns or not dimension_columns:
        return

    default_x = temporal_columns[0] if temporal_columns else dimension_columns[0]
    default_group = next(
        (column for column in dimension_columns if column != default_x), "None"
    )
    schema_key = hashlib.sha256(
        "|".join(map(str, chart_data.columns)).encode("utf-8")
    ).hexdigest()[:10]

    control_columns = st.columns(4)
    with control_columns[0]:
        x_column = st.selectbox(
            "X-axis",
            dimension_columns,
            index=dimension_columns.index(default_x),
            key=f"chart_x_{schema_key}",
        )
    with control_columns[1]:
        y_column = st.selectbox(
            "Y-axis", numeric_columns, key=f"chart_y_{schema_key}"
        )
    with control_columns[2]:
        group_selection = st.selectbox(
            "Group",
            ["None", *dimension_columns],
            index=["None", *dimension_columns].index(default_group),
            key=f"chart_group_{schema_key}",
        )
    with control_columns[3]:
        chart_type = st.selectbox(
            "Chart type",
            ["Line", "Bar"] if default_x in temporal_columns else ["Bar", "Line"],
            key=f"chart_type_{schema_key}",
        )

    group_column = None if group_selection == "None" else group_selection
    chart = build_chart(chart_data, x_column, y_column, group_column, chart_type)
    st.altair_chart(chart, width="stretch")


def render_analysis(data: dict) -> None:
    st.subheader("Results")
    st.code(data["sql"], language="sql")

    df = pd.DataFrame(data["data"])
    st.caption(f"{len(df):,} row(s)")
    st.dataframe(df, width="stretch")

    if df.empty:
        st.info("The query returned no rows.")
    else:
        show_chart(df)


def main() -> None:
    st.set_page_config(page_title="AI Business Analyst", layout="wide")
    st.title("AI Business Analyst Assistant")

    if "uploaded_file_keys" not in st.session_state:
        st.session_state.uploaded_file_keys = set()
    if "analysis_result" not in st.session_state:
        st.session_state.analysis_result = None

    tables, backend_error = fetch_tables()
    backend_available = backend_error is None

    with st.sidebar:
        st.caption(f"Backend: {BACKEND_URL}")
        if backend_available:
            st.success("Backend connected")
        else:
            st.error("Backend unavailable")

    if backend_error:
        st.error(f"Cannot connect to the backend: {backend_error}")

    uploaded_files = st.file_uploader(
        "Upload CSV or Excel files",
        type=["csv", "xlsx"],
        accept_multiple_files=True,
        disabled=not backend_available,
    )

    upload_clicked = st.button(
        "Upload files",
        disabled=not backend_available or not uploaded_files,
    )

    if upload_clicked and uploaded_files:
        uploaded_any = False
        for uploaded_file in uploaded_files:
            file_bytes = uploaded_file.getvalue()
            file_key = hashlib.sha256(
                uploaded_file.name.encode("utf-8") + file_bytes
            ).hexdigest()

            if file_key in st.session_state.uploaded_file_keys:
                st.info(f"{uploaded_file.name} is already uploaded.")
                continue

            content_type = (
                "text/csv"
                if uploaded_file.name.lower().endswith(".csv")
                else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            try:
                with st.spinner(f"Uploading {uploaded_file.name}..."):
                    response = requests.post(
                        f"{BACKEND_URL}/upload",
                        files={
                            "file": (uploaded_file.name, file_bytes, content_type)
                        },
                        timeout=120,
                    )
                    response.raise_for_status()
                    upload_result = parse_api_response(response, ("message",))
            except (requests.RequestException, ValueError) as exc:
                st.error(
                    f"Upload failed for {uploaded_file.name}: {exception_detail(exc)}"
                )
                continue

            st.success(str(upload_result["message"]))
            st.session_state.uploaded_file_keys.add(file_key)
            uploaded_any = True

        if uploaded_any:
            tables, refresh_error = fetch_tables()
            if refresh_error:
                st.warning(f"Could not refresh the table list: {refresh_error}")

    if tables:
        st.caption("Available tables and views: " + ", ".join(tables))

    question = st.text_input("Ask a business question")
    normalized_question = question.strip()
    analyze_clicked = st.button(
        "Analyze",
        disabled=not backend_available or not normalized_question,
        type="primary",
    )

    if analyze_clicked:
        st.session_state.analysis_result = None
        try:
            with st.spinner("Generating and running the analysis..."):
                response = requests.get(
                    f"{BACKEND_URL}/ask",
                    params={"question": normalized_question},
                    timeout=ANALYSIS_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                data = parse_api_response(response, ("sql", "data"))
                if not isinstance(data["sql"], str) or not isinstance(
                    data["data"], list
                ):
                    raise ValueError("The backend returned an invalid analysis result.")
        except (requests.RequestException, ValueError) as exc:
            st.error(f"Analysis failed: {exception_detail(exc)}")
        else:
            st.session_state.analysis_result = data

    if st.session_state.analysis_result is not None:
        render_analysis(st.session_state.analysis_result)


if __name__ == "__main__":
    main()
