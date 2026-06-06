FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# HF Spaces convention: run as user 1000
RUN useradd -m -u 1000 user

WORKDIR /app

RUN pip install "fastapi[standard]"

COPY backend/ backend/

USER user

EXPOSE 7860

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
