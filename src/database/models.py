import datetime
from sqlalchemy import (Column, Integer, String, Text, TIMESTAMP,
                        ForeignKey, Index, DateTime, UniqueConstraint,
                        ColumnElement, CheckConstraint, BigInteger, Enum as SAEnum, Boolean)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import relationship
from src.database import enums

Base = declarative_base()


class AnalysisTask(Base):
    __tablename__ = "analysis_tasks"

    id = Column(Integer, primary_key=True)
    task_id = Column(String(100), unique=True, index=True, nullable=False)
    user_id = Column(BigInteger, nullable=False, index=True)
    chat_id = Column(String(100), nullable=False, index=True)
    task_type = Column(SAEnum(
        enums.TaskType,
        values_callable=lambda enum_cls: [e.value for e in enum_cls]
    ), nullable=False)  # review, compliance

    instruction = Column(Text, nullable=True)
    date_start = Column(String(50), nullable=True)
    date_end = Column(String(50), nullable=True)

    is_notified = Column(Boolean, default=False, index=True)
    status = Column(SAEnum(
        enums.TaskStatus,
        values_callable=lambda enum_cls: [e.value for e in enum_cls]
    ), default="pending", index=True)  # pending, running, completed, failed
    progress = Column(Integer, default=0)
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    message = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.now(datetime.UTC))
    completed_at = Column(DateTime, nullable=True)

    # Индексы для быстрого поиска
    __table_args__ = (
        Index('ix_tasks_user_status', 'user_id', 'status'),
        Index('ix_tasks_created', 'created_at'),
    )


class MessageChunk(Base):
    """Чанк сообщения с эмбеддингом"""
    __tablename__ = "message_chunks"
    __table_args__ = (
        # Основные индексы для частых запросов
        Index('idx_chunks_chat_id_timestamp', 'chat_id', 'timestamp'),
        Index('idx_chunks_message_id', 'message_id'),
        Index('idx_chunks_chat_id_message_id', 'chat_id', 'message_id'),
        Index('idx_chunks_timestamp', 'timestamp'),

        # Векторные индексы для pgvector
        # IVFFlat индекс (хорош для больших таблиц)
        Index('idx_chunks_embedding_ivfflat', 'embedding',
              postgresql_using='ivfflat'),

        # HNSW индекс (быстрее, но требует больше памяти) - раскомментировать при необходимости
        # Index('idx_chunks_embedding_hnsw', 'embedding',
        #       postgresql_using='hnsw',
        #       postgresql_with_ops={'embedding': 'vector_cosine_ops'}),

        # Покрывающий индекс для ускорения запросов
        Index('idx_chunks_covering', 'chat_id', 'timestamp', 'message_id'),

        CheckConstraint('chunk_index >= 0', name='check_chunk_index_positive'),
        CheckConstraint('length(chunk_text) >= 10', name='check_chunk_min_length'),
    )
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
    __table_args__ = (
        # Композитные индексы для частых фильтраций
        Index('idx_messages_chat_id_timestamp', 'chat_id', 'timestamp'),
        Index('idx_messages_chat_id_sender_id', 'chat_id', 'sender_id'),
        Index('idx_messages_timestamp', 'timestamp'),
        Index('idx_messages_sender_id', 'sender_id'),

        # Индекс для поиска по содержимому (триграмма)
        Index('idx_messages_content_gin', 'content',
              postgresql_using='gin',
              postgresql_ops={'content': 'gin_trgm_ops'}),

        # Уникальное ограничение для предотвращения дублей
        UniqueConstraint('chat_id', 'message_id', name='uq_message_chat_message'),

        # Check constraint для валидации
        CheckConstraint('length(content) > 0', name='check_content_not_empty'),
    )
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
    embeddings = relationship("MessageEmbedding", back_populates="message",
                              cascade="all, delete-orphan", lazy='selectin')


class MessageEmbedding(Base):
    __tablename__ = "message_embeddings"
    __table_args__ = (
        Index('idx_msg_embeddings_message_id', 'message_id'),
        Index('idx_msg_embeddings_embedding_ivfflat', 'embedding',
              postgresql_using='ivfflat',
              postgresql_ops={'embedding': 'vector_cosine_ops'}),
        Index('idx_msg_embeddings_created_at', 'created_at'),
    )
    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"))
    embedding = Column(Vector(768))
    created_at = Column(TIMESTAMP, server_default=func.now())

    message = relationship("Message", back_populates="embeddings", lazy='joined')


class AnalysisReport(Base):
    __tablename__ = "analysis_reports"

    __table_args__ = (
        Index('idx_reports_chat_id_created_at', 'chat_id', 'created_at'),
        Index('idx_reports_report_type_chat_id', 'report_type', 'chat_id'),
        Index('idx_reports_created_at', 'created_at'),
        Index('idx_reports_date_range', 'chat_id', 'date_range_start', 'date_range_end'),
        Index('idx_reports_chat_type_created', 'chat_id', 'report_type', 'created_at'),
        CheckConstraint("report_type IN ('review', 'compliance')", name='check_report_type'),
    )

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
    __table_args__ = (
        # Уникальное ограничение
        UniqueConstraint('user_id', 'chat_id', name='uq_user_chat_unique'),

        # Индексы для частых запросов
        Index('idx_user_chats_user_id_selected', 'user_id', 'selected'),
        Index('idx_user_chats_user_id_last_used', 'user_id', 'last_used'),
        Index('idx_user_chats_chat_id', 'chat_id'),
        Index('idx_user_chats_selected_idx', 'selected'),

        # Композитный индекс для поиска по пользователю и дате
        Index('idx_user_chats_user_lastused', 'user_id', 'last_used'),

        # Check constraints
        CheckConstraint('selected IN (0, 1)', name='check_selected_boolean'),
    )
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False)  # Telegram user ID
    chat_id = Column(String(255), nullable=False)  # Telegram chat ID
    chat_title = Column(String(255))
    selected = Column(Integer, default=0)  # 0 - не выбран, 1 - выбран
    last_used = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    created_at = Column(TIMESTAMP, server_default=func.now())


class UserSettings(Base):
    """Настройки пользователей"""
    __tablename__ = "user_settings"
    __table_args__ = (
        Index('idx_user_settings_user_id', 'user_id'),
        Index('idx_user_settings_selected_chat', 'selected_chat_id'),
        Index('idx_user_settings_updated', 'updated_at'),
    )
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False, unique=True)
    selected_chat_id = Column(String(255), nullable=True)  # Текущий выбранный чат
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    created_at = Column(TIMESTAMP, server_default=func.now())
