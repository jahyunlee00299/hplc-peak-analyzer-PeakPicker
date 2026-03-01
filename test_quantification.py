"""Full pipeline test: read → quantify → stats → export"""
import sys
sys.path.insert(0, '.')
from pathlib import Path

# Step 1: Batch peak analysis with rainbow reader
from src.peakpicker.application import WorkflowBuilder

workflow = (WorkflowBuilder()
    .with_rainbow_reader()
    .with_default_baseline()
    .with_default_peak_detector()
    .build())

data_dir = Path(r'C:\Chem32\1\DATA\260216_cofactor_m2_main_new')
ch_files = sorted([d / 'RID1A.ch' for d in data_dir.iterdir()
                   if d.is_dir() and d.suffix.upper() == '.D' and (d / 'RID1A.ch').exists()])

print(f'Found {len(ch_files)} .ch files')
batch_result = workflow.analyze_batch(ch_files)
print(f'Batch: {batch_result.total_samples} samples analyzed')

# Quick check: what peaks are in the Tagatose/Formate RT range?
tag_count = 0
form_count = 0
for r in batch_result.results:
    for p in r.peaks:
        if 10.5 <= p.rt <= 11.2:
            tag_count += 1
        if 11.3 <= p.rt <= 12.0:
            form_count += 1
print(f'Peaks in Tagatose RT window (10.5-11.2): {tag_count}')
print(f'Peaks in Formate RT window (11.3-12.0): {form_count}')

# Step 2: Quantification workflow
from src.peakpicker import QuantificationPresets, create_quantification_workflow

config = QuantificationPresets.cofactor_m2_nad(dilution_factor=66.666666)
from src.peakpicker.domain.enums import VisualizationMode
config.visualization.mode = VisualizationMode.ALL_CONDITIONS
output_dir = data_dir / 'peakpicker_quant_results'

quant_workflow = create_quantification_workflow(
    compounds=config.calibration.compounds,
    dilution_factor=66.666666,
    config=config,
)

quant_result, stat_result, files = quant_workflow.run(
    batch_result=batch_result,
    output_dir=output_dir,
    filename_prefix='cofactor_m2',
)

print(f'\n=== Quantification Results ===')
print(f'Quantified peaks: {len(quant_result.quantified_peaks)}')
print(f'Compounds: {quant_result.compound_names}')
print(f'Samples: {len(quant_result.sample_names)}')

# NC t=0 reference check
for compound_name in quant_result.compound_names:
    nc_mean = quant_result.get_nc_mean(compound_name)
    print(f'  NC t=0 for {compound_name}: {nc_mean}')

# Show some concentrations
for compound_name in quant_result.compound_names:
    qps = quant_result.get_by_compound(compound_name)
    concs = [qp.concentration_original for qp in qps]
    if concs:
        import numpy as np
        print(f'\n  {compound_name}: n={len(concs)}, '
              f'mean={np.mean(concs):.2f}, '
              f'range=[{min(concs):.2f}, {max(concs):.2f}]')

# Step 3: Statistical results
if stat_result:
    print(f'\n=== Statistical Results ===')
    print(f'Tests performed: {len(stat_result.test_results)}')
    for tr in stat_result.test_results:
        sig_pairs = [c for c in tr.pairwise_comparisons if c.significance != 'ns']
        print(f'  {tr.compound_name}/{tr.enzyme}/{tr.time_h}: '
              f'ANOVA F={tr.anova_f_statistic:.3f} p={tr.anova_p_value:.4f} {tr.anova_significance} '
              f'| {len(sig_pairs)} significant pairs')

# Step 4: Output files
print(f'\n=== Output Files ===')
for f in files:
    print(f'  {f.name} ({f.stat().st_size / 1024:.1f} KB)')

print('\n=== TEST COMPLETE ===')
