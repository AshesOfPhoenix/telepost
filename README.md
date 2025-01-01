# Telepost

A Telegram bot for managing and scheduling social media posts across platforms, with initial support for Threads integration.

## Features

- Connect and manage Threads accounts via Telegram
- View Threads account information
- Schedule posts (coming soon)
- Create thread sequences (coming soon)
- AI-powered post optimization (coming soon)

## Architecture

The project consists of two main components:

- **API Service**: FastAPI backend handling authentication and platform integrations
    - **Threads**: Threads API integration with [Threads API Python Library](https://marclove.com/pythreads/index.html#)
    - **Twitter**: Twitter API integration with [Twitter API Python Library](https://github.com/twitterdev/Twitter-API-v2-sample-code/tree/main/User-Auth)
- **Bot Service**: Telegram bot interface built with python-telegram-bot
    - **Telegram**: Telegram API integration with [python-telegram-bot](https://docs.python-telegram-bot.org/en/v21.9/index.html)

## Tech Stack

- Python 3.11
- FastAPI
- python-telegram-bot
- LangChain
- PostgreSQL
- Docker

## Setup

1. Clone the repository

2. Generate a Telegram bot token with @BotFather. Follow the instructions at https://core.telegram.org/api/bots

3. Generate certificates. Used for Threads authentication. Follow the instructions at https://developers.threads.net/docs/auth/overview

    3.1. Create a subdirectory for the certificates called `certs`

    3.2. Create a key and a certificate
    - openssl genrsa -out key.pem 2048
    - openssl req -new -key key.pem -out csr.pem
    - openssl x509 -req -days 365 -in csr.pem -signkey key.pem -out cert.pem

2. Create a `.env` file with the variables from the .env.example file

3. Run with Docker Compose:
   ```bash
   docker-compose up --build
   ```

## Usage

1. Start a chat with your Telegram bot
2. Use `/start` to see the welcome message
3. Connect your Threads account using `/connect`
4. View your account info with `/account`

## License

Apache License 2.0 - See LICENSE file for details