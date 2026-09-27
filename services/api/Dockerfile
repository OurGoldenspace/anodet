FROM python:3.12-slim

WORKDIR /srv

COPY services/api/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r /srv/requirements.txt

COPY services/api/app /srv/app
COPY data/cmapss/train_FD001.txt /data/cmapss/train_FD001.txt

ENV ANODET_DATA=/data/cmapss/train_FD001.txt
ENV ANODET_DB=/var/lib/anodet/anodet.db
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
