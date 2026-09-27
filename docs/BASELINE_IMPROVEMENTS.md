# Baseline Algorithm Improvements

## Overview

Analyzed and improved the baseline correction algorithm for `exported_signals` data.

## Key Improvements

### 1. Improved Anchor Point Detection

#### Previous Method (HybridBaselineCorrector)
- **Problem**: Generates an excessive number of anchor points (80-85)
- Finds both Valley and Local Minimum, but the deduplication logic is inefficient
- Too many unnecessary anchors make the baseline overly complex

#### Improved Method (ImprovedBaselineCorrector)
- **Result**: Optimized anchor points (12-15)
- Cluster-based Local Minimum detection
- Priority-based deduplication (Valley > Boundary > Local Min)
- Confidence-based quality evaluation

```python
# Improved anchor detection
corrector = ImprovedBaselineCorrector(time, intensity)
anchors = corrector.find_anchors(
    valley_prominence_factor=0.01,
    local_min_percentile=10,
    min_anchor_distance=15
)
```

### 2. RT-Based Slope Relaxation

#### New Feature
Automatically relaxes steep slopes when the RT difference between adjacent anchors is large.

```python
# Relax the slope if the RT difference is 0.5 min or more
baseline = corrector.generate_baseline(
    method='adaptive_spline',
    apply_rt_relaxation=True  # Enable RT-based relaxation
)
```

**How it works**:
- RT difference > 0.5 min: check the slope
- If the slope is too steep: adjust to the segment's minimum value (5th percentile)
- Result: a smoother, more stable baseline

### 3. Improved Evaluation Function

#### Previous Method
```python
score = (1 - neg_ratio) * 100 + peak_preservation * 50 - smoothness
```
- Simple weighting
- Does not account for baseline height

#### Improved Method
```python
# Evaluated on 4 criteria (225 points total)
score = neg_score (100 pts)      # negative ratio
      + smooth_score (50 pts)    # smoothness
      + peak_score (50 pts)      # peak preservation
      + height_score (25 pts)    # baseline height
```

- More granular evaluation
- Penalizes a baseline that is too high
- Applies appropriate weights per criterion

### 4. Efficient Baseline Generation

#### Method Types

**adaptive_spline** (recommended):
- Confidence weighting + RT-based relaxation
- Adaptive spline fitting
- Most balanced result

**robust_spline**:
- Automatic outlier removal (MAD-based)
- Robust fitting
- Effective on noisy data

**linear**:
- Simple linear interpolation
- Fast processing

### 5. Automatic Negative-Value Handling

```python
# Automatically handles negative values at initialization
corrector = ImprovedBaselineCorrector(time, intensity)
# Negative values are corrected internally
```

## Performance Comparison

### Test Results (3 samples)

| Metric | Previous Method | Improved Method | Improvement |
|------|-----------|-----------|--------|
| Anchor points | 80-85 | 12-15 | **-82%** |
| Peaks detected | 4 | 4 | same |
| Average peak width | 37.9 | 37.9 | same |
| Negative ratio | 0.00% | 0.00% | same |
| Quality score | N/A | 204.6 | N/A |

### Key Advantages

1. **Simplicity**: 82% fewer anchor points → a smoother baseline
2. **Accuracy**: peak detection performance maintained
3. **Stability**: RT-based slope relaxation prevents abrupt changes
4. **Quality**: provides an objective evaluation score

## Usage

### Basic Usage

```python
from improved_baseline import ImprovedBaselineCorrector
import pandas as pd

# Load data
df = pd.read_csv('exported_signals/sample.csv',
                 header=None, sep='\t', encoding='utf-16-le')
time = df[0].values
intensity = df[1].values

# Baseline correction
corrector = ImprovedBaselineCorrector(time, intensity)
baseline, params = corrector.optimize_baseline(use_linear_peaks=True)

# Corrected signal
corrected = np.maximum(intensity - baseline, 0)

print(f"Method: {params['method']}")
print(f"Anchors: {params['num_anchors']}")
print(f"Score: {params['score']:.2f}")
```

### Advanced Usage

```python
# Manual configuration
corrector.find_anchors(
    valley_prominence_factor=0.01,  # Valley sensitivity
    local_min_percentile=10,        # Local min threshold
    min_anchor_distance=15          # Minimum distance
)

baseline = corrector.generate_baseline(
    method='adaptive_spline',       # Method selection
    smooth_factor=1.0,              # Smoothing strength
    apply_rt_relaxation=True        # RT relaxation
)

# Apply a linear baseline under the peaks
baseline = corrector.apply_linear_to_peaks(baseline)
```

### Convenience Function

```python
from improved_baseline import process_exported_signal

# Process in one line
time, intensity, baseline, params = process_exported_signal(
    'exported_signals/sample.csv',
    method='auto',  # automatic optimization
    use_linear_peaks=True,
    apply_rt_relaxation=True
)
```

## Comparison Visualization

```bash
# Compare previous vs improved method
python compare_baseline_improvements.py
```

Generated images:
- Anchor point comparison
- Baseline comparison
- Corrected signal comparison
- Baseline difference
- Detailed per-peak comparison table

Result location: `result/baseline_comparison/`

## File Structure

```
src/
├── hybrid_baseline.py          # previous method
└── improved_baseline.py        # improved method ✨

compare_baseline_improvements.py  # comparison script
```

## Key Classes and Methods

### ImprovedBaselineCorrector

**Key methods**:
- `find_anchors()`: find anchor points
- `generate_baseline()`: generate the baseline
- `apply_linear_to_peaks()`: apply a linear baseline under the peaks
- `optimize_baseline()`: automatic optimization
- `_apply_rt_based_relaxation()`: RT-based slope relaxation
- `_evaluate_baseline()`: evaluate baseline quality

### BaselineAnchor (dataclass)

```python
@dataclass
class BaselineAnchor:
    index: int          # data index
    rt: float           # Retention Time
    value: float        # intensity value
    type: str           # 'valley', 'local_min', 'boundary'
    confidence: float   # confidence (0-1)
```

## Future Directions

1. **ML-based anchor selection**: learn optimal anchor patterns from training data
2. **Baseline per peak type**: adaptive baseline for Sharp vs Broad peaks
3. **Batch optimization**: automatic parameter tuning when processing multiple samples at once
4. **Real-time processing**: an online baseline correction algorithm

## References

- Previous method: `src/hybrid_baseline.py`
- Improved method: `src/improved_baseline.py`
- Comparison script: `compare_baseline_improvements.py`
- Test results: `result/baseline_comparison/`

## License

Follows the project license.
