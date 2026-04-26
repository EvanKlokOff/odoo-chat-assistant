from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, ForeignKey, Index,DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from sqlalchemy import ColumnElement
from sqlalchemy.orm import relationship

Base = declarative_base()


class MessageChunk(Base):
    """Чанк сообщения с эмбеддингом"""
    __tablename__ = "message_chunks"

    id = Column(Integer, primary_key=True)
    chat_id = Column(String, nullable=False)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, default=0)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Vector(768))  # Для PostgreSQL pgvector
    timestamp = Column(DateTime, nullable=False)

    # Отношения
    message = relationship("Message", back_populates="chunks")

    @staticmethod
    def cosine_distance(embedding_vector: list[float]) -> ColumnElement:
        """
        Вычисляет косинусное расстояние между эмбеддингом чанка и заданным вектором.

        Использует оператор pgvector <=> (косинусное расстояние)

        Args:
            embedding_vector: Список float значений эмбеддинга

        Returns:
            SQL выражение для косинусного расстояния
        """
        from sqlalchemy import cast
        from pgvector.sqlalchemy import Vector as VectorType

        # Преобразуем список в тип Vector
        vector_value = cast(embedding_vector, VectorType(768))

        # Оператор <=> для косинусного расстояния
        return MessageChunk.embedding.cosine_distance(vector_value)

    @staticmethod
    def cosine_similarity(embedding_vector: list[float]) -> int:
        """
        Вычисляет косинусное сходство между эмбеддингом чанка и заданным вектором.

        Returns:
            SQL выражение для косинусного сходства (1 - расстояние)
        """
        return 1 - MessageChunk.cosine_distance(embedding_vector)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    message_id = Column(String(255), nullable=False)
    chat_id = Column(String(255), nullable=False)
    chat_title = Column(String(255))
    sender_id = Column(String(255))
    sender_name = Column(String(255))
    content = Column(Text, nullable=False)
    timestamp = Column(TIMESTAMP, nullable=False)
    platform = Column(String(50), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    reply_to_message_id = Column(String(255), nullable=True)
    chunks = relationship("MessageChunk", back_populates="message", cascade="all, delete-orphan")

class MessageEmbedding(Base):
    __tablename__ = "message_embeddings"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"))
    embedding = Column(Vector(768))
    created_at = Column(TIMESTAMP, server_default=func.now())


class AnalysisReport(Base):
    __tablename__ = "analysis_reports"

    id = Column(Integer, primary_key=True)
    chat_id = Column(String(255), nullable=False)
    report_type = Column(String(50), nullable=False)
    date_range_start = Column(TIMESTAMP)
    date_range_end = Column(TIMESTAMP)
    instruction = Column(Text)
    content = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())


class UserChat(Base):
    """Связь пользователей с чатами"""
    __tablename__ = "user_chats"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False)  # Telegram user ID
    chat_id = Column(String(255), nullable=False)  # Telegram chat ID
    chat_title = Column(String(255))
    selected = Column(Integer, default=0)  # 0 - не выбран, 1 - выбран
    last_used = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    created_at = Column(TIMESTAMP, server_default=func.now())

    # Составной уникальный индекс
    __table_args__ = (
        Index('idx_user_chat_unique', 'user_id', 'chat_id', unique=True),
        Index('idx_user_selected', 'user_id', 'selected'),
    )


class UserSettings(Base):
    """Настройки пользователей"""
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False, unique=True)
    selected_chat_id = Column(String(255), nullable=True)  # Текущий выбранный чат
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    created_at = Column(TIMESTAMP, server_default=func.now())