from gli_scrapers.cosmetics_design.client import CosmeticsDesignClient
from gli_scrapers.cosmetics_design.config import MAPPER
from gli_scrapers.runner_base import run_scraper

POLL_INTERVAL = 60
POLL_TIMEOUT  = 18000  # 5h


async def main():
    client = CosmeticsDesignClient()
    try:
        return await run_scraper(
            name="cosmetics_design",
            client=client,
            mapper=MAPPER,
            poll_interval=POLL_INTERVAL,
            poll_timeout=POLL_TIMEOUT,
        )
    finally:
        await client.aclose()
