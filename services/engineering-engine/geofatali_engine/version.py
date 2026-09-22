"""Engine version, stamped onto every calculation record.

Bump this whenever a formula, a default, or a correction factor changes. A
stored calculation is only reproducible if the version that produced it is
known, so this string is written into every result and every report.
"""

ENGINE_VERSION = "0.1.0"
