```markdown
# Инструкция по запуску Telegram бота с Celery

## 📋 Требования

- Docker и Docker Compose
- Python 3.9+
- Git
- Ollama (установленный локально или на сервере)

---

## 🚀 Пошаговая инструкция

### 1. Клонирование репозитория

```bash
git clone <your-repository-url>
cd <project-directory>
```

### 2. Настройка переменных окружения

Создайте файл `.env` в корне проекта:

```bash
nano .env
```

Скопируйте туда следующий конфиг, заменив значения на свои(также это можно сделать из .env.example):

```env
# Database
DB_PASSWORD=your_secure_db_password
DATABASE_URL=postgresql://analyzer:your_secure_db_password@postgres:5432/chat_analyzer

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
CHAT_PER_PAGE=5

# Ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_LLM_MODEL=qwen2.5:7b
OLLAMA_EMBEDDING_MODEL=nomic-embed-text

# LLM Provider Settings
LLM_PROVIDER=ollama
EMBEDDING_PROVIDER=nomic
LLM_TEMPERATURE=0.1

# Application Settings
LOG_LEVEL=INFO
MONITOR_INTERVAL=300
LLM_CONTEXT_SIZE=4096
LLM_MAX_TOKENS=2048

# Celery
CELERY_BROKER_URL=redis://:secure_redis_password@localhost:6379/0
CELERY_RESULT_BACKEND=redis://:secure_redis_password@localhost:6379/0
CELERY_POOL_TYPE=threads
CELERY_CONCURRENCY=10
TASK_MONITOR_INTERVAL=3.0

# Database Redis
REDIS_PASSWORD=secure_redis_password
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_URL=redis://:secure_redis_password@localhost:6379/0
REDIS_MAXMEMORY=256mb
REDIS_MAXMEMORY_POLICY=allkeys-lru
REDIS_KEY_EXPIRATION=86400
```

### 3. Запуск баз данных (PostgreSQL и Redis)

```bash
# Запуск контейнеров для бота
docker-compose -f docker-compose.bot.yaml up -d

# Проверка статуса контейнеров
docker-compose -f docker-compose.bot.yaml ps

# Просмотр логов (при необходимости)
docker-compose -f docker-compose.bot.yaml logs -f
```

**Ожидаемый результат:**
- Контейнер `chat_analyzer_db` запущен и здоров
- Контейнер `chat-analyzer-redis_db` запущен и здоров

### 4. Установка зависимостей Python

```bash
# Создание виртуального окружения
python3 -m venv venv

# Активация виртуального окружения
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установка зависимостей
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Проверка подключения к базам данных

```bash
# Проверка PostgreSQL
docker exec -it chat_analyzer_db pg_isready -U analyzer -d chat_analyzer

# Проверка Redis
docker exec -it chat-analyzer-redis_db redis-cli -a secure_redis_password ping
# Должен вернуть: PONG
```

### 6. Запуск Celery задач

Откройте **первый терминал** — запуск воркера для эмбеддингов:

```bash
source venv/bin/activate
chmod +x run-celery.sh
./run-celery.sh worker-embeddings
```

Откройте **второй терминал** — запуск воркера для анализа (LLM):

```bash
source venv/bin/activate
./run-celery.sh worker-analysis
```

Откройте **третий терминал** — запуск Celery Beat (планировщик):

```bash
source venv/bin/activate
./run-celery.sh beat
```

**Альтернативный вариант:** все воркеры одной командой в фоне:

```bash
./run-celery.sh all
```

### 7. Запуск Telegram бота

Откройте **четвертый терминал**:

```bash
source venv/bin/activate
python -m src.bot
```

или если бот находится в другом месте:

```bash
python bot.py
```

### 8. Проверка статуса всех сервисов

```bash
# Статус Celery
./run-celery.sh status

# Статус контейнеров Docker
docker-compose -f docker-compose.bot.yaml ps

# Просмотр логов бота
tail -f logs/bot.log  # если логи настроены
```

---

## 🛠️ Полезные команды

### Остановка всех сервисов

```bash
# Остановка Celery воркеров
./run-celery.sh stop

# Остановка контейнеров Docker
docker-compose -f docker-compose.bot.yaml down

# Деактивация виртуального окружения
deactivate
```

### Перезапуск с чистыми базами данных

```bash
# Остановка и удаление томов (ВНИМАНИЕ: удалит все данные!)
docker-compose -f docker-compose.bot.yaml down -v

# Запуск заново
docker-compose -f docker-compose.bot.yaml up -d
```

### Просмотр логов отдельных сервисов

```bash
# Логи PostgreSQL
docker logs chat_analyzer_db

# Логи Redis
docker logs chat-analyzer-redis_db

# Логи Celery (если запущены в фоне)
tail -f logs/analysis_worker.log
tail -f logs/embeddings_worker.log
tail -f logs/fast_worker.log
```

---

## 📁 Структура проекта (ожидаемая)

```
project/
├── .env                          # Переменные окружения
├── requirements.txt              # Зависимости Python
├── docker-compose.bot.yaml       # Docker Compose для бота
├── run-celery.sh                 # Скрипт запуска Celery
├── init.sql                      # Инициализация БД
├── redis_db.conf                 # Конфиг Redis
├── src/
│   ├── bot.py                    # Точка входа бота
│   ├── tasks/
│   │   └── celery_app.py         # Celery приложение
│   └── ...                       # Другие модули
└── logs/                         # Директория с логами
```

---


### 4. Права на выполнение скрипта

```bash
chmod +x run-celery.sh
```

---

## ✅ Чеклист успешного запуска

- [ ] Docker контейнеры запущены и здоровы (`docker ps`)
- [ ] Виртуальное окружение активировано (`which python`)
- [ ] Зависимости установлены (`pip list`)
- [ ] Файл `.env` настроен корректно
- [ ] Redis отвечает на PING
- [ ] PostgreSQL принимает подключения
- [ ] Celery worker-embeddings запущен
- [ ] Celery worker-analysis запущен
- [ ] Celery beat запущен
- [ ] Telegram бот запущен и отвечает
- [ ] Ollama работает (`ollama list`)

---

## 🎯 Оптимальный порядок запуска (кратко)

```bash
# 1. Базы данных
docker-compose -f docker-compose.bot.yaml up -d

# 2. Активация окружения
source venv/bin/activate

# 3. Celery воркеры (3 терминала)
./run-celery.sh worker-embeddings   # терминал 1
./run-celery.sh worker-analysis     # терминал 2
./run-celery.sh beat                # терминал 3

# 4. Бот
python -m src.bot                    # терминал 4
```

---
