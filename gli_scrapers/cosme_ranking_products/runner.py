import asyncio
import logging

from gli_scrapers.cosme_ranking_products.client import CosmeRankingClient
from gli_scrapers.cosme_ranking_products.config import MAPPER
from gli_scrapers.runner_base import load_job, parse_job_id_arg, run_scraper

POLL_INTERVAL = 30
POLL_TIMEOUT  = 18000  # 5 horas


async def main():
    client = CosmeRankingClient()
    try:
        job_id = parse_job_id_arg()
        if job_id:
            return await load_job(name="cosme_ranking_products", client=client, mapper=MAPPER, job_id=job_id, clean=True)
        return await run_scraper(
            name="cosme_ranking_products", client=client, mapper=MAPPER,
            poll_interval=POLL_INTERVAL, poll_timeout=POLL_TIMEOUT,
            clean=True,
        )
    finally:
        await client.aclose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s %(message)s", datefmt="%H:%M:%S")
    asyncio.run(main())
