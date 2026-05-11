# Minimal image for `examples/docker_compose`. Adjust COPY/RUN for your project layout.
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir "fluxlit>=0.4.0"
COPY . .
ENV FLUXLIT_GATEWAY_HOST=0.0.0.0
EXPOSE 8000
CMD ["fluxlit", "run", "app:app"]
