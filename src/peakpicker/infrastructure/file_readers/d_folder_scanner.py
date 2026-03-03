"""
.D Folder Scanner
==================

Scans directories for Agilent .D data folders.
"""

import logging
import re
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class DFolderScanner:
    """Scans directories for .D folders."""

    def __init__(self, recursive: bool = True, max_depth: int = 5):
        self.recursive = recursive
        self.max_depth = max_depth

    def scan(
        self,
        root_dir: Path,
        pattern: Optional[str] = None,
        exclude_pattern: Optional[str] = None,
    ) -> List[Path]:
        """
        Find all .D folders under root_dir.

        Parameters
        ----------
        root_dir : Path
            Root directory to scan
        pattern : str, optional
            Regex to filter .D folder names (e.g., '.*STD.*')
        exclude_pattern : str, optional
            Regex to exclude .D folder names

        Returns
        -------
        List[Path]
            Sorted list of .D folder paths
        """
        root_dir = Path(root_dir)
        if not root_dir.exists():
            raise FileNotFoundError(f"Directory not found: {root_dir}")

        d_folders: List[Path] = []

        if self.recursive:
            self._scan_recursive(root_dir, d_folders, 0)
        else:
            for item in root_dir.iterdir():
                if item.is_dir() and item.suffix.lower() == '.d':
                    d_folders.append(item)

        if pattern:
            regex = re.compile(pattern, re.IGNORECASE)
            d_folders = [f for f in d_folders if regex.search(f.stem)]

        if exclude_pattern:
            regex = re.compile(exclude_pattern, re.IGNORECASE)
            d_folders = [f for f in d_folders if not regex.search(f.stem)]

        d_folders.sort()
        return d_folders

    def scan_for_std_and_samples(self, root_dir: Path) -> dict:
        """
        Scan and categorize .D folders into STD and sample groups.

        Returns
        -------
        dict
            {'std': [...], 'samples': [...], 'all': [...]}
        """
        all_folders = self.scan(root_dir)

        std_folders = [f for f in all_folders if 'STD' in f.stem.upper()]
        sample_folders = [f for f in all_folders if 'STD' not in f.stem.upper()]

        return {
            'std': std_folders,
            'samples': sample_folders,
            'all': all_folders,
        }

    def _scan_recursive(
        self, directory: Path, results: List[Path], depth: int
    ):
        if depth > self.max_depth:
            return

        try:
            for item in directory.iterdir():
                if item.is_dir():
                    if item.suffix.lower() == '.d':
                        results.append(item)
                    else:
                        self._scan_recursive(item, results, depth + 1)
        except (PermissionError, OSError) as e:
            logger.warning(f"Cannot access {directory}: {e}")
