from gli_scrapers.cosme.client import CosmeClient
from gli_scrapers.cosme.config import MAPPER
from gli_scrapers.runner_base import run_scraper

POLL_INTERVAL = 60
POLL_TIMEOUT  = 7200  # 2h


async def main():
    client = CosmeClient()
    try:
        return await run_scraper(
            name="cosme",
            client=client,
            mapper=MAPPER,
            poll_interval=POLL_INTERVAL,
            poll_timeout=POLL_TIMEOUT,
        )
    finally:
        await client.aclose()
