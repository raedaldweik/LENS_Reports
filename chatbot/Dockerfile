# Build from the REPO ROOT so the CSVs are in the build context:
#   docker build -f chatbot/Dockerfile -t rta-assistant .

# ── Stage 1: build the React frontend ──
FROM node:20-alpine AS frontend
WORKDIR /build
COPY chatbot/frontend/package*.json ./
RUN npm ci
COPY chatbot/frontend/ ./
RUN npm run build

# ── Stage 2: Python backend + built frontend ──
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app/backend

COPY chatbot/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY chatbot/backend/ .
COPY --from=frontend /build/dist /app/frontend/dist

# Ship the datasets with the image (data.py also falls back to the GitHub Pages URLs)
COPY alerts.csv violations.csv /app/backend/data/

EXPOSE 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
