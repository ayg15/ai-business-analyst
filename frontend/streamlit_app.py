import streamlit as st
import requests
import pandas as pd
import hashlib

st.title("AI Business Analyst Assistant")

if "uploaded_file_keys" not in st.session_state:
    st.session_state.uploaded_file_keys = set()

uploaded_files = st.file_uploader(
    "Upload CSV Files", type=["csv"], accept_multiple_files=True
)

if uploaded_files:

    for uploaded_file in uploaded_files:
        file_bytes = uploaded_file.getvalue()
        file_key = hashlib.sha256(
            uploaded_file.name.encode("utf-8") + file_bytes
        ).hexdigest()

        if file_key in st.session_state.uploaded_file_keys:
            continue

        response = requests.post(
            "http://localhost:8000/upload",
            files={"file": (uploaded_file.name, file_bytes, "text/csv")},
            timeout=60,
        )
        response.raise_for_status()

        st.success(response.json()["message"])
        st.session_state.uploaded_file_keys.add(file_key)

question = st.text_input("Ask a business question")

if st.button("Analyze") and question:

    response = requests.get(
        "http://localhost:8000/ask", params={"question": question}, timeout=180
    )
    response.raise_for_status()

    data = response.json()

    st.code(data["sql"])

    df = pd.DataFrame(data["data"])

    st.dataframe(df)

    if len(df.columns) > 1:
        st.bar_chart(df.iloc[:, 1])
