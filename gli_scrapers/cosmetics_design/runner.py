import asyncio
import logging

from gli_scrapers.cosmetics_design.client import CosmeticsDesignClient
from gli_scrapers.cosmetics_design.config import MAPPER
from gli_scrapers.runner_base import load_job, parse_job_id_arg, run_scraper

POLL_INTERVAL = 60
POLL_TIMEOUT  = 18000  # 5 horas


async def main():
    client = CosmeticsDesignClient()
    try:
        job_id = parse_job_id_arg()
        if job_id:
            return await load_job(name="cosmetics_design", client=client, mapper=MAPPER, job_id=job_id)
        return await run_scraper(
            name="cosmetics_design", client=client, mapper=MAPPER,
            poll_interval=POLL_INTERVAL, poll_timeout=POLL_TIMEOUT,
        )
    finally:
        await client.aclose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s %(message)s", datefmt="%H:%M:%S")
    asyncio.run(main())
