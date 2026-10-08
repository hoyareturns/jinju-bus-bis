FROM python:3.12-slim
WORKDIR /app
COPY mobile_app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && mkdir /data && chown 65532:65532 /data
COPY bus_data.json ./bus_data.json
COPY mobile_app ./mobile_app
ENV HOST=0.0.0.0 PORT=8765 PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 BUS_DATA_DIR=/data
USER 65532:65532
EXPOSE 8765
CMD ["python", "-m", "mobile_app.server"]
