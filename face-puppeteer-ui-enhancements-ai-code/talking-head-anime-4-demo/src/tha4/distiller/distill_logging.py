"""
Optional file mirror for distill-related INFO logs.

Set environment variable THA4_DISTILL_LOG to an absolute or relative path; child
processes (torchrun) inherit it, so face and body stages append to the same file.

Log lines use an explicit timestamp prefix so external monitors can correlate saves
and progress without reading another console.
"""

from __future__ import annotations

import logging
import os


_LOG_FMT = "%(asctime)s %(levelname)s:%(name)s:%(message)s"
_LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"


def configure_distill_logging() -> None:
    path = os.environ.get("THA4_DISTILL_LOG", "").strip()
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if path:
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        handlers.append(logging.FileHandler(path, mode="a", encoding="utf-8"))
    formatter = logging.Formatter(fmt=_LOG_FMT, datefmt=_LOG_DATEFMT)
    for h in handlers:
        h.setFormatter(formatter)
    logging.basicConfig(level=logging.INFO, handlers=handlers, force=True)


def log_distill_project_banner(project_name: str, character_image: str, output_prefix: str) -> None:
    """One-line banner for monitors; runs after configure_distill_logging(). Tabs separate fields."""
    safe_prefix = output_prefix.replace("\t", " ").replace("\r", " ").replace("\n", " ")
    logging.info(
        "[tha4_distill] project_name=%s\tcharacter_image=%s\toutput_prefix=%s",
        project_name,
        character_image,
        safe_prefix,
    )
