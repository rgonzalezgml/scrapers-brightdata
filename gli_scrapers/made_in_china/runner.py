from gli_scrapers.made_in_china.client import MadeInChinaClient
from gli_scrapers.made_in_china.config import MAPPER
from gli_scrapers.runner_base import run_scraper

POLL_INTERVAL = 45
POLL_TIMEOUT  = 5400  # 90 min


async def main():
    client = MadeInChinaClient()
    try:
        return await run_scraper(
            name="made_in_china",
            client=client,
            mapper=MAPPER,
            poll_interval=POLL_INTERVAL,
            poll_timeout=POLL_TIMEOUT,
        )
    finally:
        await client.aclose()
