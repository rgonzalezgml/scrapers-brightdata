from gli_scrapers.cosme_ranking_products.client import CosmeRankingClient
from gli_scrapers.cosme_ranking_products.config import MAPPER
from gli_scrapers.runner_base import run_scraper

POLL_INTERVAL = 30   # seconds between polls
POLL_TIMEOUT  = 1800 # 30 minutes (2x the typical 15-min run)


async def main():
    client = CosmeRankingClient()
    try:
        return await run_scraper(
            name="cosme_ranking_products",
            client=client,
            mapper=MAPPER,
            poll_interval=POLL_INTERVAL,
            poll_timeout=POLL_TIMEOUT,
        )
    finally:
        await client.aclose()
