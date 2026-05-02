#!/bin/bash
# run-celery.sh - в корне проекта

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

MODE=${1:-"all"}  # all, worker, beat, worker-analysis, worker-embeddings, worker-fast

# Загружаем переменные из .env файла
if [ -f .env ]; then
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
fi

# Оптимальные настройки для Mac с 8-10 ядрами
# Для задач анализа (LLM) - умеренная конкурентность, т.к. задачи тяжелые
ANALYSIS_CONCURRENCY=${ANALYSIS_CONCURRENCY:-2}
# Для эмбеддингов - можно больше, задачи легче
EMBEDDINGS_CONCURRENCY=${EMBEDDINGS_CONCURRENCY:-4}
# Для быстрых I/O задач - gevent с высокой конкурентностью
FAST_CONCURRENCY=${FAST_CONCURRENCY:-50}

# Функция для запуска worker (все очереди)
start_worker() {
    echo -e "${GREEN}🚀 Starting Celery Worker (all queues)${NC}"
    echo -e "${BLUE}   Pool: prefork${NC}"
    echo -e "${BLUE}   Concurrency: 4${NC}"
    echo -e "${BLUE}   Queues: embeddings, analysis, default, high_priority${NC}"
    echo ""

    exec celery -A src.tasks.celery_app worker \
        --loglevel=INFO \
        --pool=prefork \
        --concurrency=4 \
        --queues=embeddings,analysis,default,high_priority \
        --prefetch-multiplier=1 \
        --max-tasks-per-child=100 \
        --without-gossip \
        --without-mingle \
        --without-heartbeat
}

# Функция для запуска worker только для analysis (LLM задачи)
start_worker_analysis() {
    echo -e "${GREEN}🚀 Starting Celery Worker (ANALYSIS queue - LLM tasks)${NC}"
    echo -e "${BLUE}   Pool: prefork${NC}"
    echo -e "${BLUE}   Concurrency: ${ANALYSIS_CONCURRENCY} (для тяжелых LLM задач)${NC}"
    echo -e "${BLUE}   Queue: analysis${NC}"
    echo ""

    exec celery -A src.tasks.celery_app worker \
        --loglevel=INFO \
        --pool=prefork \
        --concurrency="$ANALYSIS_CONCURRENCY" \
        --queues=analysis \
        --prefetch-multiplier=1 \
        --max-tasks-per-child=10 \
        --without-gossip \
        --without-mingle \
        --without-heartbeat
}

# Функция для запуска worker только для embeddings
start_worker_embeddings() {
    echo -e "${GREEN}🚀 Starting Celery Worker (EMBEDDINGS queue)${NC}"
    echo -e "${BLUE}   Pool: prefork${NC}"
    echo -e "${BLUE}   Concurrency: ${EMBEDDINGS_CONCURRENCY}${NC}"
    echo -e "${BLUE}   Queue: embeddings${NC}"
    echo ""

    exec celery -A src.tasks.celery_app worker \
        --loglevel=INFO \
        --pool=prefork \
        --concurrency="$EMBEDDINGS_CONCURRENCY" \
        --queues=embeddings \
        --prefetch-multiplier=1 \
        --max-tasks-per-child=50 \
        --without-gossip \
        --without-mingle \
        --without-heartbeat
}

# Функция для запуска worker для быстрых I/O задач (gevent)
start_worker_fast() {
    echo -e "${GREEN}🚀 Starting Celery Worker (FAST I/O tasks - gevent)${NC}"
    echo -e "${BLUE}   Pool: gevent${NC}"
    echo -e "${BLUE}   Concurrency: ${FAST_CONCURRENCY} (для высокой I/O нагрузки)${NC}"
    echo -e "${BLUE}   Queues: default, high_priority${NC}"
    echo ""

    exec celery -A src.tasks.celery_app worker \
        --loglevel=INFO \
        --pool=prefork \
        --concurrency="$FAST_CONCURRENCY" \
        --queues=default,high_priority \
        --prefetch-multiplier=1
}

# Функция для запуска всех воркеров (максимальная производительность)
start_all() {
    echo -e "${GREEN}🚀 Starting ALL Celery Workers${NC}"
    echo -e "${YELLOW}Это запустит 3 воркера в фоне${NC}"
    echo ""

    # Worker для анализа (LLM)
    echo -e "${BLUE}Starting analysis worker...${NC}"
    celery -A src.tasks.celery_app worker \
        --loglevel=INFO \
        --pool=prefork \
        --concurrency="$ANALYSIS_CONCURRENCY" \
        --queues=analysis \
        --prefetch-multiplier=1 \
        --max-tasks-per-child=10 \
        --without-gossip \
        --without-mingle \
        --without-heartbeat \
        --logfile=logs/analysis_worker.log &

    # Worker для эмбеддингов
    echo -e "${BLUE}Starting embeddings worker...${NC}"
    celery -A src.tasks.celery_app worker \
        --loglevel=INFO \
        --pool=prefork \
        --concurrency="$EMBEDDINGS_CONCURRENCY" \
        --queues=embeddings \
        --prefetch-multiplier=1 \
        --max-tasks-per-child=50 \
        --without-gossip \
        --without-mingle \
        --without-heartbeat \
        --logfile=logs/embeddings_worker.log &

    # Worker для быстрых задач
    echo -e "${BLUE}Starting fast I/O worker...${NC}"
    celery -A src.tasks.celery_app worker \
        --loglevel=INFO \
        --pool=gevent \
        --concurrency="$FAST_CONCURRENCY" \
        --queues=default,high_priority \
        --prefetch-multiplier=1 \
        --logfile=logs/fast_worker.log &

    echo ""
    echo -e "${GREEN}✅ All workers started!${NC}"
    echo -e "${BLUE}   Analysis worker:    logs/analysis_worker.log${NC}"
    echo -e "${BLUE}   Embeddings worker:  logs/embeddings_worker.log${NC}"
    echo -e "${BLUE}   Fast I/O worker:    logs/fast_worker.log${NC}"
    echo ""
    echo -e "${YELLOW}Press Ctrl+C to stop all workers${NC}"

    # Создаем директорию для логов
    mkdir -p logs

    # Ждем все процессы
    wait
}

# Функция для запуска beat
start_beat() {
    echo -e "${GREEN}⏰ Starting Celery Beat${NC}"
    echo -e "${BLUE}   Scheduler: redbeat.RedBeatScheduler${NC}"
    echo ""

    exec celery -A src.tasks.celery_app beat \
        --loglevel=INFO \
        --scheduler redbeat.RedBeatScheduler
}

# Функция для проверки статуса
status() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}📊 Celery Services Status${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # Проверяем workers
    if pgrep -f "celery.*worker.*analysis" > /dev/null; then
        WORKER_PID=$(pgrep -f "celery.*worker.*analysis" | head -1)
        echo -e "${GREEN}✅ Analysis Worker: Running (PID: ${WORKER_PID})${NC}"
    elif pgrep -f "celery.*worker" > /dev/null; then
        WORKER_PID=$(pgrep -f "celery.*worker" | head -1)
        echo -e "${GREEN}✅ Worker (all queues): Running (PID: ${WORKER_PID})${NC}"
    else
        echo -e "${RED}❌ Worker: Not running${NC}"
    fi

    # Проверяем beat
    if pgrep -f "celery.*beat" > /dev/null; then
        BEAT_PID=$(pgrep -f "celery.*beat" | head -1)
        echo -e "${GREEN}✅ Beat: Running (PID: ${BEAT_PID})${NC}"
    else
        echo -e "${RED}❌ Beat: Not running${NC}"
    fi

    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Функция для остановки
stop() {
    echo -e "${YELLOW}🛑 Stopping Celery services...${NC}"

    pkill -f "celery.*worker" && echo -e "${GREEN}✅ All workers stopped${NC}" || echo -e "${YELLOW}⚠️ No workers running${NC}"
    pkill -f "celery.*beat" && echo -e "${GREEN}✅ Beat stopped${NC}" || echo -e "${YELLOW}⚠️ Beat not running${NC}"
}

# Основная логика
case $MODE in
    worker)
        start_worker
        ;;
    worker-analysis)
        start_worker_analysis
        ;;
    worker-embeddings)
        start_worker_embeddings
        ;;
    worker-fast)
        start_worker_fast
        ;;
    all)
        start_all
        ;;
    beat)
        start_beat
        ;;
    status)
        status
        ;;
    stop)
        stop
        ;;
    help|--help|-h)
        help
        ;;
    *)
        echo -e "${RED}❌ Unknown mode: $MODE${NC}"
        echo ""
        help
        exit 1
        ;;
esac