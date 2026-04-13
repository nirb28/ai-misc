FROM apache/superset:4.1.1

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements-local.txt
RUN pip install --no-cache-dir -r /app/requirements-local.txt

COPY superset_config.py /app/pythonpath/superset_config.py
COPY bootstrap_superset.py /app/bootstrap_superset.py
COPY mcp_server.py /app/mcp_server.py
COPY docker-entrypoint.sh /app/docker-entrypoint.sh

RUN chmod +x /app/docker-entrypoint.sh

ENV PYTHONPATH=/app/pythonpath:/app \
    SUPERSET_CONFIG_PATH=/app/pythonpath/superset_config.py \
    SUPERSET_HOME=/app/superset_home \
    SUPERSET_PORT=8088 \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8811 \
    MCP_TRANSPORT=streamable-http

EXPOSE 8088 8811

USER superset

ENTRYPOINT ["/app/docker-entrypoint.sh"]
