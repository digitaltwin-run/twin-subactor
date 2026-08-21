FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a

RUN useradd --create-home --uid 10001 twin
RUN apt-get update \
    && apt-get install --yes --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY src /app/src
COPY config /app/config
ENV PYTHONPATH=/app/src

USER 10001:10001
EXPOSE 8188
ENTRYPOINT ["python", "-m", "twin_subactor.cli"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8188"]
