import logging
from typing import List, Dict, Any
from sqlalchemy import text
from src.database.session import AsyncSessionLocal
from src.config import settings
from langchain_ollama import OllamaEmbeddings

logger = logging.getLogger(__name__)

# Initialize embeddings
embeddings = OllamaEmbeddings(
    model=settings.embedding_model,
    base_url=settings.ollama_base_url,
)


async def store_message_embedding(message_id: int, content: str) -> None:
    """Generate and store embedding for a message"""
    try:
        embedding = await embeddings.aembed_query(content)

        async with AsyncSessionLocal() as db:
            query = text("""
                         INSERT INTO message_embeddings (message_id, embedding)
                         VALUES (:message_id, :embedding::vector) ON CONFLICT (message_id) DO
                         UPDATE
                             SET embedding = EXCLUDED.embedding
                         """)
            await db.execute(query, {"message_id": message_id, "embedding": embedding})
            await db.commit()

        logger.debug(f"Stored embedding for message {message_id}")
    except Exception as e:
        logger.error(f"Failed to store embedding: {e}")


async def semantic_search(query: str, chat_id: str = None, limit: int = 5) -> List[Dict[str, Any]]:
    """Perform semantic search across messages"""
    try:
        query_embedding = await embeddings.aembed_query(query)

        async with AsyncSessionLocal() as db:
            sql = """
                  SELECT m.content, \
                         m.sender_name, \
                         m.timestamp, \
                         m.chat_title,
                         (me.embedding < - > :embedding::vector) as distance
                  FROM message_embeddings me
                           JOIN messages m ON me.message_id = m.id
                  WHERE (:chat_id IS NULL OR m.chat_id = :chat_id)
                  ORDER BY me.embedding < - > :embedding::vector
                LIMIT :limit \
                  """
            result = await db.execute(
                text(sql),
                {"embedding": query_embedding, "chat_id": chat_id, "limit": limit}
            )
            rows = result.fetchall()

            return [
                {
                    "content": row[0],
                    "sender": row[1],
                    "timestamp": row[2].isoformat() if row[2] else None,
                    "chat": row[3],
                    "similarity": 1 - row[4]  # Convert distance to similarity
                }
                for row in rows
            ]
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        return []