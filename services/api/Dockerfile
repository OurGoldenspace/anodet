FROM python:3.12-slim

WORKDIR /srv

COPY services/api/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r /srv/requirements.txt

COPY services/api/app /srv/app
COPY data/cmapss/train_FD001.txt /data/cmapss/train_FD001.txt

ENV ANODET_DATA=/data/cmapss/train_FD001.txt
ENV ANODET_DB=/var/lib/anodet/anodet.db
ENV PYTHONUNBUFFERED=1

ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=90s --retries=8 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8000'))"

CMD ["sh", "-c", "python -m uvicorn app.main:app --host :: --port ${PORT:-8000}"]
