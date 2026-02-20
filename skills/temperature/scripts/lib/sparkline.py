"""Unicode sparkline generator for temperature skill.

Generates compact visual trend representations using Unicode block
characters. Used in dimension tables and compact output format.
"""

# 9 Unicode block characters: index 0 = space (lowest), index 8 = full block
SPARK_BLOCKS = " \u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"


def sparkline(values: list, width: int = 30) -> str:
    """Generate a Unicode sparkline from numeric values.

    Args:
        values: List of numeric values.
        width: Target character width (values compressed if needed).

    Returns:
        String of Unicode block characters representing the trend.
        Empty string if values is empty.
    """
    if not values:
        return ""

    if len(values) == 1:
        return SPARK_BLOCKS[4]  # Mid-height block for single value

    # Compress to target width by averaging buckets
    if len(values) > width:
        bucket_size = len(values) / width
        compressed = []
        for i in range(width):
            start = int(i * bucket_size)
            end = int((i + 1) * bucket_size)
            bucket = values[start:end]
            compressed.append(sum(bucket) / len(bucket))
        values = compressed

    mn = min(values)
    mx = max(values)
    rng = mx - mn

    # Constant values: flat line at mid-height
    if rng == 0:
        return SPARK_BLOCKS[4] * len(values)

    # Map each value to a block character
    chars = []
    for v in values:
        idx = int((v - mn) / rng * 8)
        idx = min(8, max(0, idx))
        chars.append(SPARK_BLOCKS[idx])

    return "".join(chars)
