"""
Anchor Filters
==============

Post-filters for baseline anchor points, shared by the baseline strategies.
"""

import numpy as np


def baseline_anchor_mask(
    indices: np.ndarray,
    values: np.ndarray,
    signal_range: float,
    k: int = 7,
) -> np.ndarray:
    """
    Boolean mask of anchors that lie on the baseline rather than on a peak flank.

    An anchor finder that takes the lowest point of every window also returns anchors for windows
    that lie entirely on a peak flank; interpolating through them lifts the baseline under the peak
    (flat baseline + one peak: area recovered ~40-65 %).

    An anchor is rejected when it exceeds the median of its ``k`` nearest anchors by more than
    3 robust sigma (MAD of the residuals, floored at 0.5 % of ``signal_range`` so a noise-free
    baseline does not make the test hypersensitive). Neighbour medians follow a drifting or curved
    baseline, unlike one global median. The first and last anchors are kept, and the filter is
    skipped (everything kept) when fewer than 6 anchors exist or fewer than 4 would remain.

    Parameters
    ----------
    indices, values : np.ndarray
        Anchor sample indices (sorted ascending) and signal values.
    signal_range : float
        Peak-to-peak range of the signal, used for the noise floor.
    k : int
        Number of neighbouring anchors in the local median.
    """
    indices = np.asarray(indices)
    values = np.asarray(values)
    n = len(indices)
    keep = np.ones(n, dtype=bool)
    if n < 6:
        return keep
    floor = 0.005 * signal_range
    for _ in range(3):
        idx_k, val_k = indices[keep], values[keep]
        if len(idx_k) < 6:
            break
        kk = min(k, len(idx_k) - 1)
        resid = np.empty(len(idx_k))
        for j in range(len(idx_k)):
            order = np.argsort(np.abs(idx_k - idx_k[j]))[1:kk + 1]
            resid[j] = val_k[j] - np.median(val_k[order])
        scale = max(1.4826 * np.median(np.abs(resid - np.median(resid))), floor)
        bad = resid > 3.0 * scale
        bad[0] = bad[-1] = False
        if not bad.any():
            break
        keep_positions = np.flatnonzero(keep)
        keep[keep_positions[bad]] = False
    if keep.sum() < 4:
        return np.ones(n, dtype=bool)
    return keep
