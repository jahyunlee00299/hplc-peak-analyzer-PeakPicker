"""
Auto-detecting File Reader
===========================

Composite reader that selects the appropriate reader
based on the input file type. Follows Open/Closed Principle.
"""

from pathlib import Path
from typing import List

from ...interfaces import IDataReader
from ...domain import ChromatogramData


class AutoReader(IDataReader):
    """
    Auto-detecting reader that delegates to the first
    compatible reader in its chain.
    """

    def __init__(self, readers: List[IDataReader]):
        if not readers:
            raise ValueError("At least one reader is required")
        self.readers = readers

    def read(self, file_path: Path) -> ChromatogramData:
        """Read using the first compatible reader."""
        file_path = Path(file_path)

        for reader in self.readers:
            if reader.can_read(file_path):
                return reader.read(file_path)

        reader_names = [type(r).__name__ for r in self.readers]
        raise ValueError(
            f"No compatible reader found for: {file_path}\n"
            f"Tried: {reader_names}"
        )

    def can_read(self, file_path: Path) -> bool:
        """Check if any reader can handle this file."""
        file_path = Path(file_path)
        return any(r.can_read(file_path) for r in self.readers)
