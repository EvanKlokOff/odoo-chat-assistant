from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

Base = declarative_base()


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