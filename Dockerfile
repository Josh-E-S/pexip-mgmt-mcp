# Minimal image for the Pexip Management MCP server.
#
# By default the server binds to 0.0.0.0:8000 INSIDE the container so Docker
# port-mapping can expose it. Run with `-p 127.0.0.1:8000:8000` to keep
# the host-side bind on loopback (the recommended posture when you're
# fronting it with Cloudflare Tunnel running on the host).
#
# When binding to a non-loopback host (which 0.0.0.0 is, from the
# server's POV), PEXIP_MCP_TOKEN MUST be set or the server refuses to
# start. This is the safety net against accidentally exposing an
# unauthenticated MCP server.

# Base image pinned by digest for reproducible builds (tag + digest so it stays
# readable and Dependabot's docker ecosystem can bump both). Digest is for the
# multi-arch python:3.14-slim index.
FROM python:3.14-slim@sha256:b877e50bd90de10af8d82c57a022fc2e0dc731c5320d762a27986facfc3355c1 AS builder

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml uv.lock* README.md ./
COPY src/ ./src/
RUN uv pip install --system --no-cache .


FROM python:3.14-slim@sha256:b877e50bd90de10af8d82c57a022fc2e0dc731c5320d762a27986facfc3355c1
# Copy the whole lib tree (not a version-pinned site-packages path) so a base
# image bump doesn't silently break this COPY when the python3.X directory
# name changes.
COPY --from=builder /usr/local/lib/ /usr/local/lib/
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/ /app/src/
WORKDIR /app
ENV PYTHONPATH=/app/src

RUN useradd -m -u 1000 mcp
USER mcp

EXPOSE 8000

# Probe the Management Node using the container's PEXIP_* env. Marks the
# container unhealthy if host/TLS/credentials stop working. Long start-period
# so a slow-to-reach node doesn't flap during boot.
HEALTHCHECK --interval=30s --timeout=15s --start-period=30s --retries=3 \
  CMD ["python", "-m", "pexip_mcp", "--healthcheck"]

ENTRYPOINT ["python", "-m", "pexip_mcp"]
CMD ["--http", "--host", "0.0.0.0", "--port", "8000"]
