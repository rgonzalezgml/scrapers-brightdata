from gli_scrapers.olive_young.client import OliveYoungClient
from gli_scrapers.olive_young.config import MAPPER
from gli_scrapers.runner_base import run_scraper

POLL_INTERVAL = 30
POLL_TIMEOUT  = 2700  # 45 min


async def main():
    client = OliveYoungClient()
    try:
        return await run_scraper(
            name="olive_young",
            client=client,
            mapper=MAPPER,
            poll_interval=POLL_INTERVAL,
            poll_timeout=POLL_TIMEOUT,
        )
    finally:
        await client.aclose()
