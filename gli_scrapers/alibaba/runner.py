from gli_scrapers.alibaba.client import AlibabaClient
from gli_scrapers.alibaba.config import MAPPER
from gli_scrapers.runner_base import run_scraper

POLL_INTERVAL = 30
POLL_TIMEOUT  = 18000  # 5 horas


async def main():
    client = AlibabaClient()
    try:
        return await run_scraper(
            name="alibaba",
            client=client,
            mapper=MAPPER,
            poll_interval=POLL_INTERVAL,
            poll_timeout=POLL_TIMEOUT,
        )
    finally:
        await client.aclose()
