"""Logging setup shared by the pipeline script and the notebook."""

from __future__ import annotations

import logging


def configure_logging(level: int | str = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        force=True,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
