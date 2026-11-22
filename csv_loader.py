"""Parse flight CSV data while keeping precise physical line numbers."""

import csv
from pathlib import Path

from validator import to_record, validate_row


def parse_files(paths: list[str], airports: set[str]) -> tuple[list[dict], list[str]]:
    """Return valid flights and one error message for each invalid CSV row.

    Files are read in the supplied order. Duplicates are detected across ALL files
    and only among rows that passed regular validation.
    """
    records: list[dict] = []
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()

    for path in paths:
        filename = Path(path).name
        with open(path, "r", encoding="utf-8", newline="") as input_file:
            for line_number, raw_line in enumerate(input_file, start=1):
                if line_number == 1:  # The header is always the first line.
                    continue
                if not raw_line.strip() or raw_line.lstrip().startswith("#"):
                    continue

                # CSV handles quoted fields and embedded commas correctly.
                fields = next(csv.reader([raw_line]))
                error = validate_row(fields, airports)
                if error is None:
                    stripped = [field.strip() for field in fields]
                    key = (stripped[0], stripped[3])
                    if key in seen:
                        error = "DUPLICATE_FLIGHT"
                    else:
                        seen.add(key)
                        records.append(to_record(stripped))

                if error is not None:
                    original_line = raw_line.rstrip("\r\n")
                    errors.append(
                        f"{filename}:{line_number}: {error} | {original_line}"
                    )

    return records, errors
