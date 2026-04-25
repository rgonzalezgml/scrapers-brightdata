from gli_scrapers.indiamart.client import IndiamartClient
from gli_scrapers.indiamart.config import MAPPER
from gli_scrapers.runner_base import run_scraper

POLL_INTERVAL = 45
POLL_TIMEOUT  = 5400  # 90 min


async def main():
    client = IndiamartClient()
    try:
        return await run_scraper(
            name="indiamart",
            client=client,
            mapper=MAPPER,
            poll_interval=POLL_INTERVAL,
            poll_timeout=POLL_TIMEOUT,
        )
    finally:
        await client.aclose()
