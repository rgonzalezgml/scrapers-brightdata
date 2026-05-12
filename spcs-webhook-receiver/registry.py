from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Type


@dataclass
class ScraperHandler:
    client_cls: Type[Any]
    mapper: Any
    # Optional post-ETL filter: return True to keep the row, False to drop it.
    row_filter: Callable[[dict[str, Any]], bool] | None = field(default=None)


def _build_registry() -> dict[str, ScraperHandler]:
    from gli_scrapers.alibaba.client import AlibabaClient
    from gli_scrapers.alibaba.config import MAPPER as ALIBABA_MAPPER

    from gli_scrapers.indiamart.client import IndiamartClient
    from gli_scrapers.indiamart.config import MAPPER as INDIAMART_MAPPER

    from gli_scrapers.made_in_china.client import MadeInChinaClient
    from gli_scrapers.made_in_china.config import MAPPER as MADE_IN_CHINA_MAPPER

    from gli_scrapers.cosmetics_design.client import CosmeticsDesignClient
    from gli_scrapers.cosmetics_design.config import MAPPER as COSMETICS_DESIGN_MAPPER

    from gli_scrapers.cosme_ranking_products.client import CosmeRankingClient
    from gli_scrapers.cosme_ranking_products.config import MAPPER as COSME_RANKING_MAPPER

    from gli_scrapers.olive_young.client import OliveYoungClient
    from gli_scrapers.olive_young.config import MAPPER as OLIVE_YOUNG_MAPPER

    from gli_scrapers.olive_young_new_arrivals.client import OliveYoungNewArrivalsClient
    from gli_scrapers.olive_young_new_arrivals.config import MAPPER as OLIVE_YOUNG_NA_MAPPER

    from gli_scrapers.cosme_new_arrivals.client import CosmeNewArrivalsClient
    from gli_scrapers.cosme_new_arrivals.config import MAPPER as COSME_NA_MAPPER

    return {
        "alibaba": ScraperHandler(
            client_cls=AlibabaClient,
            mapper=ALIBABA_MAPPER,
            row_filter=lambda r: bool(r.get("price_raw")),
        ),
        "indiamart": ScraperHandler(client_cls=IndiamartClient, mapper=INDIAMART_MAPPER),
        "made_in_china": ScraperHandler(client_cls=MadeInChinaClient, mapper=MADE_IN_CHINA_MAPPER),
        "cosmetics_design": ScraperHandler(client_cls=CosmeticsDesignClient, mapper=COSMETICS_DESIGN_MAPPER),
        "cosme_ranking_products": ScraperHandler(client_cls=CosmeRankingClient, mapper=COSME_RANKING_MAPPER),
        "olive_young": ScraperHandler(client_cls=OliveYoungClient, mapper=OLIVE_YOUNG_MAPPER),
        "olive_young_new_arrivals": ScraperHandler(client_cls=OliveYoungNewArrivalsClient, mapper=OLIVE_YOUNG_NA_MAPPER),
        "cosme_new_arrivals": ScraperHandler(client_cls=CosmeNewArrivalsClient, mapper=COSME_NA_MAPPER),
    }


REGISTRY: dict[str, ScraperHandler] = _build_registry()
