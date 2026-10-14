FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY pyproject.toml README.md ./
COPY xianyu_workbench ./xianyu_workbench
RUN pip install --no-cache-dir --no-deps .     && useradd --create-home --uid 10001 workbench     && mkdir -p /app/data && chown -R workbench:workbench /app/data
USER workbench
EXPOSE 8099
CMD ["xianyu-workbench", "serve", "--host", "0.0.0.0", "--port", "8099"]
