FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./

COPY src/ ./src/

RUN uv sync --frozen --no-dev

COPY . .

CMD ["uv", "run", "python", "main.py"]