# Use official Python image (pin to Bookworm for stable mirrors; avoids Trixie network issues)
FROM python:3.10-slim-bookworm

# Set working directory
WORKDIR /app

# Prevents Python from writing pyc files
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies for Playwright Chromium (retry once on network failure)
RUN apt-get update && (apt-get install -y \
    wget \
    ca-certificates \
    fonts-liberation \
    fonts-noto-color-emoji \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    libx11-6 \
    libxcb1 \
    libxext6 \
    libglib2.0-0 \
    || (sleep 10 && apt-get update && apt-get install -y \
        wget ca-certificates fonts-liberation fonts-noto-color-emoji \
        libasound2 libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 libcups2 \
        libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 libnspr4 libnss3 \
        libxcomposite1 libxdamage1 libxfixes3 libxkbcommon0 libxrandr2 \
        libx11-6 libxcb1 libxext6 libglib2.0-0)) \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Install Playwright browsers (chromium only)
RUN playwright install chromium

COPY ./celery_scripts/start-celeryworker /start-celeryworker
RUN sed -i 's/\r$//g' /start-celeryworker
RUN chmod +x /start-celeryworker

COPY ./celery_scripts/start-celerybeat /start-celerybeat
RUN sed -i 's/\r$//g' /start-celerybeat
RUN chmod +x /start-celerybeat

COPY ./celery_scripts/start-flower /start-flower
RUN sed -i 's/\r$//g' /start-flower
RUN chmod +x /start-flower

# Copy project
COPY . .

# Run server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
