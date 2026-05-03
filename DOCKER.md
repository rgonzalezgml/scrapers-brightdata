# Docker — Scrapers GLI

Corre los scrapers automaticamente a las **04:00 hora Mexico** y escribe en Snowflake PROD.

Todos los comandos son para **PowerShell en Windows**.

---

## Requisitos

- Docker Desktop instalado y corriendo
- Abrir PowerShell en la carpeta del proyecto

```powershell
cd C:\proyectos\brightdata-scrapers
```

---

## Primera vez

```powershell
# 1. Construir la imagen (tarda ~3 min)
docker compose build

# 2. Levantar el daemon en segundo plano
docker compose up -d

# 3. Verificar que esta corriendo
docker ps
```

Deberias ver `gli_scrapers_prod` con estado `Up`.

---

## Probar en DEV antes de ir a PROD

Corre un contenedor temporal que escribe en `DEV_STG.GNM_MEX`. Desaparece solo al terminar, no toca PROD.

```powershell
# Todos los scrapers -> DEV
docker run --rm --env-file .env.dev gli_scrapers:latest python scheduler.py --now

# Un scraper especifico -> DEV
docker run --rm --env-file .env.dev gli_scrapers:latest python scheduler.py --now alibaba
docker run --rm --env-file .env.dev gli_scrapers:latest python scheduler.py --now cosme_ranking
docker run --rm --env-file .env.dev gli_scrapers:latest python scheduler.py --now olive_young
```

Scrapers disponibles: `alibaba`, `indiamart`, `made_in_china`, `olive_young`, `cosmetics_design`, `cosme_ranking`

---

## Subir el daemon de PROD

Solo cuando ya probaste en DEV y todo esta bien:

```powershell
docker compose up -d
```

El daemon queda corriendo en segundo plano y ejecuta los scrapers todos los dias a las 04:00.

---

## Trigger manual en PROD

```powershell
# Todos los scrapers ahora mismo
docker exec gli_scrapers_prod python scheduler.py --now

# Un scraper especifico
docker exec gli_scrapers_prod python scheduler.py --now alibaba
docker exec gli_scrapers_prod python scheduler.py --now cosme_ranking
```

---

## Conectarse al contenedor

```powershell
docker exec -it gli_scrapers_prod bash
```

Desde adentro podes verificar variables y correr cosas manualmente:

```bash
# Confirmar que apunta a PROD
env | grep SNOWFLAKE

# Correr manualmente
python run.py all
python run.py alibaba

exit
```

---

## Ver logs

```powershell
# En vivo (Ctrl+C para salir)
docker compose logs -f gli_scrapers

# Ultimas 50 lineas
docker logs gli_scrapers_prod --tail 50

# Ultimas 2 horas
docker logs gli_scrapers_prod --since 2h
```

Un run exitoso se ve asi:

```
2026-05-03 04:00:00  INFO     === Iniciando scrapers: ['all'] ===
2026-05-03 04:08:14  INFO     [alibaba] inserted 340 rows
2026-05-03 04:11:02  INFO     [indiamart] inserted 218 rows
2026-05-03 04:14:37  INFO     === Ejecucion completada ===
```

---

## Operaciones del dia a dia

```powershell
# Bajar el daemon
docker compose down

# Reiniciar
docker compose restart gli_scrapers

# Ver estado
docker ps
```

---

## Si la PC reinicia

El contenedor se levanta solo. Para confirmar:

```powershell
docker ps
```

---

## Reconstruir la imagen

Necesario cuando cambia codigo o dependencias:

```powershell
docker compose down
docker compose build
docker compose up -d
```
