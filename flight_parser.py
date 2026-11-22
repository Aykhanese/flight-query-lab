"""Command-line entry point for the flight schedule query lab."""

import argparse
from datetime import datetime
import json
import logging
from pathlib import Path
import sys

from csv_loader import parse_files
from query import run_queries
from validator import load_airports

STUDENT_ID = "251ADC004"
FIRST_NAME = "Aykhan"
LAST_NAME = "Asadov"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and query flight schedules")
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument("-i", metavar="FILE", help="input CSV file")
    sources.add_argument("-d", metavar="FOLDER", help="directory of CSV files")
    sources.add_argument("-j", metavar="FILE", help="existing JSON database")
    parser.add_argument("-a", metavar="FILE", help="airport code list")
    parser.add_argument("-o", metavar="FILE", help="output database path")
    parser.add_argument("-q", metavar="FILE", help="query JSON file")
    parser.add_argument("-r", metavar="FOLDER", default=".", help="response folder")
    return parser


def _write_json(path: Path, data: object) -> None:
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(data, output_file, indent=2, ensure_ascii=False, allow_nan=False)
        output_file.write("\n")


def _read_json(path: str) -> object:
    with open(path, "r", encoding="utf-8") as input_file:
        return json.load(input_file)


def _parse_input(args: argparse.Namespace) -> list[dict]:
    database_path = Path(args.o or "db.json")
    log_path = database_path.parent / "errors.log"

    # Do not use basicConfig: the grader invokes main() repeatedly in a process.
    logger = logging.getLogger("flight_parser")
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(handler)
    try:
        airports = load_airports(args.a)
        if args.i is not None:
            paths = [args.i]
        else:
            directory = Path(args.d)
            paths = [
                str(path) for path in sorted(directory.iterdir())
                if path.is_file() and path.name.endswith(".csv")
            ]
            if not paths:
                raise ValueError("no .csv files found in the input folder")

        records, errors = parse_files(paths, airports)
        for error in errors:
            logger.warning(error)
        _write_json(database_path, records)
        return records
    finally:
        logger.removeHandler(handler)
        handler.close()


def main(argv: list[str] | None = None) -> int:
    """Run the program and return 0, 1 or 2 without raising SystemExit."""
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        if args.j is None and args.a is None:
            parser.error("-a is required with -i and -d")
        if args.j is not None and args.o is not None:
            parser.error("-o cannot be used with -j")
    except SystemExit as exc:  # argparse convention (help = 0, misuse = 2)
        return int(exc.code)

    try:
        if args.j is not None:
            database = _read_json(args.j)
            if not isinstance(database, list) or any(
                not isinstance(record, dict) for record in database
            ):
                raise ValueError("JSON database must be an array of objects")
        else:
            database = _parse_input(args)

        if args.q is not None:
            queries = _read_json(args.q)
            responses = run_queries(database, queries)
            name = (
                f"response_{STUDENT_ID}_{FIRST_NAME}_{LAST_NAME}_"
                f"{datetime.now().strftime('%Y%m%d_%H%M')}.json"
            )
            _write_json(Path(args.r) / name, responses)
        return 0
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
