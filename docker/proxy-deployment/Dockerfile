# Build from repository root:
#   docker build -f docker/proxy-deployment/Dockerfile .
FROM python:3.12-slim

WORKDIR /build
RUN pip install --no-cache-dir --upgrade pip

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

# Sample app (not part of the wheel)
COPY docker/proxy-deployment/app ./sample-app

RUN pip install --no-cache-dir .

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

CMD ["fluxlit", "run", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-pidfile"]
