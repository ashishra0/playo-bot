# Playo Badminton Court Finder Bot

Telegram bot that searches [Playo.co](https://playo.co) for badminton courts.

## Setup

### 1. Create a Telegram Bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the bot token

### 2. Configure

```bash
cp .env.example .env
# Edit .env and paste your bot token
```

### 3. Run Locally

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python bot.py
```

### 4. Run with Docker

```bash
docker-compose up -d --build
```

## Usage

In your Telegram chat with the bot:

```
/start              — Welcome message
/help               — Full usage guide
/find koramangala 7pm
/find hsr layout 7:30pm tomorrow
/find area=indiranagar time=6pm
/find hadapsar city=pune
```

City defaults to Bangalore. Add `city=pune` (or mumbai, delhi, hyderabad, etc.) to search other cities.

## Deploy to Hetzner VPS

```bash
ssh root@your-server-ip
git clone <your-repo-url> playo-bot
cd playo-bot
cp .env.example .env
nano .env  # paste your bot token
docker-compose up -d --build
```

### Update / Redeploy

```bash
ssh root@your-server-ip
cd playo-bot
git pull
docker-compose up -d --build
```

### View Logs

```bash
docker-compose logs -f bot
```
