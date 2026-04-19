import numpy as np

def cosine_similarity_np(a: list[float], b: list[float]) -> float:
    """Вычисление косинусного сходства с помощью NumPy"""
    a_np = np.array(a)
    b_np = np.array(b)

    # Нормализация векторов
    norm_a = np.linalg.norm(a_np)
    norm_b = np.linalg.norm(b_np)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    # Косинусное сходство
    return np.dot(a_np, b_np) / (norm_a * norm_b)

