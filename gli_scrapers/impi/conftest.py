"""Package-scoped conftest for the ``impi`` middleware.

Runs before ``tests/conftest.py`` so we add the checked-in ``impi_scraper_mx``
package root before any test module tries to import from the standalone package.

The fix is also re-applied defensively inside the middleware itself, so
this conftest is just belt-and-suspenders for pytest's collection order.
"""

from __future__ import annotations

from gli_scrapers.impi.client import _ensure_impi_scraper_mx_path

_ensure_impi_scraper_mx_path()
