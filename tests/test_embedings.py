import pytest
import asyncio
import time
import numpy as np
import tests.utils as test_utils

# Способ 1: Создаём loop один раз
_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)


def test_embed_single_text(nomic_embedding):
    """Тест получения эмбеддинга для одного текста"""
    text = "Тестовое сообщение для проверки эмбеддингов"
    vector = asyncio.run(nomic_embedding.embed(text))

    assert vector is not None
    assert isinstance(vector, list)
    assert len(vector) == 768  # Размерность nomic-embed-text
    assert all(isinstance(x, float) for x in vector[:10])
    print(f"\n✅ Single embedding test passed: dimension={len(vector)}")


def test_embed_batch(nomic_embedding):
    """Тест пакетного получения эмбеддингов"""
    texts = [
        "Первое сообщение",
        "Второе сообщение для проверки",
        "Третье сообщение с другим смыслом"
    ]

    vectors = asyncio.run(nomic_embedding.embed_batch(texts))

    assert vectors is not None
    assert len(vectors) == len(texts)
    assert all(len(v) == 768 for v in vectors)
    print(f"\n✅ Batch embedding test passed: {len(vectors)} vectors")


def test_embedding_similarity(nomic_embedding):
    """Тест схожести эмбеддингов"""

    texts = ["Куплю квартиру в центре Москвы", "Хочу приобрести недвижимость в Москве",
             "Сегодня отличная погода для прогулки"]

    vec1, vec2, vec3 = _loop.run_until_complete(test_utils.get_embeddings(texts, nomic_embedding))
    # Проверка на нулевые векторы
    assert not all(v == 0 for v in vec1), "vec1 is all zeros"
    assert not all(v == 0 for v in vec2), "vec2 is all zeros"
    assert not all(v == 0 for v in vec3), "vec3 is all zeros"

    vec1_np = np.array(vec1)
    vec2_np = np.array(vec2)
    vec3_np = np.array(vec3)

    norm1 = np.linalg.norm(vec1_np)
    norm2 = np.linalg.norm(vec2_np)
    norm3 = np.linalg.norm(vec3_np)

    assert norm1 > 0, "Norm of vec1 is zero"
    assert norm2 > 0, "Norm of vec2 is zero"
    assert norm3 > 0, "Norm of vec3 is zero"

    sim_similar = np.dot(vec1_np, vec2_np) / (np.linalg.norm(vec1_np) * np.linalg.norm(vec2_np))
    sim_different = np.dot(vec1_np, vec3_np) / (np.linalg.norm(vec1_np) * np.linalg.norm(vec3_np))

    # Похожие тексты должны иметь большее сходство
    assert sim_similar > sim_different


def test_semantic_search(nomic_embedding):
    """Тест семантического поиска"""
    documents = [
        "Квартира продается в центре города",
        "Машина в хорошем состоянии, пробег 50000 км",
        "Дом с участком в пригороде",
        "Ноутбук Apple MacBook Pro 2024"
    ]

    query = "Хочу купить жилье в городе"
    results = asyncio.run(nomic_embedding.semantic_search(query, documents))

    assert results is not None
    assert len(results) == len(documents)
    # Самый релевантный результат должен быть первым
    assert "квартир" in documents[results[0][0]].lower() or "дом" in documents[results[0][0]].lower()


def test_embedding_truncation(nomic_embedding):
    """Тест обрезания длинных текстов"""
    long_text = "A" * 10000  # Длинный текст

    vector = asyncio.run(nomic_embedding.embed(long_text))

    assert vector is not None
    assert len(vector) == 768
    print(f"\n✅ Truncation test passed for {len(long_text)} chars")


def test_embedding_speed(nomic_embedding):
    """Тест скорости получения эмбеддингов"""
    texts = [f"Тестовое сообщение {i}" for i in range(10)]

    start = time.time()
    asyncio.run(nomic_embedding.embed_batch(texts))
    elapsed = time.time() - start

    assert elapsed < 30  # 10 эмбеддингов за 30 секунд


def test_embedding_consistency(nomic_embedding):
    """Тест консистентности эмбеддингов"""
    texts = ["Одно и то же сообщение", "Одно и то же сообщение"]
    vec1, vec2= _loop.run_until_complete(test_utils.get_embeddings(texts, nomic_embedding))
    # Вектора должны быть одинаковыми (или очень близкими)
    difference = sum(abs(a - b) for a, b in zip(vec1, vec2))
    assert difference < 0.01  # Очень маленькая разница
