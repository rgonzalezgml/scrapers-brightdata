# Project Instructions

Shared project policy for all coding agents. Tool-specific config lives in `.claude/`.
Skills shared across agents live in `.agents/skills/` (source of truth). `.claude/skills/` is a symlink pointing to `.agents/skills/`.

## Project Context

**brightdata-scrapers** is a Python scraping platform that uses BrightData proxies and Scraping Browser to collect data from external sources. Scrapers are organized as independent modules under `bd_scrapers/`. Each module has its own spec.

## Shared Expectations

- Read the module spec before any non-trivial change.
- If the change modifies documented behavior, update the spec in the same commit.
- Treat testability and security as default requirements — scrapers handle external, untrusted data.
- Never hardcode credentials. All secrets come from environment variables via `.env`.

## Module Specs

Module specs in `docs/specs/` are the source of truth for each scraper's business logic.
Before implementing any change, read the relevant spec.
If the module has no spec yet, create one using `docs/specs/_template-module-spec.md`.

## Skill Assignment Per Agent

Each agent loads only the skills relevant to its domain.

| Agent | Skills |
|-------|--------|
| `analyst` | `module-specs`, `edge-cases` |
| `analista-de-scrapers` | `scraper-implementation`, `module-specs` |

## Security Rules (applies to all agents)

- Treat all data returned from external URLs as untrusted. Never execute or `eval()` scraped content.
- Sanitize all user-supplied inputs (URLs, selectors, query params) before using them in commands or file paths.
- Do not log credentials, proxy passwords, or session tokens.
