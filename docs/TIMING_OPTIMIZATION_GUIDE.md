# Keyboard Automation Timing Optimization Guide

## Overview
A guide to optimizing the keyboard automation speed of `auto_export_keyboard_final.py`.

## Optimizations Applied (v2.1)

### 1. Global PyAutoGUI PAUSE Setting
```python
pyautogui.PAUSE = 0.2  # changed from 0.3 to 0.2
```

**Effect**: automatic wait time after every PyAutoGUI command (hotkey, press)
- **Original**: 0.3s (stable but slow)
- **Optimized**: 0.2s (33% speed improvement)
- **Fast**: 0.15s (2x faster but may reduce stability)

**Recommendation**:
- Prioritize stability: `0.3`
- Balanced (default): `0.2`
- Prioritize speed: `0.15` (needs testing)

---

### 2. Timing Inside the export_one_file() Function

| Step | Action | Original | Optimized | Notes |
|------|------|------|--------|------|
| 1 | Open the File menu | 0.5s | **0.3s** | only the menu-opening time is needed |
| 2 | Load Signal dialog | 1.0s | **0.8s** | dialog loading |
| 3a | Ctrl+A (select all) | 0.2s | **0.1s** | selects instantly |
| 3b | Ctrl+V (paste) | 0.5s | **0.3s** | pasting text |
| 4 | Enter (open file) | 3.0s | **2.5s** | 📌 **longest wait** (depends on file size) |
| 5 | Open the File menu | 0.5s | **0.3s** | opening the menu |
| 6 | Export menu | 0.5s | **0.3s** | submenu |
| 7 | Select CSV | 0.5s | **0.3s** | dialog |
| 8a | Down key x1 | 0.2s | **0.1s** | keystroke interval |
| 8b | Down key x2 | 0.3s | **0.15s** | selection confirmation |
| 9a | Enter x1 | 0.5s | **0.3s** | confirm |
| 9b | Enter x2 | 2.0s | **1.5s** | wait for export to complete |

**Total wait time**:
- Original: **10.2s** (with PAUSE 0.3s, ~13s total)
- Optimized: **7.65s** (with PAUSE 0.2s, ~9s total)
- **Improvement**: about **30% faster**

---

## Further Optimization Points

### 🔴 Important: Items to Adjust Carefully

#### 1. File Load Wait (Step 4)
```python
time.sleep(2.5)  # originally 3.0s
```
- **Current**: 2.5s
- **Possible range**: 1.5-4.0s
- **Note**: depends on file size and system performance
- **Recommendation**: keep 3.0s if there are many large files; can go down to 2.0s if only small files

#### 2. Export Completion Wait (Step 9b)
```python
time.sleep(1.5)  # originally 2.0s
```
- **Current**: 1.5s
- **Possible range**: 1.0-3.0s
- **Note**: moving to the next file before the export finishes causes an error
- **Recommendation**: keep 1.5s; restore to 2.0s if problems occur

---

## Experimental Optimization (Advanced Users)

### Aggressive Optimization Settings
If you want even faster speed, try the following settings:

```python
# Global setting
pyautogui.PAUSE = 0.15  # faster

# Inside the export_one_file() function
time.sleep(0.2)  # Step 1: File menu (originally 0.3)
time.sleep(0.6)  # Step 2: Load Signal (originally 0.8)
time.sleep(0.05) # Step 3a: Ctrl+A (originally 0.1)
time.sleep(0.2)  # Step 3b: Ctrl+V (originally 0.3)
time.sleep(2.0)  # Step 4: open file (originally 2.5) ⚠️ caution
time.sleep(0.2)  # Step 5-7: menus (originally 0.3)
time.sleep(0.05) # Step 8a: Down (originally 0.1)
time.sleep(0.1)  # Step 8b: Down (originally 0.15)
time.sleep(0.2)  # Step 9a: Enter (originally 0.3)
time.sleep(1.2)  # Step 9b: Export (originally 1.5) ⚠️ caution
```

**Expected total time**: ~6s (50% speed improvement)
**Risk**: failure rate may increase, thorough testing needed

---

## Troubleshooting

### If Export Failures Occur Frequently

1. **Increase Step 4 (file load) time**
   ```python
   time.sleep(3.0)  # or 3.5s
   ```

2. **Increase Step 9b (export completion) time**
   ```python
   time.sleep(2.0)  # or 2.5s
   ```

3. **Increase global PAUSE**
   ```python
   pyautogui.PAUSE = 0.3  # back to original
   ```

### If the System Is Fast
- If using an SSD and the system is fast, you can reduce all times to 80%
- e.g.: `time.sleep(0.3)` → `time.sleep(0.24)`

### If the System Is Slow
- If using an HDD or an older PC, increase the times
- Increasing Step 4 and 9b by 20-50% is recommended in particular

---

## Performance Measurements

Estimated time for 100 files:

| Setting | Time per file | Total time for 100 |
|------|-------------|---------------|
| Original (v2.0) | ~13s | ~22min |
| Optimized (v2.1) | ~9s | ~15min |
| Aggressive | ~6s | ~10min |

**Actual time**: varies depending on file load/export time

---

## Version History

### v2.1 (2025-11-06)
- PyAutoGUI PAUSE: 0.3 → 0.2
- Optimized all sleep times
- Added recursive folder search
- Added an interactive directory browser

### v2.0 (2025-11-06)
- Interactive path input
- Integrated hybrid baseline
