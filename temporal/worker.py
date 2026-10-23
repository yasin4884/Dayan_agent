from __future__ import annotations

import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from ai_model.activities import (
    ask_rag_activity,
    chunk_text_activity,
    crawl_web_activity,
    embed_passages_activity,
    embed_query_activity,
    index_document_activity,
    retrieve_activity,
    upsert_chunks_activity,
    web_search_activity,
)
from core.config import get_settings
from temporal.workflows import (
    AskRAGWorkflow,
    CrawlWebWorkflow,
    IndexDocumentWorkflow,
    RetrieveWorkflow,
    WebSearchWorkflow,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    logger.info(
        "╪º╪¬╪╡╪º┘ä ╪¿┘ç Temporal ╪»╪▒ %s / namespace=%s / queue=%s",
        settings.temporal_host,
        settings.temporal_namespace,
        settings.temporal_task_queue,
    )

    client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
    )

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[
            IndexDocumentWorkflow,
            AskRAGWorkflow,
            RetrieveWorkflow,
            CrawlWebWorkflow,
            WebSearchWorkflow,
        ],
        activities=[
            chunk_text_activity,
            embed_passages_activity,
            embed_query_activity,
            upsert_chunks_activity,
            index_document_activity,
            retrieve_activity,
            ask_rag_activity,
            crawl_web_activity,
            web_search_activity,
        ],
    )

    logger.info("Temporal worker ╪┤╪▒┘ê╪╣ ╪┤╪».")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
