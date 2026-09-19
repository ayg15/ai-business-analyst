FROM python:3.12-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

FROM base AS backend

COPY app ./app
COPY ["data/Online Retail.xlsx", "./data/Online Retail.xlsx"]

EXPOSE 8000

CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS frontend

COPY app ./app

EXPOSE 8501

CMD ["streamlit", "run", "app/ui.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
