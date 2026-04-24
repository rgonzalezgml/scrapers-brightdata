# Fixtures — impi middleware

## `impi_snapshot_s_demo01.json`

**Hand-crafted, NOT captured from a real IMPI portal run.** The suffix
`s_demo01` is a placeholder snapshot id used by the harness fixture-mode
dispatcher (`agent_harness/registry.py::_fixture_path_for`).

## Why hand-crafted

The `impi` middleware wraps the standalone `impi_scraper_mx` package which hits
the IMPI Mexico portal directly. There is no BrightData snapshot to capture
— the natural "real" artifact would be a JSON dump of
`IMPIClient.search(...).rows` against a live run, but:

- The portal requires outbound connectivity to `marcia.impi.gob.mx` and can
  be rate-limited or IP-blocked, so a hands-off capture during CI is not
  reliable.
- The row shape is fully determined by
  `impi_scraper_mx.models.Marca` (10 fields, spec in the standalone package's
  README). Hand-crafting guarantees we exercise every edge case without
  flakiness.

The rows here mirror exactly the `Marca.model_dump()` shape: the same 10
keys, all present on every row (null or `[]` for missing values), including
`scraper_flags` which is a list even when empty.

## Scenarios covered

| denominacion      | scenario                                                |
|-------------------|---------------------------------------------------------|
| `TAFIROL`         | clean row, owner match, no image                        |
| `SUERO-BEBE`      | clean row, empty `imagen` list                          |
| `OXISEPT`         | paginated flag + image as string URL                    |
| `X-IBUPROFENO`    | `owner_mismatch` flag + null registration number        |

## Harness fixture mode

When the harness runs with `AGENT_MODE=fixture`, it loads this file via
`agent_harness/registry.py::_fixture_for("impi")` and passes the rows to
`IMPIMiddlewareClient.build_envelope_for_rows(rows, public_inputs={})`. The
resulting envelope is what `get_result` returns without ever hitting the
IMPI portal.

## TODO — replace with a real capture

Once we have a scheduled run against the portal, dump one cycle's rows to
this file via something like:

```python
from impi_scraper_mx import IMPIClient, SearchInputs
import json
with IMPIClient() as client:
    result = client.search(SearchInputs(owner="Genomma", expires_within_days=90))
with open("impi_snapshot_<yyyymmdd>.json", "w") as fh:
    json.dump([m.model_dump() for m in result.rows], fh, indent=2)
```

Then update `tests/conftest.py::SNAPSHOT_FIXTURE` to point at the new file
and delete this hand-crafted fixture.
