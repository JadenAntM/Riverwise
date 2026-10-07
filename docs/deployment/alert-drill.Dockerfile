# Optional, isolated monitor/email drill. Do not attach a production database.
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace
COPY apps/api/requirements.txt /workspace/apps/api/requirements.txt
RUN pip install --no-cache-dir -r /workspace/apps/api/requirements.txt
COPY apps/api/app /workspace/apps/api/app
COPY scripts/phase2_alert_drill.py /workspace/scripts/phase2_alert_drill.py
COPY data/stations.json /workspace/data/stations.json
COPY tests/fixtures/wsc_additional_stations_sample.csv /workspace/tests/fixtures/wsc_additional_stations_sample.csv
EXPOSE 8013
CMD ["sh", "-c", "exec python scripts/phase2_alert_drill.py serve --state-file /tmp/riverwise-phase2-alert-drill.json --host 0.0.0.0 --port \"${PORT:-8013}\""]
