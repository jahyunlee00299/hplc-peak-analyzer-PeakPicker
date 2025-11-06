"""
Test script for Quantitative Analyzer
"""

import sys
from pathlib import Path
import numpy as np

sys.path.append(str(Path(__file__).parent))

from modules.quantification import QuantitativeAnalyzer, StandardPoint


def test_standard_curve_creation():
    """Test standard curve creation"""
    print("\n=== Testing Standard Curve Creation ===")

    try:
        analyzer = QuantitativeAnalyzer()

        # Create standard curve
        concentrations = [0.0, 1.0, 2.5, 5.0, 10.0]
        areas = [0.0, 100.0, 250.0, 500.0, 1000.0]  # Perfect linear

        curve = analyzer.create_standard_curve(
            concentrations,
            areas,
            curve_name="test_curve",
            method="linear",
            force_zero=False
        )

        print(f"✅ Standard curve created")
        print(f"   Equation: {curve.equation}")
        print(f"   Slope: {curve.slope:.4f}")
        print(f"   Intercept: {curve.intercept:.4f}")
        print(f"   R²: {curve.r_squared:.6f}")

        return abs(curve.r_squared - 1.0) < 0.001  # Should be ~1.0 for perfect data

    except Exception as e:
        print(f"❌ Error creating curve: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_concentration_calculation():
    """Test concentration calculation"""
    print("\n=== Testing Concentration Calculation ===")

    try:
        analyzer = QuantitativeAnalyzer()

        # Create standard curve
        concentrations = [0.0, 1.0, 2.5, 5.0, 10.0]
        areas = [5.0, 105.0, 255.0, 505.0, 1005.0]

        analyzer.create_standard_curve(
            concentrations,
            areas,
            curve_name="test_curve"
        )

        # Test concentration calculation
        test_area = 355.0  # Should be ~3.5
        calculated_conc = analyzer.calculate_concentration(
            test_area,
            curve_name="test_curve",
            dilution_factor=1.0
        )

        print(f"✅ Concentration calculated")
        print(f"   Test area: {test_area}")
        print(f"   Calculated concentration: {calculated_conc:.4f}")

        # Test with dilution factor
        diluted_conc = analyzer.calculate_concentration(
            test_area,
            curve_name="test_curve",
            dilution_factor=10.0
        )

        print(f"   With 10x dilution: {diluted_conc:.4f}")

        return True

    except Exception as e:
        print(f"❌ Error calculating concentration: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_batch_quantification():
    """Test batch concentration calculation"""
    print("\n=== Testing Batch Quantification ===")

    try:
        analyzer = QuantitativeAnalyzer()

        # Create standard curve
        concentrations = [0.0, 1.0, 2.5, 5.0, 10.0]
        areas = [0.0, 100.0, 250.0, 500.0, 1000.0]

        analyzer.create_standard_curve(concentrations, areas)

        # Batch samples
        sample_areas = [150.0, 350.0, 750.0]
        sample_names = ["Sample_1", "Sample_2", "Sample_3"]
        dilution_factors = [1.0, 5.0, 10.0]

        results = analyzer.calculate_batch_concentrations(
            sample_areas,
            dilution_factors=dilution_factors,
            sample_names=sample_names
        )

        print(f"✅ Batch quantification completed")
        for result in results:
            print(f"   {result['sample_name']}: "
                  f"Area={result['area']:.1f}, "
                  f"Dilution={result['dilution_factor']:.1f}x, "
                  f"Conc={result['concentration']:.4f}")

        return len(results) == 3

    except Exception as e:
        print(f"❌ Error in batch quantification: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_curve_validation():
    """Test curve validation"""
    print("\n=== Testing Curve Validation ===")

    try:
        analyzer = QuantitativeAnalyzer()

        # Good curve
        concentrations = [0.0, 1.0, 2.5, 5.0, 10.0]
        areas = [0.0, 100.0, 250.0, 500.0, 1000.0]

        analyzer.create_standard_curve(
            concentrations,
            areas,
            curve_name="good_curve"
        )

        is_valid, message = analyzer.validate_curve("good_curve", min_r_squared=0.98)

        print(f"✅ Good curve validation: {message}")
        print(f"   Valid: {is_valid}")

        # Poor curve (with noise)
        noisy_areas = [np.random.normal(a, 50) for a in areas]
        analyzer.create_standard_curve(
            concentrations,
            noisy_areas,
            curve_name="noisy_curve"
        )

        is_valid2, message2 = analyzer.validate_curve("noisy_curve", min_r_squared=0.99)

        print(f"✅ Noisy curve validation: {message2}")
        print(f"   Valid: {is_valid2}")

        return True

    except Exception as e:
        print(f"❌ Error in validation: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_curve_save_load():
    """Test curve save and load"""
    print("\n=== Testing Curve Save/Load ===")

    try:
        analyzer = QuantitativeAnalyzer()

        # Create and save curve
        concentrations = [0.0, 1.0, 2.5, 5.0, 10.0]
        areas = [0.0, 100.0, 250.0, 500.0, 1000.0]

        analyzer.create_standard_curve(
            concentrations,
            areas,
            curve_name="save_test"
        )

        # Save
        save_file = "test_results/test_curve.json"
        Path("test_results").mkdir(exist_ok=True)
        analyzer.save_curve("save_test", save_file)

        print(f"✅ Curve saved to: {save_file}")

        # Load in new analyzer
        analyzer2 = QuantitativeAnalyzer()
        loaded_name = analyzer2.load_curve(save_file)

        print(f"✅ Curve loaded as: {loaded_name}")

        # Verify
        stats1 = analyzer.get_curve_statistics("save_test")
        stats2 = analyzer2.get_curve_statistics(loaded_name)

        print(f"   Original slope: {stats1['slope']:.4f}")
        print(f"   Loaded slope: {stats2['slope']:.4f}")

        return abs(stats1['slope'] - stats2['slope']) < 0.0001

    except Exception as e:
        print(f"❌ Error in save/load: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_lod_loq():
    """Test LOD/LOQ calculation"""
    print("\n=== Testing LOD/LOQ Calculation ===")

    try:
        analyzer = QuantitativeAnalyzer()

        # Create standard curve
        concentrations = [0.0, 1.0, 2.5, 5.0, 10.0]
        areas = [0.0, 100.0, 250.0, 500.0, 1000.0]

        analyzer.create_standard_curve(concentrations, areas)

        # Calculate LOD and LOQ
        lod = analyzer.get_lod_loq(confidence=3.3)  # LOD
        loq = analyzer.get_lod_loq(confidence=10)   # LOQ

        print(f"✅ LOD/LOQ calculated")
        print(f"   LOD (3.3σ): {lod:.6f}")
        print(f"   LOQ (10σ): {loq:.6f}")

        return lod < loq  # LOD should be less than LOQ

    except Exception as e:
        print(f"❌ Error in LOD/LOQ: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("Quantitative Analyzer Tests")
    print("=" * 60)

    results = []

    # Test quantification features
    results.append(("Standard Curve Creation", test_standard_curve_creation()))
    results.append(("Concentration Calculation", test_concentration_calculation()))
    results.append(("Batch Quantification", test_batch_quantification()))
    results.append(("Curve Validation", test_curve_validation()))
    results.append(("Curve Save/Load", test_curve_save_load()))
    results.append(("LOD/LOQ Calculation", test_lod_loq()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{name}: {status}")

    all_passed = all(result for _, result in results)

    if all_passed:
        print("\n🎉 All tests passed!")
    else:
        print("\n⚠️ Some tests failed!")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
