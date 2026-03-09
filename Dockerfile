# ── Frontend build stage ──
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ .
RUN npm run build

# ── Backend stage ──
FROM python:3.12-slim
WORKDIR /app

# Install CPU-only PyTorch first (~200MB instead of ~2GB)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY backend/ backend/
COPY --from=frontend /app/frontend/dist frontend/dist

RUN mkdir -p /app/data

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
