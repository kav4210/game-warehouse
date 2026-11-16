FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends default-jre-headless && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir pandas pyspark==3.5.1 dash plotly
COPY src/ src/
COPY dashboard/ dashboard/
COPY data/raw_*.csv data/mart_*.csv data/alerts.json data/
CMD ["python", "src/spark_pipeline.py"]
