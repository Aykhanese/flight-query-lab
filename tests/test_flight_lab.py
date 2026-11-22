"""Self-contained tests exercising published lab requirements (not official tests)."""

import contextlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest

import flight_parser
from csv_loader import parse_files
from query import run_query, run_queries
from validator import load_airports, validate_row, to_record


AIRPORTS = {"RIX", "LHR", "JFK", "OSL", "FRA", "HEL", "AMS"}
ROW = [" BA2490 ", " LHR ", " JFK ", "2025-11-14 10:30", "2025-11-14 13:05", " 489.99 "]
HEADER = "flight_id,origin,destination,departure_datetime,arrival_datetime,price\n"


class ValidatorTests(unittest.TestCase):
    def check_code(self, index, value, expected):
        row = ROW.copy()
        row[index] = value
        self.assertEqual(validate_row(row, AIRPORTS), expected)

    def test_all_validation_codes(self):
        self.assertIsNone(validate_row(ROW, AIRPORTS))
        self.assertEqual(validate_row(ROW[:-1], AIRPORTS), "WRONG_FIELD_COUNT")
        self.check_code(0, " ", "MISSING_FIELD")
        self.check_code(0, "AB_1", "INVALID_FLIGHT_ID")
        self.check_code(0, "ĀB", "INVALID_FLIGHT_ID")
        self.check_code(0, "A", "INVALID_FLIGHT_ID")
        self.check_code(0, "ABCDEFGH9", "INVALID_FLIGHT_ID")
        self.check_code(1, "rix", "INVALID_ORIGIN")
        self.check_code(1, "ZZZ", "INVALID_ORIGIN")
        self.check_code(2, "JFKK", "INVALID_DESTINATION")
        self.check_code(2, "ĀBC", "INVALID_DESTINATION")
        self.check_code(2, "LHR", "SAME_ORIGIN_DESTINATION")
        self.check_code(3, "2025-1-14 10:30", "INVALID_DEPARTURE")
        self.check_code(3, "2025-02-29 10:30", "INVALID_DEPARTURE")
        self.check_code(3, "2025-11-14T10:30", "INVALID_DEPARTURE")
        self.check_code(4, "2025-11-14 24:00", "INVALID_ARRIVAL")
        self.check_code(4, "2025-11-14 10:30", "ARRIVAL_NOT_AFTER_DEPARTURE")
        self.check_code(4, "2025-11-14 10:29", "ARRIVAL_NOT_AFTER_DEPARTURE")
        self.check_code(5, "nan", "INVALID_PRICE")
        self.check_code(5, "inf", "INVALID_PRICE")
        self.check_code(5, "abc", "INVALID_PRICE")
        self.check_code(5, "0", "NON_POSITIVE_PRICE")
        self.check_code(5, "-0.1", "NON_POSITIVE_PRICE")

    def test_first_error_wins(self):
        row = ["bad_id", "XYZ", "", "not-date", "not-date", "NaN"]
        self.assertEqual(validate_row(row, AIRPORTS), "MISSING_FIELD")
        row[2] = "JFK"
        self.assertEqual(validate_row(row, AIRPORTS), "INVALID_FLIGHT_ID")

    def test_record_shape(self):
        record = to_record(ROW)
        self.assertEqual(set(record), {
            "flight_id", "origin", "destination", "departure_datetime",
            "arrival_datetime", "price",
        })
        self.assertEqual(record["flight_id"], "BA2490")
        self.assertEqual(record["price"], 489.99)

    def test_airports_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "airports.txt"
            path.write_text(" # skip\n\n RIX \r\nLHR\nrix\n", encoding="utf8")
            self.assertEqual(load_airports(str(path)), {"RIX", "LHR", "rix"})


class ParsingTests(unittest.TestCase):
    def test_skip_physical_lines_and_duplicate_across_files(self):
        with tempfile.TemporaryDirectory() as folder:
            first, second = Path(folder) / "a.csv", Path(folder) / "b.csv"
            first.write_text(
                HEADER + "\n # Comment\n"
                + " BA2490 , LHR , JFK , 2025-11-14 10:30 , 2025-11-14 13:05 , 489.99 \n"
                + "BADLINE,NO,DATE\n",
                encoding="utf-8", newline="",
            )
            second.write_text(
                HEADER + "BA2490,LHR,JFK,2025-11-14 10:30,2025-11-14 13:05,100\n"
                + "BA2490,LHR,JFK,2025-11-15 10:30,2025-11-15 13:05,100\n",
                encoding="utf-8", newline="",
            )
            records, errors = parse_files([str(first), str(second)], AIRPORTS)
            self.assertEqual(len(records), 2)
            self.assertEqual(errors[0].split(" | ")[0], "a.csv:5: WRONG_FIELD_COUNT")
            self.assertEqual(errors[1].split(" | ")[0], "b.csv:2: DUPLICATE_FLIGHT")


class QueryTests(unittest.TestCase):
    def setUp(self):
        self.db = [
            {"flight_id": "A1", "origin": "RIX", "destination": "LHR",
             "departure_datetime": "2025-11-14 10:30", "arrival_datetime": "2025-11-14 11:30", "price": 200.0},
            {"flight_id": "A2", "origin": "RIX", "destination": "LHR",
             "departure_datetime": "2025-11-15 10:30", "arrival_datetime": "2025-11-15 11:30", "price": 100.0},
            {"flight_id": "A3", "origin": "JFK", "destination": "RIX",
             "departure_datetime": "2025-11-16 10:30", "arrival_datetime": "2025-11-16 11:30", "price": 100.0},
        ]

    def test_query_filters_sort_and_limits(self):
        q = {"origin": "RIX", "min_price": 101, "price": 200}
        self.assertEqual([x["flight_id"] for x in run_query(self.db, q)["matches"]], ["A1"])
        q = {"sort_by": "price", "order": "desc", "limit": 2}
        self.assertEqual([x["flight_id"] for x in run_query(self.db, q)["matches"]], ["A1", "A2"])
        q = {"departure_datetime": "2025-11-15 10:30", "arrival_datetime": "2025-11-15 11:30"}
        self.assertEqual([x["flight_id"] for x in run_query(self.db, q)["matches"]], ["A2"])
        self.assertEqual(len(run_query(self.db, {})["matches"]), 3)
        self.assertEqual(run_query(self.db, {"limit": 0})["matches"], [])

    def test_invalid_queries(self):
        invalid = [
            {"colour": "red"}, {"price": True}, {"min_price": None},
            {"departure_datetime": "2025-1-15 10:30"},
            {"arrival_datetime": "2025-02-29 10:30"},
            {"limit": -1}, {"limit": True}, {"limit": 1.0},
            {"order": "desc"}, {"sort_by": "min_price"},
            {"sort_by": "price", "order": "up"},
        ]
        for q in invalid:
            with self.subTest(query=q):
                response = run_query(self.db, q)
                self.assertEqual(response, {"query": q, "error": "INVALID_QUERY", "matches": []})
        self.assertEqual(len(run_queries(self.db, {})), 1)
        self.assertEqual(len(run_queries(self.db, [{}, {"limit": 1}])), 2)
        for wrong in (1, "abc", [1]):
            with self.assertRaises(ValueError):
                run_queries(self.db, wrong)


class CliTests(unittest.TestCase):
    def test_parse_log_response_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            csv_path = base / "db.csv"
            airport_path = base / "airports.txt"
            query_path = base / "query.json"
            output_path = base / "db.json"
            csv_path.write_text(
                HEADER + "BA2490,LHR,JFK,2025-11-14 10:30,2025-11-14 13:05,489.99\n"
                + "NOPE,RIX,XYZ,2025-11-14 10:30,2025-11-14 13:05,100\n",
                encoding="utf-8",
            )
            airport_path.write_text("LHR\nJFK\nRIX\n", encoding="utf-8")
            query_path.write_text('[{"destination": "JFK"}, {"limit": -1}]', encoding="utf-8")
            arguments = ["-i", str(csv_path), "-a", str(airport_path), "-o", str(output_path), "-q", str(query_path), "-r", folder]
            self.assertEqual(flight_parser.main(arguments), 0)
            self.assertEqual(len(json.loads(output_path.read_text(encoding="utf-8"))), 1)
            warnings = [line for line in (base / "errors.log").read_text(encoding="utf-8").splitlines() if " WARNING " in line]
            self.assertEqual(len(warnings), 1)
            self.assertIn("db.csv:3: INVALID_DESTINATION |", warnings[0])
            response_files = list(base.glob("response_*.json"))
            self.assertEqual(len(response_files), 1)
            self.assertRegex(response_files[0].name, r"^response_251ADC004_Aykhan_Asadov_\d{8}_\d{4}\.json$")
            response = json.loads(response_files[0].read_text(encoding="utf-8"))
            self.assertEqual(len(response[0]["matches"]), 1)
            self.assertEqual(response[1]["error"], "INVALID_QUERY")

            # A second invocation must not retain the previous FileHandler.
            self.assertEqual(flight_parser.main(arguments), 0)
            warnings = [line for line in (base / "errors.log").read_text(encoding="utf-8").splitlines() if " WARNING " in line]
            self.assertEqual(len(warnings), 1)

            self.assertEqual(flight_parser.main(["-j", str(output_path), "-q", str(query_path), "-r", folder]), 0)

    def test_cli_usage_and_runtime_errors(self):
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(flight_parser.main([]), 2)
            self.assertEqual(flight_parser.main(["-i", "x.csv"]), 2)
            self.assertEqual(flight_parser.main(["-i", "x.csv", "-j", "x.json"]), 2)
            self.assertEqual(flight_parser.main(["-j", "x.json", "-o", "out.json"]), 2)
            self.assertEqual(flight_parser.main(["-j", "missing.json"]), 1)
            self.assertEqual(flight_parser.main(["--help"]), 0)

    def test_folder_sorted(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            airport_path = base / "airports.txt"
            airport_path.write_text("RIX\nJFK\nLHR\n", encoding="utf-8")
            csv_dir = base / "input"
            csv_dir.mkdir()
            (csv_dir / "b.csv").write_text(HEADER + "B1,RIX,JFK,2025-11-15 10:30,2025-11-15 13:05,100\n", encoding="utf-8")
            (csv_dir / "a.csv").write_text(HEADER + "A1,LHR,JFK,2025-11-15 10:30,2025-11-15 13:05,100\n", encoding="utf-8")
            (csv_dir / "c.CSV").write_text(HEADER + "C1,LHR,JFK,2025-11-15 10:30,2025-11-15 13:05,100\n", encoding="utf-8")
            out = base / "output.json"
            self.assertEqual(flight_parser.main(["-d", str(csv_dir), "-a", str(airport_path), "-o", str(out)]), 0)
            db = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual([x["flight_id"] for x in db], ["A1", "B1"])


if __name__ == "__main__":
    unittest.main()
