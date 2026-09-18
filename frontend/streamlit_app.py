import hashlib
import os

import altair as alt
import pandas as pd
import streamlit as st
import requests

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.title("AI Business Analyst Assistant")
st.caption(f"Backend: {BACKEND_URL}")

if "uploaded_file_keys" not in st.session_state:
    st.session_state.uploaded_file_keys = set()

uploaded_files = st.file_uploader(
    "Upload CSV or Excel files", type=["csv", "xlsx", "xls"], accept_multiple_files=True
)


if uploaded_files:
    for uploaded_file in uploaded_files:
        file_bytes = uploaded_file.getvalue()
        file_key = hashlib.sha256(
            uploaded_file.name.encode("utf-8") + file_bytes
        ).hexdigest()

        if file_key in st.session_state.uploaded_file_keys:
            continue

        try:
            response = requests.post(
                f"{BACKEND_URL}/upload",
                files={"file": (uploaded_file.name, file_bytes, "text/csv")},
                timeout=60,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            st.error(f"Upload failed: {exc}")
            st.stop()

        upload_result = response.json()
        st.success(upload_result["message"])
        st.session_state.uploaded_file_keys.add(file_key)

try:
    tables_response = requests.get(f"{BACKEND_URL}/tables", timeout=10)
    tables_response.raise_for_status()
    tables = tables_response.json()["tables"]
except requests.RequestException:
    tables = []

if tables:
    st.caption("Available tables and views: " + ", ".join(tables))

question = st.text_input("Ask a business question")


def error_detail(response: requests.Response) -> str:
    try:
        return response.json().get("detail", response.text)
    except ValueError:
        return response.text


def show_chart(df: pd.DataFrame) -> None:
    numeric_columns = df.select_dtypes(include="number").columns.tolist()

    if len(numeric_columns) == 1 and len(df.columns) > 1:
        count_col = numeric_columns[0]
        label_col = next(column for column in df.columns if column != count_col)
        chart = alt.Chart(df).mark_bar().encode(
            x=alt.X(f"{label_col}:N", title=label_col),
            y=alt.Y(f"{count_col}:Q", title=count_col),
            tooltip=[label_col, count_col],
        ).properties(
            width=700,
            height=400,
            title=f"{count_col} by {label_col}",
        )
        st.altair_chart(chart, use_container_width=True)
    elif numeric_columns:
        st.bar_chart(df[numeric_columns])


if st.button("Analyze", disabled=not question):
    try:
        response = requests.get(
            f"{BACKEND_URL}/ask", params={"question": question}, timeout=240
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        detail = error_detail(exc.response) if exc.response is not None else str(exc)
        st.error(f"Analysis failed: {detail}")
        st.stop()

    data = response.json()
    st.code(data["sql"])

    df = pd.DataFrame(data["data"])
    st.dataframe(df, width="stretch")

    if not df.empty:
        show_chart(df)
