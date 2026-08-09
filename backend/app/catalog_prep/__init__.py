"""Turning a client's spreadsheet into a canonical Vista catalog dataset.

This package prepares data. It does not import it: the output is a preview-dataset YAML
file, and `scripts.preview_cli` remains the only thing that writes a catalog into a
database. Nothing here mutates a product, a category, a media asset or an order.
"""

from app.catalog_prep.prepare import (
    Issue,
    PreparationError,
    PreparedCatalog,
    prepare_catalog,
    render_yaml,
)
from app.catalog_prep.workbook import SheetRow, WorkbookError, read_sheets

__all__ = [
    "Issue",
    "PreparationError",
    "PreparedCatalog",
    "SheetRow",
    "WorkbookError",
    "prepare_catalog",
    "read_sheets",
    "render_yaml",
]
