FROM python:3.11-slim

# WeasyPrint(PDF生成)が必要とするシステムライブラリと日本語フォント。
# これが無いと import 時に libgobject/libpango が見つからず失敗する。
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
      libffi-dev shared-mime-info fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
