# Flight query tool — Python graded lab

A Python 3.13 standard-library-only command-line application for validating flight
CSV data and answering queries against its JSON database.

## Files

- `flight_parser.py`: CLI and output files
- `validator.py`: airport loading, row checks, record conversion
- `csv_loader.py`: CSV files and duplicate detection
- `query.py`: filters, ordering, limits, and invalid query detection
- `AI_USAGE.md`: disclosure of AI assistance (complete the conversation URL)

## Usage

From the repository root:

```bash
python flight_parser.py -i data/db.csv -a data/airports.txt
python flight_parser.py -d data/flights -a data/airports.txt -o out/db.json
python flight_parser.py -j out/db.json -q data/query.json -r out
python -m unittest discover -s tests -v
```

The first three commands require the referenced input files/folders to exist.
Importing these modules does not run the program.

## Submission

Submit the GitHub URL of this repository, not the output database. The five
required files belong at the **top level** of the repository.
