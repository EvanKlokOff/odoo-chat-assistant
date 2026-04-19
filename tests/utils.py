import asyncio
from src.analyzers import nodes
from src.llm.providers import BaseEmbeddingProvider

async def get_embeddings(texts: list[str], embeding_model: BaseEmbeddingProvider):
    tasks = (embeding_model.embed(text) for text in texts)
    vectors = await asyncio.gather(*tasks)
    return vectors

async def mock_retrieve_chat_messages(state, sample_messages):
    state["chat_messages"] = sample_messages
    return state


def sync_analyze_query_type(state):
    import asyncio
    return asyncio.run(nodes.analyze_query_type(state))

def sync_retrieve_chat_messages(state):
    import asyncio
    return asyncio.run(nodes.retrieve_chat_messages(state))

def sync_generate_review(state):
    import asyncio
    return asyncio.run(nodes.generate_review(state))

def sync_check_compliance(state):
    import asyncio
    return asyncio.run(nodes.check_compliance(state))

def sync_extract_deviations(state):
    import asyncio
    return asyncio.run(nodes.extract_deviations(state))