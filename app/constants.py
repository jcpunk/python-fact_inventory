"""
Size limits used across the fact_inventory application.

All values are in bytes.  They are centralised here so that related
limits (per-field validator, controller body cap) stay in sync and
can be found without hunting through business-logic code.
"""

# Maximum number of bytes allowed for a single JSON field
# (system_facts or package_facts).  Validated before the record is
# written to the database to avoid storing extremely large blobs.
MAX_JSON_FIELD_BYTES: int = 1024 * 1024 * 4  # 4 MiB - educated guess

# Maximum number of bytes Litestar will read from the raw request body
# before rejecting the upload.  Must be larger than two MAX_JSON_FIELD_BYTES
# combined to leave room for the surrounding JSON envelope.
MAX_REQUEST_BODY_BYTES: int = 1024 * 1024 * 9  # 9 MiB
