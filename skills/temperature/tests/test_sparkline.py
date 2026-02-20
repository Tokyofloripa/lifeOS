"""Tests for temperature skill sparkline module."""

import sys
import unittest
from pathlib import Path

# Match last60days test convention for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.sparkline import SPARK_BLOCKS, sparkline


class TestSparkline(unittest.TestCase):
    """Test sparkline() function."""

    def test_ascending_values(self):
        """10 ascending values produce ascending block characters."""
        values = list(range(1, 11))
        result = sparkline(values)
        self.assertEqual(len(result), 10)
        # First char should be lowest block, last should be highest
        self.assertEqual(result[0], SPARK_BLOCKS[0])
        self.assertEqual(result[-1], SPARK_BLOCKS[8])
        # Characters should be monotonically non-decreasing
        for i in range(len(result) - 1):
            self.assertLessEqual(
                SPARK_BLOCKS.index(result[i]),
                SPARK_BLOCKS.index(result[i + 1]),
                f"Character at index {i} should be <= character at index {i+1}",
            )

    def test_empty_array(self):
        """Empty array returns empty string."""
        result = sparkline([])
        self.assertEqual(result, "")

    def test_single_element(self):
        """Single element returns a single mid-height character."""
        result = sparkline([42])
        self.assertEqual(len(result), 1)
        self.assertEqual(result, SPARK_BLOCKS[4])

    def test_constant_values(self):
        """Constant values return flat line at mid-height."""
        result = sparkline([5.0, 5.0, 5.0, 5.0, 5.0])
        self.assertEqual(len(result), 5)
        self.assertTrue(all(c == SPARK_BLOCKS[4] for c in result))

    def test_compression(self):
        """60 values compressed to 30 characters."""
        values = list(range(60))
        result = sparkline(values, width=30)
        self.assertEqual(len(result), 30)

    def test_negative_values(self):
        """Negative values work correctly (-10 to 10)."""
        values = list(range(-10, 11))
        result = sparkline(values)
        self.assertEqual(len(result), 21)
        # Should still be ascending (min-max normalization handles negatives)
        self.assertEqual(result[0], SPARK_BLOCKS[0])
        self.assertEqual(result[-1], SPARK_BLOCKS[8])

    def test_large_range(self):
        """Large range (0 to 1000000) does not crash."""
        values = [0, 250000, 500000, 750000, 1000000]
        result = sparkline(values)
        self.assertEqual(len(result), 5)
        self.assertEqual(result[0], SPARK_BLOCKS[0])
        self.assertEqual(result[-1], SPARK_BLOCKS[8])

    def test_width_parameter_respected(self):
        """Width parameter controls output length when compression needed."""
        values = list(range(100))
        result_20 = sparkline(values, width=20)
        result_10 = sparkline(values, width=10)
        self.assertEqual(len(result_20), 20)
        self.assertEqual(len(result_10), 10)

    def test_width_not_applied_when_short(self):
        """Width has no effect when values are shorter than width."""
        values = [1, 2, 3, 4, 5]
        result = sparkline(values, width=30)
        self.assertEqual(len(result), 5)

    def test_mixed_positive_negative_with_zero_crossing(self):
        """Mixed positive/negative with zero crossing."""
        values = [-5, -3, -1, 0, 1, 3, 5]
        result = sparkline(values)
        self.assertEqual(len(result), 7)
        # First should be lowest, last should be highest
        self.assertEqual(result[0], SPARK_BLOCKS[0])
        self.assertEqual(result[-1], SPARK_BLOCKS[8])
        # Middle value (0) should be somewhere in between
        mid_idx = SPARK_BLOCKS.index(result[3])
        self.assertTrue(0 < mid_idx < 8)

    def test_descending_values(self):
        """Descending values produce descending block characters."""
        values = list(range(10, 0, -1))
        result = sparkline(values)
        self.assertEqual(len(result), 10)
        self.assertEqual(result[0], SPARK_BLOCKS[8])
        self.assertEqual(result[-1], SPARK_BLOCKS[0])

    def test_two_equal_values(self):
        """Two equal values return flat line."""
        result = sparkline([7.0, 7.0])
        self.assertEqual(len(result), 2)
        self.assertTrue(all(c == SPARK_BLOCKS[4] for c in result))

    def test_float_values(self):
        """Float values work correctly."""
        values = [0.1, 0.5, 0.9, 1.3, 1.7]
        result = sparkline(values)
        self.assertEqual(len(result), 5)
        # Should be ascending
        self.assertEqual(result[0], SPARK_BLOCKS[0])
        self.assertEqual(result[-1], SPARK_BLOCKS[8])

    def test_spark_blocks_constant(self):
        """SPARK_BLOCKS has 9 characters (space + 8 block chars)."""
        self.assertEqual(len(SPARK_BLOCKS), 9)
        self.assertEqual(SPARK_BLOCKS[0], " ")
        self.assertEqual(SPARK_BLOCKS[8], "\u2588")


if __name__ == "__main__":
    unittest.main()
