# Use official Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Prevents Python from writing pyc files
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# System deps needed for Playwright Chromium inside slim image
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libgobject-2.0-0 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libgio-2.0-0 \
    libexpat1 \
    libdrm2 \
    libxcb1 \
    libxkbcommon0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
  && rm -rf /var/lib/apt/lists/*

# Install Python deps (including Playwright) and browser binaries
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && playwright install chromium

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
