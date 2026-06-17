# Python 3.12 avoids the 3.13 stdlib `audioop` removal that discord.py needs.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install deps first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code (the dataset CSV ships in the repo; no other local state is needed).
COPY . .

# Run as a non-root user.
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

# The bot is a long-running worker (no inbound port). It connects out to Discord.
CMD ["python", "bot.py"]
