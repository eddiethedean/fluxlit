# Minimal image for `examples/docker_compose`. Adjust COPY/RUN for your project layout.
# python:3.12-slim @ sha256:ec948fa5f90f4f8907e89f4800cfd2d2e91e391a4bce4a6afa77ba265bc3a2fe
FROM python@sha256:ec948fa5f90f4f8907e89f4800cfd2d2e91e391a4bce4a6afa77ba265bc3a2fe
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser
ENV FLUXLIT_GATEWAY_HOST=0.0.0.0
EXPOSE 8000
CMD ["fluxlit", "run", "app:app"]
