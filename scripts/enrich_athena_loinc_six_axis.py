"""LOINC six-axis recovery from Athena CONCEPT_RELATIONSHIP edges.

The Athena distribution flattens LOINC into one CONCEPT.csv row per LOINC
term with a name and concept_class_id, but the six-axis structure
(Component / Property / Time / System / Scale / Method) is encoded in
CONCEPT_RELATIONSHIP edges:

    LOINC concept --[Has component]--> LOINC Part (Component)
    LOINC concept --[Has property]--> LOINC Part (Property)
    ...

Theme 6 Omics anchors need flat six-axis fields per LOINC code, not a graph
walk. This script reconstructs the axes via a DuckDB SQL join and emits a
lookup parquet that the Tuesday dedup pass joins back onto LOINC rows.

Usage:
    python scripts/enrich_athena_loinc_six_axis.py \\
        --athena-dir data/sources/athena/v20260227 \\
        --out data/foundation/staging/loinc_six_axis.parquet

The script auto-discovers CONCEPT.csv and CONCEPT_RELATIONSHIP.csv under
the Athena dir and accepts either tab-delimited (Athena default) or CSV
formats.

Dependencies: duckdb >= 0.9
    pip install duckdb
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("loinc_six_axis")


# DuckDB SQL — single query with two CTEs and a pivot.
# Reads tab-delimited CSVs directly without loading them into Python.
SIX_AXIS_SQL = """
WITH parts AS (
    SELECT
        concept_id,
        concept_name,
        concept_class_id
    FROM read_csv_auto(
        ?, delim=?, header=true,
        ignore_errors=true
    )
    WHERE vocabulary_id = 'LOINC'
      AND concept_class_id IN (
          'Component', 'Property', 'Time', 'System', 'Scale', 'Method',
          'LOINC Component', 'LOINC Property', 'LOINC Time', 'LOINC System',
          'LOINC Scale', 'LOINC Method'
      )
),
loinc_concepts AS (
    SELECT concept_id, concept_code, concept_name
    FROM read_csv_auto(
        ?, delim=?, header=true,
        ignore_errors=true
    )
    WHERE vocabulary_id = 'LOINC'
      AND (standard_concept = 'S' OR standard_concept IS NULL)
),
edges AS (
    SELECT concept_id_1, concept_id_2, relationship_id
    FROM read_csv_auto(
        ?, delim=?, header=true,
        ignore_errors=true
    )
    WHERE relationship_id IN (
        'Has component', 'Has property', 'Has time aspect',
        'Has system', 'Has scale type', 'Has method type',
        'Has time', 'Has scale', 'Has method'
    )
      AND (invalid_reason IS NULL OR invalid_reason = '')
)
SELECT
    lc.concept_id      AS omop_concept_id,
    lc.concept_code    AS loinc_code,
    lc.concept_name    AS loinc_long_name,
    MAX(CASE WHEN e.relationship_id IN ('Has component')
             THEN p.concept_name END)              AS axis_component,
    MAX(CASE WHEN e.relationship_id IN ('Has property')
             THEN p.concept_name END)              AS axis_property,
    MAX(CASE WHEN e.relationship_id IN ('Has time', 'Has time aspect')
             THEN p.concept_name END)              AS axis_time,
    MAX(CASE WHEN e.relationship_id IN ('Has system')
             THEN p.concept_name END)              AS axis_system,
    MAX(CASE WHEN e.relationship_id IN ('Has scale', 'Has scale type')
             THEN p.concept_name END)              AS axis_scale,
    MAX(CASE WHEN e.relationship_id IN ('Has method', 'Has method type')
             THEN p.concept_name END)              AS axis_method
FROM loinc_concepts lc
LEFT JOIN edges e ON e.concept_id_1 = lc.concept_id
LEFT JOIN parts p ON p.concept_id = e.concept_id_2
GROUP BY lc.concept_id, lc.concept_code, lc.concept_name
"""


def run_six_axis_recovery(
    athena_dir: Path,
    out_path: Path,
) -> int:
    """Execute the six-axis recovery query and write parquet output.

    Returns the number of LOINC concepts in the output (one row per).
    """
    try:
        import duckdb
    except ImportError:
        raise SystemExit(
            "duckdb is required for six-axis recovery. Install: pip install duckdb"
        )

    athena_dir = Path(athena_dir)
    concept_csv = athena_dir / "CONCEPT.csv"
    rel_csv = athena_dir / "CONCEPT_RELATIONSHIP.csv"

    if not concept_csv.exists():
        raise FileNotFoundError(f"CONCEPT.csv not found at {concept_csv}")
    if not rel_csv.exists():
        raise FileNotFoundError(f"CONCEPT_RELATIONSHIP.csv not found at {rel_csv}")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    logger.info("Reading CONCEPT.csv from %s", concept_csv)
    logger.info("Reading CONCEPT_RELATIONSHIP.csv from %s", rel_csv)
    logger.info("Output: %s", out_path)

    con = duckdb.connect(":memory:")
    # Allocate sensibly — Athena CSVs can be large
    con.execute("SET memory_limit='8GB'")
    con.execute("SET threads=4")

    # Sniff delimiters — newer Athena releases (post-2025) use comma,
    # older releases used tab. Header inspection reliably detects.
    def _sniff(p: Path) -> str:
        with p.open(encoding="utf-8", errors="replace") as f:
            first = f.readline()
        return "\t" if first.count("\t") >= first.count(",") else ","
    concept_delim = _sniff(concept_csv)
    rel_delim = _sniff(rel_csv)
    logger.info("CONCEPT.csv delimiter: %s, CONCEPT_RELATIONSHIP.csv delimiter: %s",
                "tab" if concept_delim == "\t" else "comma",
                "tab" if rel_delim == "\t" else "comma")

    # Same CONCEPT.csv is read twice (parts + loinc_concepts), once
    # CONCEPT_RELATIONSHIP.csv. Pass file paths and delimiters in pairs
    # matching the SQL placeholder order.
    result = con.execute(
        SIX_AXIS_SQL,
        [
            str(concept_csv), concept_delim,
            str(concept_csv), concept_delim,
            str(rel_csv), rel_delim,
        ],
    )

    # Stream to parquet — avoids materializing in memory
    import pyarrow.parquet as pq
    arrow_reader = result.fetch_record_batch()
    arrow_table = arrow_reader.read_all()
    n_rows = arrow_table.num_rows
    pq.write_table(arrow_table, out_path, compression="snappy")

    elapsed = time.time() - t0
    logger.info(
        "Wrote %d LOINC six-axis rows to %s in %.1fs",
        n_rows, out_path, elapsed,
    )

    # Quick sanity report
    con.execute("CREATE TABLE result AS SELECT * FROM read_parquet(?)",
                [str(out_path)])
    pop_stats = con.execute("""
        SELECT
            SUM(CASE WHEN axis_component IS NOT NULL THEN 1 ELSE 0 END) AS has_component,
            SUM(CASE WHEN axis_property  IS NOT NULL THEN 1 ELSE 0 END) AS has_property,
            SUM(CASE WHEN axis_time      IS NOT NULL THEN 1 ELSE 0 END) AS has_time,
            SUM(CASE WHEN axis_system    IS NOT NULL THEN 1 ELSE 0 END) AS has_system,
            SUM(CASE WHEN axis_scale     IS NOT NULL THEN 1 ELSE 0 END) AS has_scale,
            SUM(CASE WHEN axis_method    IS NOT NULL THEN 1 ELSE 0 END) AS has_method,
            COUNT(*) AS total
        FROM result
    """).fetchone()
    logger.info(
        "Axis population: component=%d/%d, property=%d/%d, time=%d/%d, "
        "system=%d/%d, scale=%d/%d, method=%d/%d",
        pop_stats[0], pop_stats[6], pop_stats[1], pop_stats[6],
        pop_stats[2], pop_stats[6], pop_stats[3], pop_stats[6],
        pop_stats[4], pop_stats[6], pop_stats[5], pop_stats[6],
    )

    return n_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--athena-dir", required=True,
                        help="Path to Athena release dir containing "
                             "CONCEPT.csv and CONCEPT_RELATIONSHIP.csv")
    parser.add_argument("--out",
                        default="data/foundation/staging/loinc_six_axis.parquet",
                        help="Output parquet path")
    args = parser.parse_args()
    n = run_six_axis_recovery(Path(args.athena_dir), Path(args.out))
    print(f"Wrote {n} LOINC six-axis rows.")


if __name__ == "__main__":
    main()
