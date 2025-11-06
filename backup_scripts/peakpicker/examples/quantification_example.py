"""
Example: Quantitative Analysis with Standard Curves
"""

import sys
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

sys.path.append(str(Path(__file__).parent.parent))

from modules.quantification import QuantitativeAnalyzer


def example_basic_calibration():
    """Example 1: Basic calibration curve"""
    print("\n" + "="*60)
    print("Example 1: Basic Calibration Curve")
    print("="*60)

    # Standard solutions (perfect linear relationship)
    concentrations = [0.0, 1.0, 2.5, 5.0, 10.0]  # mg/L
    areas = [0.0, 100.0, 250.0, 500.0, 1000.0]   # Peak area

    print("Standard solutions:")
    for conc, area in zip(concentrations, areas):
        print(f"  {conc:>5.1f} mg/L → Area: {area:>7.1f}")

    # Create calibration curve
    analyzer = QuantitativeAnalyzer()
    curve = analyzer.create_standard_curve(
        concentrations=concentrations,
        areas=areas,
        curve_name="basic_curve",
        method="linear"
    )

    print(f"\n✓ Calibration curve created")
    print(f"  Equation: {curve.equation}")
    print(f"  Slope: {curve.slope:.4f}")
    print(f"  Intercept: {curve.intercept:.4f}")
    print(f"  R²: {curve.r_squared:.6f}")

    # Visualize
    fig, ax = plt.subplots(figsize=(10, 6))

    # Data points
    ax.scatter(concentrations, areas, s=100, c='blue', label='Standard Points', zorder=3)

    # Regression line
    conc_range = np.linspace(0, max(concentrations) * 1.1, 100)
    pred_areas = curve.slope * conc_range + curve.intercept
    ax.plot(conc_range, pred_areas, 'r--', linewidth=2, label='Calibration Line')

    ax.set_xlabel('Concentration (mg/L)', fontsize=12)
    ax.set_ylabel('Peak Area', fontsize=12)
    ax.set_title(f'Calibration Curve\n{curve.equation}, R² = {curve.r_squared:.6f}',
                 fontsize=14, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    output_file = Path(__file__).parent / "calibration_curve_basic.png"
    plt.tight_layout()
    plt.savefig(output_file, dpi=300)
    print(f"\n✓ Plot saved to: {output_file}")


def example_realistic_calibration():
    """Example 2: Realistic calibration with noise"""
    print("\n" + "="*60)
    print("Example 2: Realistic Calibration (with noise)")
    print("="*60)

    # Realistic data with some variation
    concentrations = [0.0, 1.0, 2.5, 5.0, 10.0]
    # Add realistic noise
    true_slope = 100
    true_intercept = 5
    areas = [true_slope * c + true_intercept + np.random.normal(0, 5)
             for c in concentrations]
    areas[0] = max(0, areas[0])  # Blank should be ~0

    print("Standard solutions (with measurement variation):")
    for conc, area in zip(concentrations, areas):
        print(f"  {conc:>5.1f} mg/L → Area: {area:>7.2f}")

    # Create curve
    analyzer = QuantitativeAnalyzer()
    curve = analyzer.create_standard_curve(
        concentrations=concentrations,
        areas=areas,
        curve_name="realistic_curve"
    )

    print(f"\n✓ Calibration curve created")
    print(f"  Equation: {curve.equation}")
    print(f"  R²: {curve.r_squared:.6f}")

    # Validate
    is_valid, message = analyzer.validate_curve("realistic_curve", min_r_squared=0.995)
    print(f"\n✓ Validation: {message}")


def example_force_zero():
    """Example 3: Force zero intercept"""
    print("\n" + "="*60)
    print("Example 3: Force Zero Intercept")
    print("="*60)

    # Data with small intercept
    concentrations = [0.0, 1.0, 2.5, 5.0, 10.0]
    areas = [2.5, 102.3, 252.1, 502.8, 1002.5]  # Small intercept ~2.5

    # Compare normal vs force_zero
    analyzer = QuantitativeAnalyzer()

    # Normal regression
    curve_normal = analyzer.create_standard_curve(
        concentrations, areas,
        curve_name="normal",
        force_zero=False
    )

    # Force zero
    curve_forced = analyzer.create_standard_curve(
        concentrations, areas,
        curve_name="forced",
        force_zero=True
    )

    print("Comparison:")
    print(f"\nNormal regression:")
    print(f"  Equation: {curve_normal.equation}")
    print(f"  Slope: {curve_normal.slope:.4f}")
    print(f"  Intercept: {curve_normal.intercept:.4f}")
    print(f"  R²: {curve_normal.r_squared:.6f}")

    print(f"\nForce zero:")
    print(f"  Equation: {curve_forced.equation}")
    print(f"  Slope: {curve_forced.slope:.4f}")
    print(f"  Intercept: {curve_forced.intercept:.4f}")
    print(f"  R²: {curve_forced.r_squared:.6f}")

    # Visualize comparison
    fig, ax = plt.subplots(figsize=(10, 6))

    # Data points
    ax.scatter(concentrations, areas, s=100, c='blue', label='Standard Points', zorder=3)

    # Both lines
    conc_range = np.linspace(0, max(concentrations) * 1.1, 100)

    pred_normal = curve_normal.slope * conc_range + curve_normal.intercept
    ax.plot(conc_range, pred_normal, 'r--', linewidth=2,
            label=f'Normal (R²={curve_normal.r_squared:.6f})')

    pred_forced = curve_forced.slope * conc_range + curve_forced.intercept
    ax.plot(conc_range, pred_forced, 'g--', linewidth=2,
            label=f'Force Zero (R²={curve_forced.r_squared:.6f})')

    ax.set_xlabel('Concentration (mg/L)', fontsize=12)
    ax.set_ylabel('Peak Area', fontsize=12)
    ax.set_title('Normal vs Force Zero Calibration', fontsize=14, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    output_file = Path(__file__).parent / "calibration_comparison.png"
    plt.tight_layout()
    plt.savefig(output_file, dpi=300)
    print(f"\n✓ Comparison plot saved to: {output_file}")


def example_concentration_calculation():
    """Example 4: Calculate sample concentrations"""
    print("\n" + "="*60)
    print("Example 4: Sample Concentration Calculation")
    print("="*60)

    # Create calibration curve
    analyzer = QuantitativeAnalyzer()
    concentrations = [0.0, 1.0, 2.5, 5.0, 10.0]
    areas = [0.0, 100.0, 250.0, 500.0, 1000.0]

    curve = analyzer.create_standard_curve(concentrations, areas)
    print(f"Calibration: {curve.equation}, R² = {curve.r_squared:.6f}")

    # Sample measurements
    samples = [
        ("Sample 1", 125.5, 1.0),   # area, dilution
        ("Sample 2", 378.2, 5.0),
        ("Sample 3", 756.8, 10.0),
        ("Sample 4", 234.1, 2.0),
        ("Sample 5", 892.3, 10.0)
    ]

    print("\nSample analysis:")
    print(f"{'Sample':<12} {'Area':>8} {'Dilution':>10} {'Conc (mg/L)':>15}")
    print("-" * 50)

    for name, area, dilution in samples:
        conc = analyzer.calculate_concentration(
            area=area,
            dilution_factor=dilution
        )
        print(f"{name:<12} {area:>8.1f} {dilution:>9.0f}x {conc:>14.4f}")


def example_batch_quantification():
    """Example 5: Batch quantification"""
    print("\n" + "="*60)
    print("Example 5: Batch Quantification")
    print("="*60)

    # Calibration
    analyzer = QuantitativeAnalyzer()
    concentrations = [0.0, 1.0, 2.5, 5.0, 10.0]
    areas = [0.0, 100.0, 250.0, 500.0, 1000.0]
    analyzer.create_standard_curve(concentrations, areas, curve_name="batch_curve")

    print(f"✓ Calibration curve created")

    # Batch samples
    sample_areas = [145.2, 312.8, 678.5, 189.3, 923.1, 456.7, 234.5, 789.2]
    sample_names = [f"S{i+1}" for i in range(len(sample_areas))]
    dilution_factors = [1, 5, 10, 2, 10, 5, 2, 10]

    # Batch calculation
    results = analyzer.calculate_batch_concentrations(
        areas=sample_areas,
        dilution_factors=dilution_factors,
        sample_names=sample_names,
        curve_name="batch_curve"
    )

    print(f"\n✓ Batch quantification completed ({len(results)} samples)")
    print(f"\n{'Sample':<8} {'Area':>8} {'Dil':>5} {'Conc (mg/L)':>12}")
    print("-" * 38)

    for r in results:
        print(f"{r['sample_name']:<8} {r['area']:>8.1f} "
              f"{r['dilution_factor']:>4.0f}x {r['concentration']:>12.4f}")


def example_lod_loq():
    """Example 6: LOD and LOQ calculation"""
    print("\n" + "="*60)
    print("Example 6: LOD and LOQ Calculation")
    print("="*60)

    # Calibration curve
    analyzer = QuantitativeAnalyzer()
    concentrations = [0.0, 0.1, 0.5, 1.0, 5.0, 10.0]  # Low concentration range
    areas = [2.1, 12.3, 52.5, 102.8, 502.3, 1002.9]

    curve = analyzer.create_standard_curve(concentrations, areas, curve_name="lod_curve")
    print(f"Calibration: {curve.equation}")
    print(f"R²: {curve.r_squared:.6f}")

    # Calculate LOD and LOQ
    lod = analyzer.get_lod_loq(curve_name="lod_curve", confidence=3.3)
    loq = analyzer.get_lod_loq(curve_name="lod_curve", confidence=10)

    print(f"\n✓ Detection limits:")
    print(f"  LOD (3.3σ): {lod:.6f} mg/L")
    print(f"  LOQ (10σ): {loq:.6f} mg/L")

    # Test samples at different levels
    test_samples = [
        ("Below LOD", lod * 0.5),
        ("Between LOD-LOQ", (lod + loq) / 2),
        ("Above LOQ", loq * 2)
    ]

    print(f"\nSample interpretation:")
    for name, conc in test_samples:
        if conc < lod:
            status = "Not Detected (< LOD)"
        elif conc < loq:
            status = "Detected but < LOQ (not quantifiable)"
        else:
            status = "Quantifiable"

        print(f"  {name}: {conc:.6f} mg/L → {status}")


def example_save_load_curve():
    """Example 7: Save and load calibration curve"""
    print("\n" + "="*60)
    print("Example 7: Save and Load Calibration Curve")
    print("="*60)

    # Create curve
    analyzer1 = QuantitativeAnalyzer()
    concentrations = [0.0, 1.0, 2.5, 5.0, 10.0]
    areas = [0.0, 100.0, 250.0, 500.0, 1000.0]

    curve = analyzer1.create_standard_curve(
        concentrations, areas,
        curve_name="saved_curve"
    )

    print(f"✓ Created curve: {curve.equation}")

    # Save to file
    save_dir = Path(__file__).parent.parent / "test_results"
    save_dir.mkdir(exist_ok=True)
    save_path = save_dir / "example_calibration_curve.json"

    analyzer1.save_curve("saved_curve", str(save_path))
    print(f"✓ Saved to: {save_path}")

    # Load in new analyzer
    analyzer2 = QuantitativeAnalyzer()
    loaded_name = analyzer2.load_curve(str(save_path))

    print(f"✓ Loaded as: {loaded_name}")

    # Verify it works
    test_area = 375.0
    conc1 = analyzer1.calculate_concentration(test_area, curve_name="saved_curve")
    conc2 = analyzer2.calculate_concentration(test_area, curve_name=loaded_name)

    print(f"\nVerification (area={test_area}):")
    print(f"  Original: {conc1:.4f} mg/L")
    print(f"  Loaded: {conc2:.4f} mg/L")
    print(f"  Match: {abs(conc1 - conc2) < 0.0001}")


def example_quadratic_curve():
    """Example 8: Quadratic calibration for wide range"""
    print("\n" + "="*60)
    print("Example 8: Quadratic Calibration (Wide Range)")
    print("="*60)

    # Wide concentration range with nonlinear response
    concentrations = [0.0, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0]
    # Simulated nonlinear detector response
    areas = [0, 48, 95, 450, 850, 3500, 6200]

    analyzer = QuantitativeAnalyzer()

    # Try linear first
    curve_linear = analyzer.create_standard_curve(
        concentrations, areas,
        curve_name="linear_wide",
        method="linear"
    )

    # Then quadratic
    curve_quad = analyzer.create_standard_curve(
        concentrations, areas,
        curve_name="quadratic_wide",
        method="quadratic"
    )

    print("Comparison for wide range:")
    print(f"\nLinear:")
    print(f"  Equation: {curve_linear.equation}")
    print(f"  R²: {curve_linear.r_squared:.6f}")

    print(f"\nQuadratic:")
    print(f"  Equation: {curve_quad.equation}")
    print(f"  R²: {curve_quad.r_squared:.6f}")

    # Visualize
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Full range
    ax1.scatter(concentrations, areas, s=100, c='blue', label='Data', zorder=3)

    conc_range = np.linspace(0, max(concentrations), 200)

    # Linear prediction
    pred_linear = curve_linear.slope * conc_range + curve_linear.intercept
    ax1.plot(conc_range, pred_linear, 'r--', linewidth=2,
             label=f'Linear (R²={curve_linear.r_squared:.4f})')

    # Quadratic prediction (recompute coefficients from standards)
    std_concs = [s.concentration for s in curve_quad.standards]
    std_areas = [s.area for s in curve_quad.standards]
    quad_coeffs = np.polyfit(std_concs, std_areas, 2)
    pred_quad = np.polyval(quad_coeffs, conc_range)
    ax1.plot(conc_range, pred_quad, 'g--', linewidth=2,
             label=f'Quadratic (R²={curve_quad.r_squared:.4f})')

    ax1.set_xlabel('Concentration (mg/L)', fontsize=12)
    ax1.set_ylabel('Peak Area', fontsize=12)
    ax1.set_title('Full Range Comparison', fontsize=13, fontweight='bold')
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.3)

    # Low range zoom
    low_concs = [c for c in concentrations if c <= 10]
    low_areas = [areas[i] for i, c in enumerate(concentrations) if c <= 10]

    ax2.scatter(low_concs, low_areas, s=100, c='blue', label='Data', zorder=3)

    conc_range_low = np.linspace(0, 10, 100)
    pred_linear_low = curve_linear.slope * conc_range_low + curve_linear.intercept
    ax2.plot(conc_range_low, pred_linear_low, 'r--', linewidth=2, label='Linear')

    pred_quad_low = np.polyval(quad_coeffs, conc_range_low)
    ax2.plot(conc_range_low, pred_quad_low, 'g--', linewidth=2, label='Quadratic')

    ax2.set_xlabel('Concentration (mg/L)', fontsize=12)
    ax2.set_ylabel('Peak Area', fontsize=12)
    ax2.set_title('Low Range Detail (0-10 mg/L)', fontsize=13, fontweight='bold')
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    output_file = Path(__file__).parent / "quadratic_calibration.png"
    plt.savefig(output_file, dpi=300)
    print(f"\n✓ Comparison plot saved to: {output_file}")


def main():
    """Run all examples"""
    print("\n" + "="*70)
    print("QUANTITATIVE ANALYSIS EXAMPLES")
    print("="*70)

    example_basic_calibration()
    example_realistic_calibration()
    example_force_zero()
    example_concentration_calculation()
    example_batch_quantification()
    example_lod_loq()
    example_save_load_curve()
    example_quadratic_curve()

    print("\n" + "="*70)
    print("All examples completed!")
    print("Check the examples/ directory for generated plots")
    print("Check the ../test_results/ directory for saved curves")
    print("="*70)


if __name__ == "__main__":
    main()
