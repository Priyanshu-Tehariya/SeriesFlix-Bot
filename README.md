<div align="center">

<!-- Replace 'assets/banner.png' with your actual image path or GitHub image URL -->
<img src="assets/banner.png" alt="SeriesFlix Banner" width="100%">

# 📺 SeriesFlix TV Series Bot

*An Advanced, Asynchronous Anti-Flood Telegram TV Series Delivery & Indexing Engine*

[![Framework](https://img.shields.io/badge/FRAMEWORK-AIOGRAM%203.X-0088cc?style=for-the-badge&logo=telegram)](https://github.com/aiogram/aiogram)
[![Database](https://img.shields.io/badge/DATABASE-SQLALCHEMY%202.0-red?style=for-the-badge&logo=postgresql)](https://www.sqlalchemy.org/)
[![Cache](https://img.shields.io/badge/CACHE-REDIS%20CLIENT-dc382d?style=for-the-badge&logo=redis)](https://redis.io/)
[![Python](https://img.shields.io/badge/PYTHON-3.12%2B-3776ab?style=for-the-badge&logo=python)](https://python.org)
[![Visibility](https://img.shields.io/badge/REPO-PRIVATE-orange?style=for-the-badge&logo=github)]()

---

</div>

## 🚀 Overview

**SeriesFlix Bot** is a high-performance, asynchronous Telegram bot architecture built with **Aiogram 3**, **SQLAlchemy 2.0**, and **Redis**. Designed to function like an inline OTT platform inside private chats, it dynamically indexes, searches, and delivers multi-season TV series through in-place message edits without chat clutter.

---

## ✨ Features

* 🔍 **Full-Text Search:** High-performance search with Redis cache-aside (10-minute TTL).
* 📺 **OTT-Style Navigation:** In-place navigation path: `Series Selection` → `Season Picker` → `Quality Picker` → `Episode Grid`.
* 📂 **Automated Channel Indexing:** Automatically catalogues series metadata and video files whenever a media file is dropped into the index channel.
* 🛡 **Admin Moderation:** Integrated request cards with inline action controls (`Uploaded`, `Coming Soon`, `Reject`).
* 🚫 **Access Control:** User ban/unban management with DB audit logs.
* 📡 **Broadcast Engine:** Mass message delivery pipeline to all registered users.
* 📊 **Analytics Dashboard:** Real-time user metrics, series count, and system usage stats.

---

## 🛠 Tech Stack

| Layer | Technology |
| :--- | :--- |
| **Bot Framework** | Aiogram 3.15+ |
| **Database Engine** | PostgreSQL 16 (via `asyncpg`) |
| **ORM** | SQLAlchemy 2.0 Async |
| **Schema Migrations** | Alembic |
| **Caching & FSM** | Redis 7.x |
| **Configuration** | Pydantic Settings v2 |
| **Logging** | Structlog (JSON formatted) |
| **Containerization** | Docker & Docker Compose |

---

## 📂 Directory Structure

```text
tv_series_bot/
├── alembic/                # Schema migration scripts
├── assets/                 # Documentation media & banner images
│   └── banner.png
├── bot/
│   ├── database/           # SQLAlchemy models & repository layers
│   ├── filters/            # Custom filters (IsAdmin, IsIndexChannel)
│   ├── handlers/           # Aiogram routers & message handlers
│   ├── keyboards/          # Inline keyboards & CallbackData factories
│   ├── middlewares/        # DB Session, Auth, Throttling, Logging
│   ├── services/           # Core business logic
│   ├── states/             # FSM finite state machines
│   ├── utils/              # Filename parser & formatters
│   ├── __init__.py
│   ├── config.py           # Pydantic environment configuration
│   ├── loader.py           # Global singletons (Bot, Dispatcher, Redis)
│   └── main.py             # Entrypoint runner
├── docker/                 # Container configuration (Dockerfile, entrypoint.sh)
├── scripts/                # Helper & maintenance scripts
├── tests/                  # Pytest test suite
├── .env.example            # Environment configuration template
├── alembic.ini             # Alembic migration settings
├── docker-compose.yml      # Multi-container Docker deployment stack
├── pyproject.toml          # Tooling & project metadata
├── README.md               # Documentation
└── requirements.txt        # Python dependencies