"""
Agilent Chemstation .D Folder Metadata Parser
==============================================

Extracts sample metadata from SAMPLE.MAC and ACQ.M/ACQ.TXT files
inside Agilent .D run folders.

Supported fields:
    - dilution: Dilution factor (from SAMPLE.MAC SAMPLECALAMT)
    - multiplier: Multiplier (from SAMPLE.MAC SAMPLECALAMT)
    - sample_amount: Sample amount (from SAMPLE.MAC SAMPLECALAMT)
    - injection_volume_uL: Injection volume in µL (from ACQ.TXT)
"""

import re
from pathlib import Path
from typing import Dict, Optional


def parse_sample_mac(mac_path: Path) -> Dict[str, float]:
    """
    Parse SAMPLE.MAC (UTF-16 encoded Chemstation macro) for calibration info.

    The macro contains: SAMPLECALAMT <amount>,<multiplier>,<dilution>

    Parameters
    ----------
    mac_path : Path
        Path to SAMPLE.MAC file

    Returns
    -------
    dict with keys: sample_amount, multiplier, dilution
    """
    result = {'sample_amount': 0.0, 'multiplier': 1.0, 'dilution': 1.0}

    if not mac_path.exists():
        return result

    try:
        with open(mac_path, 'rb') as f:
            data = f.read()
        text = data.decode('utf-16', errors='ignore')

        for line in text.splitlines():
            line = line.strip()
            if line.startswith('SAMPLECALAMT'):
                parts = line.split(None, 1)
                if len(parts) == 2:
                    vals = parts[1].split(',')
                    if len(vals) >= 1:
                        result['sample_amount'] = float(vals[0])
                    if len(vals) >= 2:
                        result['multiplier'] = float(vals[1])
                    if len(vals) >= 3:
                        result['dilution'] = float(vals[2])
                break
    except Exception:
        pass

    return result


def parse_acq_txt(acq_txt_path: Path) -> Dict[str, Optional[float]]:
    """
    Parse ACQ.M/ACQ.TXT (UTF-16 encoded) for acquisition parameters.

    Parameters
    ----------
    acq_txt_path : Path
        Path to ACQ.TXT file inside ACQ.M folder

    Returns
    -------
    dict with key: injection_volume_uL
    """
    result = {'injection_volume_uL': None}

    if not acq_txt_path.exists():
        return result

    try:
        with open(acq_txt_path, 'rb') as f:
            data = f.read()
        text = data.decode('utf-16', errors='ignore')

        for line in text.splitlines():
            if 'Injection Volume' in line:
                match = re.search(r'([\d.]+)\s*[µu]?L', line)
                if match:
                    result['injection_volume_uL'] = float(match.group(1))
                break
    except Exception:
        pass

    return result


def read_d_folder_metadata(d_folder: Path) -> Dict:
    """
    Read all available metadata from an Agilent .D run folder.

    Parameters
    ----------
    d_folder : Path
        Path to a .D folder (e.g., '260225_ACP_300_NC_90MIN.D')

    Returns
    -------
    dict with keys: sample_name, dilution, multiplier, sample_amount,
                    injection_volume_uL
    """
    d_folder = Path(d_folder)

    # Sample name from folder name
    sample_name = d_folder.name.replace('.D', '').strip()

    # Parse SAMPLE.MAC
    mac_info = parse_sample_mac(d_folder / 'SAMPLE.MAC')

    # Parse ACQ.TXT
    acq_info = parse_acq_txt(d_folder / 'ACQ.M' / 'ACQ.TXT')

    return {
        'sample_name': sample_name,
        **mac_info,
        **acq_info,
    }


def read_experiment_metadata(exp_folder: Path) -> list:
    """
    Read metadata for all .D folders in an experiment directory.

    Parameters
    ----------
    exp_folder : Path
        Path to experiment folder containing .D subfolders

    Returns
    -------
    list of dicts, one per .D folder
    """
    exp_folder = Path(exp_folder)
    results = []

    d_folders = sorted(
        [d for d in exp_folder.iterdir()
         if d.is_dir() and d.suffix.lower() == '.d']
    )

    for d_folder in d_folders:
        meta = read_d_folder_metadata(d_folder)
        meta['experiment'] = exp_folder.name
        meta['d_folder'] = str(d_folder)
        results.append(meta)

    return results


if __name__ == '__main__':
    import sys

    base = Path(r'C:\Chem32\1\DATA\2. D-Xyl cascade HPLC'
                r'\Xul 5P production\Pretest')

    print(f"{'Experiment':<45s} {'Sample':<45s} "
          f"{'Dil':>5s} {'Mult':>5s} {'Amt':>5s} {'InjVol':>8s}")
    print("-" * 160)

    for exp_dir in sorted(base.iterdir()):
        if not exp_dir.is_dir():
            continue
        for meta in read_experiment_metadata(exp_dir):
            inj = (f"{meta['injection_volume_uL']:.1f}"
                   if meta['injection_volume_uL'] else 'N/A')
            print(f"{meta['experiment']:<45s} {meta['sample_name']:<45s} "
                  f"{meta['dilution']:>5.0f} {meta['multiplier']:>5.0f} "
                  f"{meta['sample_amount']:>5.0f} {inj:>8s}")
