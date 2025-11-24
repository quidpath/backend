# Use a lightweight Python base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies (including bash so the script works properly)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    build-essential \
    libgobject-2.0-0 \
    libpango-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements/ /app/requirements/
RUN pip install --no-cache-dir -r requirements/prod.txt

# Copy project files
COPY . /app

# Copy and set up start script
COPY start.sh /start.sh
RUN chmod +x /start.sh

# Environment variables
ENV DJANGO_SETTINGS_MODULE=quidpath_backend.settings.prod \
    SECRET_KEY=u$8e@()u=d*jy+nmle1t&9$#c7w(gxd&a7p&n$$pd&kw3w-oru

# Expose Django port
EXPOSE 8000

# Run using bash (not sh)
CMD ["/bin/bash", "/start.sh"]
