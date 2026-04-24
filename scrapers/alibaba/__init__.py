"""Alibaba scraper — contrato de datos + implementaciones sc_browser/sc_code.

Spec: docs/specs/brightd-scrapers/alibaba/module-spec-v2.md
El schema canónico vive en `scrapers.alibaba.models.AlibabaProduct`
y es inmutable entre implementaciones (vendor/* y sc_browser/sc_code).
"""

from scrapers.alibaba.models import AlibabaProduct

__all__ = ["AlibabaProduct"]
