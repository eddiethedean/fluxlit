# Build from repository root:
#   docker build -f docker/proxy-deployment/Dockerfile .
# python:3.12-slim @ sha256:ec948fa5f90f4f8907e89f4800cfd2d2e91e391a4bce4a6afa77ba265bc3a2fe
FROM python@sha256:ec948fa5f90f4f8907e89f4800cfd2d2e91e391a4bce4a6afa77ba265bc3a2fe

WORKDIR /build
RUN pip install --no-cache-dir --upgrade pip

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

# Canonical smoke app (not part of the wheel)
COPY examples/smoke_app ./sample-app

RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /build

USER appuser

# COPY placed app under /build/sample-app (see COPY … ./sample-app above)
WORKDIR /build/sample-app
# FluxLit imports the target module by name; cwd is not always on sys.path.
ENV PYTHONPATH=/build/sample-app
ENV PYTHONUNBUFFERED=1
# Browser-visible prefix must match nginx location (see nginx.conf).
ENV FLUXLIT_ROOT_PATH=/myapp
ENV FLUXLIT_TRUST_PROXY=1
ENV FLUXLIT_GATEWAY_HOST=0.0.0.0
ENV FLUXLIT_GATEWAY_PORT=8000

EXPOSE 8000

CMD ["fluxlit", "run", "app:app", "--host", "0.0.0.0", "--port", "8000", "--no-pidfile"]
