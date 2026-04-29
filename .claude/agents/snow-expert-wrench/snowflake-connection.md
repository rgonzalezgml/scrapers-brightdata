# Snowflake Connection & Snowpark

---

## Key-Pair Authentication (connector Python) — DDL / SYSADMIN

Usado por snow-expert-wrench para operaciones DDL (CREATE, ALTER, DROP).
Clave privada en `~/.claude/credentials/keys/rsa_key.p8` (fuera de todos los proyectos).
Para todas las conexiones disponibles, ver `~/.claude/credentials/snowflake-connections.md`.

```python
import os, snowflake.connector, dotenv
from cryptography.hazmat.primitives.serialization import (
    load_pem_private_key, Encoding, PrivateFormat, NoEncryption
)
from cryptography.hazmat.backends import default_backend

# Cargar .env relativo al proyecto (ajustar base_path según proyecto activo)
dotenv.load_dotenv('backend/.env')

_key_path = os.path.expanduser("~/.claude/credentials/keys/rsa_key.p8")
_phrase = None  # rsa_key.p8 sin passphrase

with open(_key_path, 'rb') as f:
    pkb = load_pem_private_key(
        f.read(), password=_phrase, backend=default_backend()
    ).private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())

conn = snowflake.connector.connect(
    account     = "QOB68501-GENOMMALAB",
    user        = "ATELLEZ",
    private_key = pkb,
    warehouse   = "GENOMMA",
    role        = "SYSADMIN",   # para DDL; ver snowflake-connections.md para otras conexiones
    database    = "DEV_STG",
    schema      = "GNM_MEX",
)
cursor = conn.cursor()
```

**Role selector:**
| Operación | Role |
|-----------|------|
| DDL (CREATE, ALTER, DROP) | `SYSADMIN` |
| Queries / CALL SPs en DEV | `DEV_APP_SERVICE` |
| Queries / CALL SPs en PRD | `PRD_APP_SERVICE` |

**PROHIBIDO via esta conexión:** Crear o modificar usuarios, roles, resource monitors, ni grants a roles.

---

## Ejecutar DDL — una sentencia a la vez

`execute_string()` falla en cuerpos complejos de SPs. Siempre usar `cursor.execute()` individual:

```python
# Partir el script por ';' y ejecutar cada sentencia
statements = [s.strip() for s in sql_script.split(';') if s.strip()]
for stmt in statements:
    try:
        cursor.execute(stmt)
        print(f"[OK] {stmt[:80]}...")
    except Exception as e:
        print(f"[ERR] {stmt[:80]}... → {e}")
finally:
    cursor.close()
    conn.close()
```

---

## SnowPark Session (Python)

```python
from snowflake.snowpark import Session

def get_session(config: dict) -> Session:
    return Session.builder.configs({
        "account":   config["account"],
        "user":      config["user"],
        "password":  config["password"],   # o private_key para key-pair
        "role":      config["role"],
        "warehouse": config["warehouse"],
        "database":  config["database"],
        "schema":    config["schema"],
        "session_parameters": {
            "STATEMENT_TIMEOUT_IN_SECONDS": 300,
            "LOCK_TIMEOUT": 60,
        },
    }).create()
```

### Snowpark dentro de Streamlit in Snowflake (SiS)

```python
from snowflake.snowpark.context import get_active_session
session = get_active_session()  # usa la sesión activa de SiS — sin credenciales
```

### Cargar DataFrame a Snowflake

```python
def load_to_snowflake(session, df, table: str, mode: str = "overwrite"):
    """mode: 'overwrite' | 'append' | 'errorifexists'"""
    session.create_dataframe(df).write.mode(mode).save_as_table(table)
```

### Llamar SPs desde Python

```python
result = session.call("DEV_STG.VENTAS.SP_LOAD_VTA_SELLOUT", "AIRFLOW_WMS", "FULL")
print(result)  # Retorna VARIANT como dict
```

---

## Variables de Entorno esperadas (`.env`)

```
SNOWFLAKE_ACCOUNT=<org>-<account>
SNOWFLAKE_USER=<service_user>
SNOWFLAKE_WAREHOUSE=<warehouse_name>
SNOWFLAKE_PRIVATE_KEY_PATH=credentials/keys/rsa_key.p8
SNOWFLAKE_PRIVATE_KEY_PASSPHRASE=<passphrase_or_empty>
```
