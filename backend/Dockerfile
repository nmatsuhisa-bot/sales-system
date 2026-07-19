FROM python:3.11-slim

# WeasyPrint(PDF生成)が必要とするシステムライブラリと日本語フォント。
# これが無いと import 時に libgobject/libpango が見つからず、PDF添付ができない
# （HTML添付にフォールバックする）。
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
      libffi-dev shared-mime-info fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Renderは $PORT で待ち受けを要求する。ローカル(docker-compose)では既定8000。
ENV PORT=8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
