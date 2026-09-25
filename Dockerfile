# ==========================================
# STAGE 1: BUILD SVELTEKIT FRONTEND
# ==========================================

FROM node:22-slim AS frontend-builder

WORKDIR /app/frontend

# Copy frontend dependency files
COPY frontend/package*.json ./

# Install frontend dependencies
RUN npm ci

# Copy SvelteKit source code
COPY frontend/ ./

# Generate static production website
RUN npm run build


# ==========================================
# STAGE 2: PYTHON FASTAPI APPLICATION
# ==========================================

FROM python:3.12-slim

WORKDIR /app

# Python configuration
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install Python dependencies
COPY backend/requirements.txt ./backend/requirements.txt

RUN pip install --no-cache-dir \
    -r backend/requirements.txt

# Copy backend source code
COPY backend/ ./backend/

# Copy compiled frontend
COPY --from=frontend-builder \
    /app/frontend/build \
    ./frontend/build

# Hugging Face Spaces port
EXPOSE 7860

# Start FastAPI
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]