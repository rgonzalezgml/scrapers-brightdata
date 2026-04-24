# Sample requests — `POST /chat`

Queries listas para copiar al Swagger UI (`http://localhost:8000/docs`) del
`agent_harness`. Cada bloque es un `POST /chat` body completo.

El `session_id` va siempre en `null` para arrancar una conversación nueva.
Cuando el `POST` responde con `202 Accepted`, copiá el `session_id` devuelto
y polleá `GET /chat/{session_id}` cada ~30s hasta que `status` sea `done`
o `failed`.

Modo del harness:
- `AGENT_MODE=fixture` (default) → los 6 middlewares funcionan contra un
  snapshot hand-crafted. Perfecto para validar el tool-use del LLM.
- `AGENT_MODE=live` → pega a BrightData real. Solo `cosmetics_design` tiene
  collector configurado hoy; los otros 5 devuelven `INVALID_INPUTS` hasta que
  se configuren sus env vars (`BRIGHTDATA_DATASET_ID_<X>` o
  `BRIGHTDATA_COLLECTOR_ID_<X>`).

---

## 1. `cosmetics_design` — noticias industria cosmética

Scraper de `nutraingredients.com` sección Beauty & Wellness. Fuente de
tendencias regulatorias, lanzamientos, ingredientes emergentes.

### 1.1 Norteamérica últimos 30 días
```json
{
  "message": "Dame las últimas noticias de cosmética en Norteamérica de los últimos 30 días. Resumeme los 5 artículos más relevantes para I+D de Genomma.",
  "session_id": null,
  "middleware": "cosmetics_design"
}
```

### 1.2 Europa, belleza ingerible
```json
{
  "message": "Qué tendencias de belleza ingerible se están hablando en Europa este trimestre. Traé todos los artículos y sacá 3 insights accionables.",
  "session_id": null,
  "middleware": "cosmetics_design"
}
```

### 1.3 Full-refresh sobre longevity skincare
```json
{
  "message": "Consultá todo, sin filtrar por región ni ventana (modo full-refresh), y dame los 10 artículos más recientes sobre longevity skincare.",
  "session_id": null,
  "middleware": "cosmetics_design"
}
```

---

## 2. `cosme` — rankings Japón

Scraper de `cosme.net`. Rankings anuales de productos beauty en Japón,
categorías cíclicas, brands emergentes.

### 2.1 Ranking anual top 10
```json
{
  "message": "Traeme el ranking 2026 de productos beauty en Japón. Dame los top 10 productos y qué categorías dominan.",
  "session_id": null,
  "middleware": "cosme"
}
```

### 2.2 Solo skincare, sin brands
```json
{
  "message": "Buscame solo la categoría skincare de cosme para 2026, con rankings y sin brands. Máximo 50 productos.",
  "session_id": null,
  "middleware": "cosme"
}
```

### 2.3 Brands más rankeadas
```json
{
  "message": "Qué marcas japonesas son las más rankeadas este año. Traé solo la información de brands, sin productos individuales.",
  "session_id": null,
  "middleware": "cosme"
}
```

---

## 3. `olive_young` — K-beauty Korea

Scraper de `global.oliveyoung.com`. Bestsellers por región, rankings de
productos, catálogo de marcas coreanas.

### 3.1 Bestsellers región Global
```json
{
  "message": "Dame los bestsellers de Olive Young de la región Global. Top 20 productos con sus rankings.",
  "session_id": null,
  "middleware": "olive_young"
}
```

### 3.2 Skincare + makeup con brand visits limitadas
```json
{
  "message": "Traé los productos rankeados de las categorías skincare y makeup en Korea. Incluí info de las marcas pero sin visitar más de 10 brand pages.",
  "session_id": null,
  "middleware": "olive_young"
}
```

### 3.3 Solo rankings, tendencias actuales
```json
{
  "message": "Qué hay en tendencia en K-beauty esta semana. Solo rankings, sin productos ni brands detallados.",
  "session_id": null,
  "middleware": "olive_young"
}
```

---

## 4. `alibaba` — precios químicos industriales

Scraper de `alibaba.com`. Catálogo B2B global, precios USD, MOQ, proveedores
verificados por país.

### 4.1 Ácido hialurónico, top 10
```json
{
  "message": "Buscá proveedores de ácido hialurónico en Alibaba. Dame los 10 primeros con su precio USD por kg y el país del proveedor.",
  "session_id": null,
  "middleware": "alibaba"
}
```

### 4.2 Glicerina grado cosmético
```json
{
  "message": "Necesito comparar precios de glicerina grado cosmético. Buscá ese término y traé máximo 20 productos.",
  "session_id": null,
  "middleware": "alibaba"
}
```

### 4.3 Packaging — tarros de vidrio ámbar
```json
{
  "message": "Quiero tarros de vidrio ámbar de 30ml para cosmética. Dame productos con precio y MOQ de proveedores verificados.",
  "session_id": null,
  "middleware": "alibaba"
}
```

---

## 5. `made_in_china` — precios alternativos China

Scraper de `made-in-china.com`. Alternativa B2B a Alibaba, tiende a tener
precios mejores para materiales químicos y empaque.

### 5.1 Dióxido de titanio
```json
{
  "message": "Buscá dióxido de titanio grado cosmético en Made-in-China. Traé productos con precio y proveedores, máximo 30 productos.",
  "session_id": null,
  "middleware": "made_in_china"
}
```

### 5.2 Packaging PET para cremas
```json
{
  "message": "Necesito alternativas chinas a packaging de PET para cremas. Listame productos y suppliers, solo los que tienen precio.",
  "session_id": null,
  "middleware": "made_in_china"
}
```

### 5.3 Niacinamida — top 15 por precio
```json
{
  "message": "Comparame precios de niacinamida en Made-in-China. Dame top 15 por precio más bajo en USD/kg.",
  "session_id": null,
  "middleware": "made_in_china"
}
```

---

## 6. `indiamart` — precios India

Scraper de `indiamart.com`. Mercado B2B indio, precios INR (convertidos a
USD), proveedores con trustseal y verified_exporter.

### 6.1 Mentol cristalizado
```json
{
  "message": "Buscá proveedores de mentol cristalizado en India. Dame 10 productos con precio INR convertido a USD.",
  "session_id": null,
  "middleware": "indiamart"
}
```

### 6.2 Aceite de coco fraccionado
```json
{
  "message": "Necesito aceite de coco fraccionado de grado farmacéutico. Traé suppliers verificados de IndiaMART con trustseal.",
  "session_id": null,
  "middleware": "indiamart"
}
```

### 6.3 Caolín cosmético
```json
{
  "message": "Qué proveedores indios tienen caolín cosmético. Dame info de producto y supplier detallada.",
  "session_id": null,
  "middleware": "indiamart"
}
```

---

## Continuación de conversación en la misma sesión

Una vez que tenés un `session_id` con `status=done`, podés seguir la
conversación pasando ese `session_id`:

```json
{
  "message": "Del artículo 2 del listado, dame los actives mencionados y su respaldo científico.",
  "session_id": "<session_id_anterior>",
  "middleware": "cosmetics_design"
}
```

**Regla**: la sesión queda pinned al middleware del primer turno. Si mandás
el mismo `session_id` con otro middleware, respondé **409 Conflict** con el
detail `"session bound to <first_middleware>"`. Para cambiar de scraper
creá una sesión nueva (`session_id: null`).

---

## Debugging / otros endpoints

### Listar middlewares disponibles
```
GET /middlewares
```
Respuesta: `[{"name": "alibaba", "tools": ["alibaba_trigger", "alibaba_get_result"]}, ...]`.

### Healthcheck
```
GET /health
```
Respuesta: `{"status": "ok", "mode": "fixture", "model": "claude-opus-4-7", "middlewares": [...], "default_middleware": "cosmetics_design"}`.

### Cancelar sesión en curso
```
DELETE /sessions/{session_id}
```
Cancela la tarea background y limpia el estado de la sesión.

---

## Smoke test desde CLI (sin Swagger)

```bash
BASE=http://localhost:8000
MW=cosme

# 1) disparar
RES=$(curl -s -X POST $BASE/chat \
  -H 'content-type: application/json' \
  -d "{\"message\":\"ranking top 10 japón 2026\",\"middleware\":\"$MW\",\"session_id\":null}")
SID=$(echo "$RES" | python -c "import json,sys;print(json.load(sys.stdin)['session_id'])")
echo "session_id: $SID"

# 2) polear hasta terminal
while true; do
  OUT=$(curl -s $BASE/chat/$SID)
  STATUS=$(echo "$OUT" | python -c "import json,sys;print(json.load(sys.stdin)['status'])")
  echo "status: $STATUS"
  [ "$STATUS" != "running" ] && { echo "$OUT" | python -m json.tool; break; }
  sleep 30
done
```
