FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /workspace
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY VERSION ./VERSION
COPY app ./app
COPY lab ./lab
COPY real_lab ./real_lab
COPY scripts ./scripts
RUN mkdir -p /workspace/data && useradd -m -u 10001 resolveai && chown -R resolveai:resolveai /workspace/data
USER resolveai
EXPOSE 8501
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8501"]
