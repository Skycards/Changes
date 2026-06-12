FROM python:3.11-slim

# git for clone/commit/push; jq formats fetched JSON byte-identically to the
# historical commits; ca-certificates for HTTPS to the API and GitHub.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git jq ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Only the code is baked in; repo data is cloned fresh at runtime.
COPY scripts/ ./scripts/
COPY compare_airports.py ./

RUN useradd --create-home --uid 10001 runner
USER runner

ENTRYPOINT ["python", "/app/scripts/pipeline.py"]
