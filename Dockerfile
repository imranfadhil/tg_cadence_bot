# --- Stage 1: Build Static React + Tailwind Telegram Mini App ---
FROM node:22-alpine AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Featherweight Python 3.12-slim Unified Runtime (<100MB RAM) ---
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt && \
    python -c "import platform, urllib.request, ssl, certifi, shutil, os; \
    arch = 'arm64' if platform.machine() in ('aarch64', 'arm64') else 'amd64'; \
    url = f'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-{arch}'; \
    ctx = ssl.create_default_context(cafile=certifi.where()); \
    req = urllib.request.urlopen(url, context=ctx); \
    open('/usr/local/bin/cloudflared', 'wb').write(req.read()); \
    os.chmod('/usr/local/bin/cloudflared', 0o755); \
    os.makedirs('/etc/ssl/certs', exist_ok=True); \
    shutil.copyfile(certifi.where(), '/etc/ssl/certs/ca-certificates.crt') if not os.path.exists('/etc/ssl/certs/ca-certificates.crt') else None"

COPY backend/ ./backend/
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

