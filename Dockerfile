FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --gid 1000 app && adduser --uid 1000 --ingroup app --disabled-password --gecos "" app

WORKDIR /app

RUN mkdir /data && chown app:app /data

COPY --chown=app:app requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app . /app/

RUN chmod +x /app/manage.py

USER app

ENV PATH=/home/app/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=app.settings

ENTRYPOINT ["/usr/bin/tini", "--"]

CMD ["gunicorn", "app.wsgi:application", "--bind", "0.0.0.0:8024", "--workers", "3"]