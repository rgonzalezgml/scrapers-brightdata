.PHONY: build up down restart logs run-now run run-dev run-dev-scraper

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart gli_scrapers

logs:
	docker compose logs -f gli_scrapers

# ── PROD ──────────────────────────────────────────────────────────────────────

# Correr todos los scrapers ahora en PROD
run-now:
	docker exec gli_scrapers_prod python scheduler.py --now

# Correr un scraper específico en PROD (ej: make run scraper=alibaba)
run:
	docker exec gli_scrapers_prod python scheduler.py --now $(scraper)

# ── DEV (contenedor efímero, no toca el daemon de prod) ───────────────────────

# Correr todos los scrapers ahora en DEV
run-dev:
	docker run --rm --env-file .env.dev gli_scrapers:latest python scheduler.py --now

# Correr un scraper específico en DEV (ej: make run-dev-scraper scraper=alibaba)
run-dev-scraper:
	docker run --rm --env-file .env.dev gli_scrapers:latest python scheduler.py --now $(scraper)
