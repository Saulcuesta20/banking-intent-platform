FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# system deps for common wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    git \
 && rm -rf /var/lib/apt/lists/*

# copy only pyproject first for dependency caching
COPY pyproject.toml ./
COPY .env.example .env

# install dependencies
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir .

# copy app code
COPY app ./app
COPY data ./data
COPY tools ./tools
COPY docs ./docs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
