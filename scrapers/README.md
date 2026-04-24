# Scrapers — Estructura por módulo

Cada scraper vive en `scrapers/<nombre>/` con la siguiente estructura:

```
scrapers/<nombre>/
  __init__.py
  models.py              ← (opcional) pydantic model canónico derivado de spec §2
  transform.py           ← (opcional) reglas de negocio de spec §4

  vendor/                ← andamiaje generado por DB AI — READ-ONLY, se lee 1 vez
    sc_browser/          ← implementación con render JS generada por DB AI
    sc_code/             ← implementación sin browser generada por DB AI

  sc_browser/            ← nuestra versión iterable (render JS)
    __init__.py
  sc_code/               ← nuestra versión iterable (sin browser)
    __init__.py
```

## Reglas

1. **Schema inmutable**. El §2 de cada spec define el shape de salida. Toda
   implementación (`vendor/sc_browser`, `vendor/sc_code`, `sc_browser`, `sc_code`)
   debe producir **exactamente ese shape**. Un cambio de schema requiere nueva
   spec, no nueva versión.
2. **`vendor/` es read-only**. DB AI lo genera a partir de la spec; lo leemos
   una vez para entender y luego iteramos en `sc_browser/` y `sc_code/`.
3. **`models.py` y `transform.py` son compartidos** entre `sc_browser/` y
   `sc_code/`. El contrato es la spec — el código es reutilizable.
4. **No tocar `alibaba-old/`**: snapshot histórico de la implementación
   pre-estructura, mantenido para referencia.

## Flujo

1. Redactar / actualizar spec en `docs/specs/brightd-scrapers/<nombre>/module-spec.md`.
2. Entregar spec a DB AI → recibir código → poner en `scrapers/<nombre>/vendor/`.
3. Leer `vendor/` una vez para entender las decisiones de DB AI.
4. Escribir nuestras versiones en `scrapers/<nombre>/sc_browser/` y `sc_code/`,
   importando el schema desde `models.py` y las reglas desde `transform.py`.

## Estado actual

| Scraper | Spec | models.py | transform.py | vendor/ | sc_browser/ | sc_code/ |
|---------|------|-----------|--------------|---------|-------------|----------|
| alibaba | v0.2 Draft | ✅ (heredado) | ✅ (heredado) | 🔲 pendiente DB AI | 🔲 pendiente | 🔲 pendiente |
| made-in-china | v0.1 Draft | 🔲 pendiente | 🔲 pendiente | 🔲 pendiente DB AI | 🔲 pendiente | 🔲 pendiente |
| indiamart | v0.1 Draft | 🔲 pendiente | 🔲 pendiente | 🔲 pendiente DB AI | 🔲 pendiente | 🔲 pendiente |
| cosme | v0.1 Draft | 🔲 pendiente | 🔲 pendiente | 🔲 pendiente DB AI | 🔲 pendiente | 🔲 pendiente |
| olive-young | v0.1 Draft | 🔲 pendiente | 🔲 pendiente | 🔲 pendiente DB AI | 🔲 pendiente | 🔲 pendiente |
| cosmetics-design | v0.1 Draft | 🔲 pendiente | 🔲 pendiente | 🔲 pendiente DB AI | 🔲 pendiente | 🔲 pendiente |
