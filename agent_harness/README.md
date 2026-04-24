# agent_harness — probar el middleware como lo usaria un agente

Harness de integracion que replica el patron de David
(`agents/01-motor-bi-conversacional/backend/app/core/agent.py`): FastAPI +
`anthropic.AsyncAnthropic` + loop de tool-use + un mini ServiceRegistry que
despacha a `middlewares/cosmetics_design`.

Objetivo: validar, antes de entregar al repo de agentes, que un LLM con el
`TOOL_SCHEMA` del middleware puede disparar el scraper y leer el envelope.

No es codigo de produccion.

---

## Instalacion

```bash
cd /workspace
pip install -r requirements.txt              # deps base del proyecto
pip install -r agent_harness/requirements.txt # anthropic, fastapi, uvicorn
```

## Configuracion (.env en raiz)

```bash
# siempre
ANTHROPIC_API_KEY=sk-ant-...
AGENT_MODE=fixture            # fixture | live

# solo si AGENT_MODE=live
BRIGHTDATA_API_KEY=...
BRIGHTDATA_DATASET_ID_COSMETICS_DESIGN=...

# opcionales (solo live) — controlan el polling interno de get_result
LIVE_POLL_INTERVAL_SECONDS=30   # default 30
LIVE_POLL_TIMEOUT_SECONDS=1800  # default 1800 (30 min)
```

- `AGENT_MODE=fixture` (default): `trigger` y `get_result` estan stubbed y
  devuelven el snapshot congelado en
  `middlewares/cosmetics_design/tests/fixtures/cosmetics_design_snapshot_s_demo01.json`.
  No llama BrightData ni cuesta dinero (salvo los tokens de Anthropic).
  Perfecto para validar el cableado del agente/tool-use.
- `AGENT_MODE=live`: pega contra BrightData real. 10-60 min por corrida. En
  este modo `cosmetics_design_get_result` **polea internamente** hasta que el
  job termina (done/failed) o supera `LIVE_POLL_TIMEOUT_SECONDS`. El LLM lo
  llama una sola vez y recibe un resultado terminal — por eso `MAX_TURNS=10`
  alcanza de sobra (trigger → get_result bloqueante → texto final = 3 turnos).

## Arrancar

```bash
cd /workspace
uvicorn agent_harness.app:app --reload --port 8000
```

## Contrato HTTP (async)

El `/chat` es asincrono: `POST` dispara una task en background y devuelve
202 inmediato. El cliente polea `GET /chat/{session_id}` hasta `done`.

```
POST   /chat                    -> 202 {session_id, status: "running"}
GET    /chat/{session_id}       -> 200 {session_id, status: "running"}
                                | 200 {session_id, status: "done", reply, trace}
                                | 200 {session_id, status: "failed", error: {code, message}}
DELETE /sessions/{session_id}   -> 200 {session_id, status: "cleared"}  (cancela task)
GET    /health                  -> 200 {status, mode, model}
```

Reglas:

- Si llamas `POST /chat` con un `session_id` cuya task aun esta `running`,
  la API responde **409 Conflict** (`session busy, poll GET /chat/{id}`).
- Si la task termino (done/failed), un nuevo `POST /chat` con el mismo
  `session_id` arranca otro turno sobre el history extendido.
- El `session_id` es el mismo entre turnos; no se pierde la conversacion.

## Probar

```bash
# health
curl -s http://localhost:8000/health | jq

# arrancar conversacion
POST_OUT=$(curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Traeme las ultimas 5 noticias de cosmetica de Europa."}')
echo "$POST_OUT" | jq
SID=$(echo "$POST_OUT" | jq -r .session_id)

# polling hasta done
while true; do
  OUT=$(curl -s http://localhost:8000/chat/$SID)
  STATUS=$(echo "$OUT" | jq -r .status)
  echo "status=$STATUS"
  if [ "$STATUS" != "running" ]; then
    echo "$OUT" | jq
    break
  fi
  sleep 5
done

# continuar la misma sesion
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SID\", \"message\": \"Resume la primera noticia.\"}" | jq

# cancelar / limpiar
curl -s -X DELETE http://localhost:8000/sessions/$SID | jq
```

La respuesta final (cuando `status=="done"`) trae:

```json
{
  "session_id": "...",
  "status": "done",
  "reply": "<texto final del assistant>",
  "trace": [
    {"turn": 0, "tool": "cosmetics_design_trigger", "input": {...}, "status": null},
    {"turn": 1, "tool": "cosmetics_design_get_result", "input": {"job_id": "..."}, "status": "done"}
  ],
  "error": null
}
```

El `trace` es la bitacora de tool-use: ahi se ve si el agente elige los inputs
correctos, si respeta el `session_id`, y que cerro en `done` sin reintentos.

## Que valida (fixture mode)

- El LLM mapea correctamente el lenguaje natural a los inputs de
  `CosmeticsDesignInputs` (window_days, max_articles, region_filter, mode).
- El LLM sabe hacer el 2-step: primero `trigger`, despues `get_result`.
- El `TOOL_SCHEMA` es autodescriptivo — el LLM no necesita ayuda externa.
- El envelope devuelto por `build_envelope_for_rows` tiene el shape esperado
  por el modelo (se ve en como sintetiza la respuesta final).
- El contrato HTTP async (`POST` 202 + `GET` polling) esta cableado.

## Que valida (live mode, ademas)

- La auth contra BrightData.
- El dataset_id esta bien.
- El parser `sc_code` real de cosmetics-design emite filas que el middleware
  puede coercionar al contrato §2/§4.
- El ciclo `running -> done` de BrightData se mapea bien al contrato de
  `get_result` y el polling interno del harness (30s entre polls, 30 min de
  wall-clock) no sature `MAX_TURNS` del LLM.

## Limites del harness

- Sesiones en dict en memoria: se pierden al reiniciar uvicorn. El agente
  real de David persiste en RDS.
- No hay cola de mensajes por sesion: `POST /chat` sobre sesion busy es 409.
- No hay cache TTL de resultados (el repo de agentes lo hace con
  `scraper_runs` en Postgres).
- `MAX_TURNS=10` — si el modelo se atora en loop de tool-use, el harness
  corta y devuelve un reply marcado. Con el polling interno en live no
  deberia pasar.
- `live` y `fixture` son excluyentes por proceso (se eligen al arrancar
  uvicorn via env var).
