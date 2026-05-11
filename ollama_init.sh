#!/bin/bash
# ollama_init.sh - с поддержкой curl

set -e

echo "🚀 Starting Ollama with phi4-mini and nomic-embed-text..."
echo "==========================================================="

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Функция для проверки готовности Ollama
wait_for_ollama() {
    log "Waiting for Ollama server to be ready..."
    MAX_RETRIES=10
    RETRY=0

    while [ $RETRY -lt $MAX_RETRIES ]; do
        if curl -s -f http://localhost:11434/api/tags > /dev/null 2>&1; then
            log "✅ Ollama server is ready!"
            return 0
        fi
        RETRY=$((RETRY + 1))
        log "Waiting... ($RETRY/$MAX_RETRIES)"
        sleep 2
    done

    log "❌ Ollama server failed to start after $MAX_RETRIES attempts"
    return 1
}

# Запуск Ollama в фоне
log "Starting Ollama server..."
ollama serve &
OLLAMA_PID=$!

# Ждем готовности сервера
wait_for_ollama || exit 1

# Проверяем, нужно ли загружать модели
if [ ! -f /root/.ollama/initialized ]; then
    log "📥 First start - pulling models (this may take several minutes)..."
    log "================================================================"

    # Загрузка phi4-mini
    log "📥 Pulling phi4-mini:latest (about 6GB)..."
    if ollama pull phi4-mini:latest; then
        log "✅ phi4-mini:latest pulled successfully!"
    else
        log "❌ Failed to pull phi4-mini:latest"
        exit 1
    fi

    # Загрузка nomic-embed-text
    log "📥 Pulling nomic-embed-text (about 274MB)..."
    if ollama pull nomic-embed-text; then
        log "✅ nomic-embed-text pulled successfully!"
    else
        log "❌ Failed to pull nomic-embed-text"
        exit 1
    fi

    # Создаем маркер инициализации
    touch /root/.ollama/initialized
    log "================================================================"
    log "✅ Models loaded successfully!"
    log "   - phi4-mini:latest (LLM)"
    log "   - nomic-embed-text (Embeddings)"

    # Выводим список моделей
    log "📋 Available models:"
    ollama list
else
    log "✅ Models already loaded, skipping download"
    log "📋 Current models:"
    ollama list
fi

# Финальное тестирование
log "🧪 Testing Ollama API with curl..."
if curl -s -f http://localhost:11434/api/tags > /dev/null; then
    log "✅ Ollama API is responding correctly!"
else
    log "⚠️  Ollama API test failed, but continuing..."
fi

log "==========================================================="
log "🚀 Ollama is fully ready to accept requests!"

# Держим процесс активным и перезапускаем если упал
while true; do
    if ! kill -0 $OLLAMA_PID 2>/dev/null; then
        log "⚠️  Ollama process died, restarting..."
        ollama serve &
        OLLAMA_PID=$!
        wait_for_ollama
    fi
    sleep 10
done