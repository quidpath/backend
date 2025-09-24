# ✅ Use a lightweight Python base image
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev gcc build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/ /app/requirements/
RUN pip install --no-cache-dir -r requirements/prod.txt

COPY . /app

COPY start.sh /start.sh
RUN chmod +x /start.sh

ENV DJANGO_SETTINGS_MODULE=quidpath_backend.settings.prod \
    SECRET_KEY=u$8e@()u=d*jy+nmle1t&9$#c7w(gxd&a7p&n$$pd&kw3w-oru

EXPOSE 8000

CMD ["sh", "/start.sh"]
