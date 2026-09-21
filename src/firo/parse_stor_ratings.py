# -*- coding: utf-8 -*-
"""
parse_stor_ratings.py

Turn the elevation-storage rating workbook into one CSV per project, so nothing
downstream has to open Excel.

WHY THIS EXISTS
    Every FIRO number is a storage volume, and every observation and every rule
    curve value is an elevation. The rating is the only thing that connects the
    two, and it arrives as a workbook with one tab per project and a block of
    CWMS header comments glued to the bottom of each tab. Parsing that at the
    top of every analysis script is how a datum error gets copied around. This
    parses it once, drops the comment rows, and writes plain two-column CSVs.

    Committing the CSVs rather than the workbook is deliberate: a CSV shows up
    in a pull request diff, and a .xlsx shows up as "file not displayed".

INPUT
    A workbook with one tab per project, each tab holding an "ELEV (FEET)" and
    a "STOR (ACRE-FEET)" column. The Willamette copy is STOR_RATINGS.xlsx,
    pulled from the CWMS rating pages - see the NOTE rows at the bottom of each
    tab for the source URL and the rating's effective dates.

    Pass the path as the first argument, or drop the workbook at
    data/firo/STOR_RATINGS.xlsx and run it with no arguments.

OUTPUT
    data/firo/ratings/<TAB>.csv      elev_ft, stor_af - one row per rating point
    data/firo/ratings/_sources.csv   the NOTE rows, so the provenance survives

USAGE
    cd src\firo ; python parse_stor_ratings.py
    cd src\firo ; python parse_stor_ratings.py "C:\path\to\Some Other Book.xlsx"
"""

import os
import sys

import pandas as pd

WORKBOOK = os.path.join("data", "firo", "STOR_RATINGS.xlsx")
OUT_DIR = os.path.join("data", "firo", "ratings")

ELEV_HEADER = "ELEV (FEET)"
STOR_HEADER = "STOR (ACRE-FEET)"


# ---------------------------------------------------------------------------
def repo_root():
    """Recognise the repository root by its contents, not by a fixed "..\"."""
    here = os.path.dirname(os.path.abspath(__file__))
    while True:
        if all(os.path.isdir(os.path.join(here, d)) for d in ("data", "src")):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            raise SystemExit("Cannot find the repository root above %s"
                             % os.path.dirname(os.path.abspath(__file__)))
        here = parent


def resolve_path(path):
    return path if os.path.isabs(path) else os.path.normpath(
        os.path.join(repo_root(), path))


def parse_tab(frame):
    """Numeric (elev, stor) pairs, plus the trailing NOTE rows kept separately.

    The tabs carry the CWMS rating header as NOTE rows below the data, so a
    naive read gives a column of floats with a tail of strings. Coercing and
    dropping is safer than slicing at a fixed row: the note block is a
    different length on every tab.
    """
    if ELEV_HEADER not in frame.columns or STOR_HEADER not in frame.columns:
        return None, []

    notes = [str(v).strip() for v in frame[STOR_HEADER]
             if isinstance(v, str) and str(v).strip()]

    points = pd.DataFrame({
        "elev_ft": pd.to_numeric(frame[ELEV_HEADER], errors="coerce"),
        "stor_af": pd.to_numeric(frame[STOR_HEADER], errors="coerce"),
    }).dropna()

    # A rating has to be single valued and increasing to be interpolated
    # against. Sorting is cheap insurance; the duplicate drop catches a tab
    # where the same elevation was listed twice by two rating epochs.
    points = points.sort_values("elev_ft").drop_duplicates("elev_ft")
    return points.reset_index(drop=True), notes


def main():
    workbook = resolve_path(sys.argv[1] if len(sys.argv) > 1 else WORKBOOK)
    if not os.path.isfile(workbook):
        raise SystemExit(
            "No rating workbook at %s\n"
            "Drop it there, or pass the path as the first argument." % workbook)

    out_dir = resolve_path(OUT_DIR)
    os.makedirs(out_dir, exist_ok=True)

    book = pd.read_excel(workbook, sheet_name=None)
    sources = []
    written = 0

    for tab, frame in book.items():
        points, notes = parse_tab(frame)
        if points is None or points.empty:
            print("  %-6s skipped - no %s / %s columns"
                  % (tab, ELEV_HEADER, STOR_HEADER))
            continue

        out_csv = os.path.join(out_dir, "%s.csv" % tab)
        points.to_csv(out_csv, index=False)
        written += 1
        print("  %-6s %4d points  %8.1f - %8.1f ft  %10.0f - %10.0f ac-ft"
              % (tab, len(points), points["elev_ft"].iloc[0],
                 points["elev_ft"].iloc[-1], points["stor_af"].iloc[0],
                 points["stor_af"].iloc[-1]))
        sources.extend({"tab": tab, "note": note} for note in notes)

    if sources:
        pd.DataFrame(sources).to_csv(
            os.path.join(out_dir, "_sources.csv"), index=False)

    print("\n%d rating curves written to %s"
          % (written, os.path.relpath(out_dir, repo_root())))


if __name__ == "__main__":
    main()
