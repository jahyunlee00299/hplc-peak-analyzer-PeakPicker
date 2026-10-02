"""
Legacy-parser Chemstation reader
================================

IDataReader over ``src/chemstation_parser.ChemstationParser``, the format-130 decoder that matches the
independent ``rainbow`` decoder bit for bit on real lab files (see docs/feature-connectivity-ledger.md,
Unit 2b). It is the fallback of the default reader chain when rainbow is not installed or cannot parse a file.
"""

from pathlib import Path

from ...interfaces import IDataReader
from ...domain import ChromatogramData


def _parser_class():
    try:  # `src` on sys.path
        from chemstation_parser import ChemstationParser
    except ModuleNotFoundError:  # repo root on sys.path
        from src.chemstation_parser import ChemstationParser
    return ChemstationParser


class LegacyParserReader(IDataReader):
    """Reads Agilent Chemstation format-130/131 ``.ch`` files with the legacy parser."""

    SUPPORTED_EXTENSIONS = {'.ch'}

    def read(self, file_path: Path) -> ChromatogramData:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        parser = _parser_class()(str(file_path))
        time, intensity = parser.read()
        d_folder = file_path.parent
        sample_name = d_folder.stem if d_folder.suffix.lower() == '.d' else file_path.stem
        metadata = dict(parser.metadata)
        metadata['reader'] = 'LegacyParserReader'
        return ChromatogramData(
            time=time,
            intensity=intensity,
            sample_name=sample_name,
            detector_type='Signal',
            metadata=metadata,
        )

    def can_read(self, file_path: Path) -> bool:
        file_path = Path(file_path)
        return file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS
