"""Import-file adapters implementing `app.core.import_parser.ImportParser`."""

from app.infrastructure.import_parsers.bos import BosParser
from app.infrastructure.import_parsers.xtb import XtbParser

__all__ = ["BosParser", "XtbParser"]
