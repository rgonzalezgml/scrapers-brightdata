# Instalar y usar MCP BrightData en Claude CLI

Guía para conectar el [MCP Server de BrightData](https://docs.brightdata.com/ai/mcp-server/integrations/claude-code) a Claude Code vía CLI, quedando disponible en cualquier sesión del proyecto.

Referencia oficial: <https://docs.brightdata.com/ai/mcp-server/integrations/claude-code>

---

## 1. Requisitos previos

- **Claude Code CLI** instalado y autenticado (`claude --version` debe funcionar).
- **Cuenta de BrightData** con un API token. Se obtiene en el dashboard de BrightData → *Account settings* → *API tokens*.
- Shell con acceso a internet hacia `mcp.brightdata.com`.

---

## 2. Instalación del MCP

Registrar el servidor MCP vía transporte **SSE** con el token como query param:

```bash
claude mcp add --transport sse brightdata "https://mcp.brightdata.com/sse?token=<your-api-token>"
```

Reemplazar `<your-api-token>` por el token real. El servidor queda registrado con el nombre `brightdata`.

### Alcance del registro

Por defecto, `claude mcp add` guarda el MCP en el scope de **usuario**, disponible en todas las sesiones. Para limitarlo al proyecto actual:

```bash
claude mcp add --scope project --transport sse brightdata "https://mcp.brightdata.com/sse?token=<your-api-token>"
```

---

## 3. Verificación

Listar los MCPs registrados:

```bash
claude mcp list
```

Se debe ver una entrada `brightdata` con transport `sse` y la URL configurada.

Dentro de una sesión de Claude Code, las herramientas del MCP aparecen con el prefijo `mcp__brightdata__`. Ejemplos:

- `mcp__brightdata__scrape_as_markdown` — descarga una URL y la devuelve como markdown limpio.
- `mcp__brightdata__scrape_batch` — scraping en lote de múltiples URLs.
- `mcp__brightdata__search_engine` — búsqueda contra Google/Bing/otros motores.
- `mcp__brightdata__search_engine_batch` — búsquedas en lote.

---

## 4. Uso desde una sesión de Claude Code

Una vez registrado, se invocan pidiéndole a Claude lo que se necesita. Claude decide cuándo usar las tools del MCP. Ejemplos de prompts que disparan el MCP:

- *"Scrapea esta URL como markdown: https://ejemplo.com/articulo"*
- *"Buscá en Google los primeros 10 resultados para 'site:genomma.com producto X'"*
- *"Descargá en paralelo estas 20 URLs y devolvé el texto principal de cada una"*

Para forzar el uso del MCP se puede ser explícito: *"usá `mcp__brightdata__scrape_as_markdown` para…"*.

---

## 5. Desinstalación / re-configuración

Eliminar el MCP:

```bash
claude mcp remove brightdata
```

Para rotar el token: removerlo y volverlo a registrar con el nuevo token.

---

## 6. Troubleshooting

| Síntoma | Causa probable | Resolución |
|---------|----------------|------------|
| `claude mcp list` no muestra `brightdata` | Se registró en otro scope | Repetir con `--scope project` o `--scope user` según corresponda |
| Error 401 / token inválido | Token expirado o mal copiado | Regenerar token en BrightData y reinstalar |
| Timeout al invocar tools | Firewall bloquea `mcp.brightdata.com` o SSE | Verificar conectividad y que no haya proxy corporativo interceptando SSE |
| Las tools no aparecen en la sesión | Sesión iniciada antes del `mcp add` | Cerrar y reabrir Claude Code |

---

## 7. Seguridad del token

- **No commitear** el token en el repo ni en archivos de documentación.
- Preferir el scope de **usuario** para no arrastrarlo al proyecto compartido.
- Rotarlo si se sospecha filtración (ver sección 5).
