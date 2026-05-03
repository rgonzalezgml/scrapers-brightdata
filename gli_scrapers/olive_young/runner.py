import asyncio
import logging

from gli_scrapers.olive_young.client import OliveYoungClient
from gli_scrapers.olive_young.config import MAPPER
from gli_scrapers.runner_base import load_job, parse_job_id_arg, run_scraper

POLL_INTERVAL = 30
POLL_TIMEOUT  = 18000  # 5 horas


async def main():
    client = OliveYoungClient()
    try:
        job_id = parse_job_id_arg()
        if job_id:
            return await load_job(name="olive_young", client=client, mapper=MAPPER, job_id=job_id)
        return await run_scraper(
            name="olive_young", client=client, mapper=MAPPER,
            poll_interval=POLL_INTERVAL, poll_timeout=POLL_TIMEOUT,
        )
    finally:
        await client.aclose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s %(message)s", datefmt="%H:%M:%S")
    asyncio.run(main())
