FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV WEB_USE_EXTERNAL_ANALYSIS=false

WORKDIR /app

COPY decision_support.py web_app.py ./
COPY static ./static

EXPOSE 8000

CMD ["python", "web_app.py"]

