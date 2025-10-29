# Use official Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Prevents Python from writing pyc files
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY ./celery/start-celeryworker /start-celeryworker
RUN sed -i 's/\r$//g' /start-celeryworker
RUN chmod +x /start-celeryworker

COPY ./celery/start-celerybeat /start-celerybeat
RUN sed -i 's/\r$//g' /start-celerybeat
RUN chmod +x /start-celerybeat

COPY ./celery/start-flower /start-flower
RUN sed -i 's/\r$//g' /start-flower
RUN chmod +x /start-flower

# Copy project
COPY . .

# Run server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
