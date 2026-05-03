"""Scheduler de scrapers GLI.

Corre automáticamente a las 04:00 America/Mexico_City todos los días.

Uso:
    python scheduler.py          # modo daemon (espera y ejecuta a las 4 AM)
    python scheduler.py --now    # ejecuta inmediatamente y sale (trigger manual)
    python scheduler.py --now alibaba indiamart   # scrapers específicos + sale
"""

import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

WORKDIR = Path(__file__).parent


def run_scrapers(targets: list[str] | None = None) -> None:
    args = targets or ["all"]
    log.info("=== Iniciando scrapers: %s ===", args)
    result = subprocess.run(
        [sys.executable, "run.py"] + args,
        cwd=WORKDIR,
    )
    if result.returncode != 0:
        log.error("run.py salió con código %d", result.returncode)
    else:
        log.info("=== Ejecución completada ===")


def main() -> None:
    argv = sys.argv[1:]

    if "--now" in argv:
        targets = [a for a in argv if a != "--now"] or None
        run_scrapers(targets)
        return

    from apscheduler.schedulers.blocking import BlockingScheduler

    scheduler = BlockingScheduler(timezone="America/Mexico_City")
    scheduler.add_job(run_scrapers, "cron", hour=18, minute=25)

    log.info("Scheduler activo — ejecutará a las 18:25 America/Mexico_City")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler detenido.")


if __name__ == "__main__":
    main()
