#!/bin/bash
# run-celery.sh - в корне проекта

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}🚀 Starting Celery Worker for Async Embeddings Generation${NC}"

# Загружаем переменные из .env файла
if [ -f .env ]; then
    echo -e "${YELLOW}📝 Loading .env file...${NC}"
    set -a
    source .env
    set +a
fi

# Устанавливаем PYTHONPATH
export PYTHONPATH="$(pwd):${PYTHONPATH}"

# Проверяем Redis URL
if [ -z "$REDIS_URL" ] && [ -z "$CELERY_BROKER_URL" ]; then
    echo -e "${RED}❌ Neither REDIS_URL nor CELERY_BROKER_URL is set in .env${NC}"
    exit 1
fi

# Используем REDIS_URL или создаем из CELERY_BROKER_URL
if [ -n "$CELERY_BROKER_URL" ]; then
    export REDIS_URL="$CELERY_BROKER_URL"
    echo -e "${GREEN}✅ Using CELERY_BROKER_URL: ${REDIS_URL}${NC}"
else
    echo -e "${GREEN}✅ Using REDIS_URL: ${REDIS_URL}${NC}"
fi

# Проверяем подключение к Redis (опционально, но полезно)
echo -e "${YELLOW}📡 Checking Redis connection...${NC}"

# Извлекаем хост и порт из REDIS_URL
REDIS_HOST=$(echo "$REDIS_URL" | sed -n 's/redis:\/\/[^@]*@\([^:]*\):.*/\1/p')
if [ -z "$REDIS_HOST" ]; then
    REDIS_HOST=$(echo "$REDIS_URL" | sed -n 's/redis:\/\/\([^:]*\):.*/\1/p')
fi
REDIS_PORT=$(echo "$REDIS_URL" | sed -n 's/redis:\/\/[^:]*:\([0-9]*\)\/.*/\1/p')
[ -z "$REDIS_PORT" ] && REDIS_PORT=6379

echo -e "${BLUE}   Redis host: ${REDIS_HOST}:${REDIS_PORT}${NC}"

# Проверяем с помощью redis-cli если доступен
if command -v redis-cli &> /dev/null; then
    if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping 2>/dev/null | grep -q "PONG"; then
        echo -e "${GREEN}✅ Redis is reachable${NC}"
    else
        echo -e "${YELLOW}⚠️  Cannot ping Redis, but continuing...${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  redis-cli not found, skipping connection test${NC}"
fi

# Выбор пула выполнения
echo ""
echo -e "${YELLOW}⚙️  Worker Configuration:${NC}"
echo -e "${BLUE}   Pool: threads (для asyncio поддержки)${NC}"
echo -e "${BLUE}   Concurrency: 4 (количество параллельных задач)${NC}"
echo -e "${BLUE}   Queues: embeddings, default, high_priority${NC}"
echo ""

# Выбор стратегии выполнения
POOL_TYPE=${CELERY_POOL_TYPE:-"threads"}
CONCURRENCY=${CELERY_CONCURRENCY:-4}

echo -e "${GREEN}🔧 Starting Celery worker with ${POOL_TYPE} pool...${NC}"

# Запуск Celery с правильным пулом для asyncio
exec celery -A src.tasks.celery_app worker \
    --loglevel=INFO \
    --pool="$POOL_TYPE" \
    --concurrency="$CONCURRENCY" \
    --queues=embeddings,default,high_priority \
    --prefetch-multiplier=1 \
    --max-tasks-per-child=100 \
    --without-gossip \
    --without-mingle \
    --without-heartbeat