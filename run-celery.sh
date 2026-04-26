#!/bin/bash
# run-celery.sh - в корне проекта /Users/user/PycharmProjects/odoo-chat-assistant/

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting Celery Worker for Embeddings Generation${NC}"

# Загружаем переменные из .env файла
if [ -f .env ]; then
    echo -e "${YELLOW}📝 Loading .env file...${NC}"
    set -a
    source .env
    set +a
fi

# Устанавливаем PYTHONPATH
export PYTHONPATH="$(pwd):${PYTHONPATH}"
echo -e "${YELLOW}📂 Working directory: $(pwd)${NC}"

# Проверяем структуру проекта
if [ ! -d "src/tasks" ]; then
    echo -e "${RED}❌ src/tasks directory not found!${NC}"
    ls -la src/
    exit 1
fi

# Проверяем наличие необходимых файлов
if [ ! -f "src/tasks/celery_app.py" ]; then
    echo -e "${RED}❌ src/tasks/celery_app.py not found!${NC}"
    exit 1
fi

if [ ! -f "src/tasks/__init__.py" ]; then
    echo -e "${YELLOW}⚠️  src/tasks/__init__.py not found! Creating...${NC}"
    touch src/tasks/__init__.py
fi

# Используем Redis URL для Celery (берем из .env или создаем)
if [ -n "$CELERY_BROKER_URL" ]; then
    # Берем CELERY_BROKER_URL и заменяем хост redis на localhost
    export REDIS_URL=$(echo "$CELERY_BROKER_URL" | sed 's/@redis:/@localhost:/')
    echo -e "${GREEN}✅ Using CELERY_BROKER_URL from .env (modified to localhost)${NC}"
elif [ -n "$REDIS_URL" ]; then
    # Берем REDIS_URL и заменяем хост на localhost
    export REDIS_URL=$(echo "$REDIS_URL" | sed 's/@redis:/@localhost:/')
    echo -e "${GREEN}✅ Using REDIS_URL from .env (modified to localhost)${NC}"
else
    # Создаем новую строку подключения
    REDIS_PASSWORD=${REDIS_PASSWORD:-"secure_redis_password"}
    export REDIS_URL="redis://:${REDIS_PASSWORD}@localhost:6379/0"
    echo -e "${GREEN}✅ Created new REDIS_URL${NC}"
fi

echo -e "${GREEN}✅ Redis URL: ${REDIS_URL}${NC}"

# Извлекаем пароль из URL для проверки
REDIS_PASSWORD=$(echo "$REDIS_URL" | sed -n 's/redis:\/\/:\([^@]*\)@.*/\1/p')

# Проверяем Redis контейнер
echo -e "${YELLOW}📡 Checking Redis connection...${NC}"

if docker ps --format '{{.Names}}' | grep -q "chat-analyzer-redis_db"; then
    echo -e "${GREEN}✅ Redis container is running${NC}"

    # Тестируем подключение с паролем
    if [ -n "$REDIS_PASSWORD" ]; then
        echo -e "${YELLOW}Testing with password: ${REDIS_PASSWORD:0:5}...${NC}"
        if docker exec chat-analyzer-redis_db redis-cli -a "$REDIS_PASSWORD" ping 2>/dev/null | grep -q "PONG"; then
            echo -e "${GREEN}✅ Redis connection successful (with password)${NC}"
        else
            echo -e "${RED}❌ Redis connection failed! Wrong password?${NC}"
            echo -e "${YELLOW}Try: docker exec chat-analyzer-redis_db redis-cli -a '${REDIS_PASSWORD}' ping${NC}"
            exit 1
        fi
    else
        if docker exec chat-analyzer-redis_db redis-cli ping 2>/dev/null | grep -q "PONG"; then
            echo -e "${GREEN}✅ Redis connection successful (no password)${NC}"
        else
            echo -e "${RED}❌ Redis connection failed${NC}"
            exit 1
        fi
    fi
else
    echo -e "${RED}❌ Redis container is not running${NC}"
    echo -e "${YELLOW}Start it: docker-compose -f docker-compose.bot.yaml up -d redis${NC}"
    exit 1
fi

# Проверяем импорт модуля
echo -e "${YELLOW}🔍 Testing module import...${NC}"
if python -c "import src.tasks.celery_app; print('✅ Import OK')" 2>&1; then
    echo -e "${GREEN}✅ Module import successful${NC}"
else
    echo -e "${RED}❌ Cannot import src.tasks.celery_app${NC}"
    exit 1
fi

# Запускаем Celery worker
echo ""
echo -e "${GREEN}🔧 Starting Celery worker...${NC}"
echo -e "${YELLOW}   Redis: ${REDIS_URL}${NC}"
echo -e "${YELLOW}   Queues: embeddings, default${NC}"
echo -e "${YELLOW}   Concurrency: 2${NC}"
echo ""

# Запуск Celery
exec celery -A src.tasks.celery_app worker \
    --loglevel=INFO \
    --concurrency=2 \
    --queues=embeddings,default \
    --prefetch-multiplier=1 \
    --max-tasks-per-child=100