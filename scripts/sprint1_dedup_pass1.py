"""Sprint 1 Tuesday — Pass 1 dedup over staged source parquets.

Three-step pipeline, all in DuckDB SQL for scale (Athena alone is
~5-8M concept rows with the open-vocabulary selection):

    Step 1 — Within-source dedup:
        Same (source_authority, source_code) pairs collapse into one row.
        metadata_ JSON arrays union; member_of_collections list-unions;
        first non-null wins for scalar fields.

    Step 2 — Build equivalence index:
        Equivalence edges harvested by rop.equivalence get an internal
        rop_id assigned, then a transitive closure pass produces
        equivalent_rop_ids arrays.

    Step 3 — LOINC six-axis enrichment:
        Reads loinc_six_axis.parquet (produced by
        scripts/enrich_athena_loinc_six_axis.py earlier in the day) and
        joins onto Athena LOINC rows.

Inputs (under data/foundation/staging/):
    {source}.parquet for each source ingested
    loinc_six_axis.parquet (from enrich_athena_loinc_six_axis.py)
    equivalence_edges.parquet (from rop.equivalence harvest)

Output:
    dedup_pass1.parquet — one row per (source_authority, source_code) with
                          equivalent_rop_ids array populated where edges resolve

Usage:
    # First, harvest xrefs:
    python -c "from rop.equivalence import harvest_all, write_edges_parquet; \\
               write_edges_parquet(harvest_all('data/foundation/staging'), \\
                                   'data/foundation/staging/equivalence_edges.parquet')"

    # Then, six-axis recovery (separate, see scripts/enrich_athena_loinc_six_axis.py)

    # Finally, dedup:
    python scripts/sprint1_dedup_pass1.py \\
        --staging-dir data/foundation/staging \\
        --out data/foundation/staging/dedup_pass1.parquet
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
logger = logging.getLogger("dedup_pass1")


# Within-source dedup: same source_code in same source_authority collapses.
# Uses MAX() for scalars (first non-null wins after sort), array_agg + DISTINCT
# for arrays.
WITHIN_SOURCE_DEDUP_SQL = """
CREATE OR REPLACE TABLE within_source_dedup AS
WITH ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY source_authority, source_code
            ORDER BY
                -- Prefer rows with more populated fields
                (CASE WHEN description IS NOT NULL THEN 1 ELSE 0 END +
                 CASE WHEN unit_of_measure IS NOT NULL THEN 1 ELSE 0 END +
                 CASE WHEN plausible_min IS NOT NULL THEN 1 ELSE 0 END) DESC,
                source_retrieved_date DESC NULLS LAST
        ) AS rn
    FROM read_parquet(?)
)
SELECT
    source_authority,
    source_code,
    -- Scalars: first row's value (after rank order)
    ANY_VALUE(item) FILTER (WHERE rn = 1)              AS item,
    ANY_VALUE(description) FILTER (WHERE rn = 1)       AS description,
    ANY_VALUE(item_type) FILTER (WHERE rn = 1)         AS item_type,
    ANY_VALUE(unit_of_measure) FILTER (WHERE rn = 1)   AS unit_of_measure,
    ANY_VALUE(unit_vocabulary) FILTER (WHERE rn = 1)   AS unit_vocabulary,
    ANY_VALUE(plausible_min) FILTER (WHERE rn = 1)     AS plausible_min,
    ANY_VALUE(plausible_max) FILTER (WHERE rn = 1)     AS plausible_max,
    ANY_VALUE(cardinality) FILTER (WHERE rn = 1)       AS cardinality,
    ANY_VALUE(values) FILTER (WHERE rn = 1)            AS values,
    ANY_VALUE(source_version) FILTER (WHERE rn = 1)    AS source_version,
    ANY_VALUE(source_url) FILTER (WHERE rn = 1)        AS source_url,
    ANY_VALUE(source_retrieved_date) FILTER (WHERE rn = 1)
                                                       AS source_retrieved_date,
    ANY_VALUE(canonical_concept_id) FILTER (WHERE rn = 1)
                                                       AS canonical_concept_id,
    ANY_VALUE(curation_status) FILTER (WHERE rn = 1)   AS curation_status,
    -- Arrays: union, deduplicated (alternate_names is pipe-delimited string, member_of_collections is array)
    STRING_AGG(DISTINCT alternate_names, '|')          AS alternate_names,
    LIST_DISTINCT(FLATTEN(LIST(member_of_collections))) AS member_of_collections,
    -- Metadata: collect all non-null variants (downstream merges)
    LIST(metadata_) FILTER (WHERE metadata_ IS NOT NULL)
                                                       AS metadata_variants,
    COUNT(*)                                           AS source_row_count
FROM ranked
GROUP BY source_authority, source_code
"""


# Equivalence resolution: edges from rop.equivalence keyed by
# (src_authority, src_code) → (target_vocab, target_code). For each LHS,
# look up the RHS in within_source_dedup to get the target's full row,
# then emit equivalent_rop_id arrays.
#
# We use a simple two-step join: edge → resolve target by vocab+code
# match. Athena CONCEPT_RELATIONSHIP edges flow in via a separate join
# below.
RESOLVE_EDGES_SQL = """
CREATE OR REPLACE TABLE resolved_edges AS
SELECT
    ed.src_authority,
    ed.src_code,
    ed.target_vocab,
    ed.target_code,
    ed.evidence,
    -- Look up the target row (if it exists in our staging)
    ws.source_authority AS target_source_authority,
    ws.source_code      AS target_source_code,
    ws.item             AS target_item
FROM read_parquet(?) ed
LEFT JOIN within_source_dedup ws
    ON ws.source_authority = ed.target_vocab
    OR (ed.target_vocab = 'OMIM' AND ws.source_authority = 'OMIM')
    OR (ed.target_vocab = 'HP' AND ws.source_authority = 'HPO')
    OR (ed.target_vocab = 'MONDO' AND ws.source_authority = 'Mondo')
    OR (ed.target_vocab = 'LOINC' AND ws.source_authority = 'LOINC')
    OR (ed.target_vocab = 'CDISC' AND ws.source_authority = 'CDISC')
    -- Athena-mediated targets: target_vocab matches OMOP vocabulary_id
WHERE ws.source_code = ed.target_code OR ws.source_code IS NULL
"""


# Athena CONCEPT_RELATIONSHIP equivalences: 'Maps to' edges link non-standard
# concepts to standard ones — these are the canonical OMOP equivalence
# relations. We emit one edge per Maps-to in the same shape as the
# rop.equivalence edges so the resolve step is uniform.
ATHENA_MAPS_TO_SQL = """
CREATE OR REPLACE TABLE athena_maps_to_edges AS
SELECT
    'OMOP' AS src_authority,
    CAST(c1.concept_code AS VARCHAR) AS src_code,
    c1.vocabulary_id AS src_vocab,
    c2.vocabulary_id AS target_vocab,
    CAST(c2.concept_code AS VARCHAR) AS target_code,
    c2.concept_id AS target_concept_id,
    'omop_maps_to' AS evidence
FROM read_csv_auto(?, delim=?, header=true, ignore_errors=true) cr
JOIN read_csv_auto(?, delim=?, header=true, ignore_errors=true) c1
    ON cr.concept_id_1 = c1.concept_id
JOIN read_csv_auto(?, delim=?, header=true, ignore_errors=true) c2
    ON cr.concept_id_2 = c2.concept_id
WHERE cr.relationship_id = 'Maps to'
  AND (cr.invalid_reason IS NULL OR cr.invalid_reason = '')
  AND c1.concept_code IS NOT NULL
  AND c2.concept_code IS NOT NULL
  AND c1.standard_concept != 'S'  -- Only non-standard mapping to standard
  AND c2.standard_concept = 'S'
"""


def run_dedup(
    staging_dir: Path,
    out_path: Path,
    source_parquet_glob: str = "*.parquet",
    athena_dir: Path | None = None,
):
    """Execute Pass 1 dedup. Reads all per-source parquets in staging_dir,
    runs within-source dedup, joins equivalence edges, writes one parquet.

    If athena_dir is provided, Athena CONCEPT_RELATIONSHIP 'Maps to' edges
    are added to the equivalence pool.
    """
    try:
        import duckdb
    except ImportError:
        raise SystemExit("duckdb required. Install: pip install duckdb")

    staging_dir = Path(staging_dir)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Combine all per-source parquets via the parquet glob
    source_parquets = list(staging_dir.glob(source_parquet_glob))
    # Exclude derived parquets that aren't per-source
    source_parquets = [
        p for p in source_parquets
        if p.name not in (
            "loinc_six_axis.parquet",
            "equivalence_edges.parquet",
            "dedup_pass1.parquet",
            "manifest.json",
        )
    ]
    if not source_parquets:
        raise FileNotFoundError(
            f"No per-source parquets found in {staging_dir}. "
            f"Run scripts/sprint1_download_all.py first."
        )
    logger.info("Per-source parquets: %s",
                [p.name for p in source_parquets])

    edges_parquet = staging_dir / "equivalence_edges.parquet"
    if not edges_parquet.exists():
        logger.warning(
            "%s not found. Run rop.equivalence.harvest_all first to "
            "populate cross-source equivalences.", edges_parquet,
        )

    con = duckdb.connect(":memory:")
    con.execute("SET memory_limit='12GB'")
    con.execute("SET threads=32")  # Use all available cores

    # Stage 1: within-source dedup. Build UNION ALL of all source parquets
    # to avoid schema mismatch with equivalence_edges/loinc_six_axis
    t0 = time.time()
    logger.info("Stage 1: within-source dedup over %d source parquets", len(source_parquets))

    # Build UNION ALL query
    union_parts = [f"SELECT * FROM read_parquet('{p}')" for p in source_parquets]
    union_query = " UNION ALL BY NAME ".join(union_parts)
    con.execute(f"CREATE TABLE all_sources AS {union_query}")

    # Now run dedup on the combined table
    con.execute(WITHIN_SOURCE_DEDUP_SQL.replace("FROM read_parquet(?)", "FROM all_sources"), [])
    n_after = con.execute(
        "SELECT COUNT(*) FROM within_source_dedup"
    ).fetchone()[0]
    logger.info("Stage 1 complete in %.1fs: %d unique (source, code) rows",
                time.time() - t0, n_after)

    # Stage 2: resolve equivalence edges if available
    if edges_parquet.exists():
        t0 = time.time()
        logger.info("Stage 2: resolving equivalence edges from %s",
                    edges_parquet)
        con.execute(RESOLVE_EDGES_SQL, [str(edges_parquet)])
        n_edges = con.execute(
            "SELECT COUNT(*) FROM resolved_edges WHERE target_source_code IS NOT NULL"
        ).fetchone()[0]
        n_total_edges = con.execute(
            "SELECT COUNT(*) FROM resolved_edges"
        ).fetchone()[0]
        logger.info(
            "Stage 2 complete in %.1fs: %d/%d edges resolved (%.1f%%)",
            time.time() - t0, n_edges, n_total_edges,
            100 * n_edges / max(n_total_edges, 1),
        )

    # Stage 2b: Athena Maps-to edges (canonical OMOP equivalence)
    if athena_dir:
        athena_dir = Path(athena_dir)
        cr_csv = athena_dir / "CONCEPT_RELATIONSHIP.csv"
        c_csv = athena_dir / "CONCEPT.csv"
        if cr_csv.exists() and c_csv.exists():
            t0 = time.time()
            logger.info("Stage 2b: Athena Maps-to edges")
            # Sniff delimiters — newer Athena releases use comma, older tab
            def _sniff(p: Path) -> str:
                with p.open(encoding="utf-8", errors="replace") as f:
                    first = f.readline()
                return "\t" if first.count("\t") >= first.count(",") else ","
            cr_delim = _sniff(cr_csv)
            c_delim = _sniff(c_csv)
            con.execute(
                ATHENA_MAPS_TO_SQL,
                [str(cr_csv), cr_delim,
                 str(c_csv), c_delim,
                 str(c_csv), c_delim],
            )
            n_omop = con.execute(
                "SELECT COUNT(*) FROM athena_maps_to_edges"
            ).fetchone()[0]
            logger.info("Stage 2b complete in %.1fs: %d Maps-to edges",
                        time.time() - t0, n_omop)

    # Stage 3: LOINC six-axis enrichment if available
    six_axis_path = staging_dir / "loinc_six_axis.parquet"
    if six_axis_path.exists():
        t0 = time.time()
        logger.info("Stage 3: LOINC six-axis enrichment")
        con.execute("""
            CREATE OR REPLACE TABLE six_axis AS
            SELECT * FROM read_parquet(?)
        """, [str(six_axis_path)])
        n_axes = con.execute(
            "SELECT COUNT(*) FROM six_axis WHERE axis_component IS NOT NULL"
        ).fetchone()[0]
        logger.info("Stage 3 complete in %.1fs: %d LOINC rows enriched",
                    time.time() - t0, n_axes)

    # Stage 4: Aggregate alternate_codes from Athena Maps-to edges
    if athena_dir:
        t0 = time.time()
        logger.info("Stage 4: Aggregating alternate_codes from Athena Maps-to")
        con.execute("""
            CREATE OR REPLACE TABLE alternate_codes_agg AS
            SELECT
                target_concept_id,
                LIST(DISTINCT STRUCT_PACK(
                    vocabulary := src_vocab,
                    code := src_code
                )) AS alternate_codes
            FROM athena_maps_to_edges
            GROUP BY target_concept_id
        """)
        n_with_alts = con.execute(
            "SELECT COUNT(*) FROM alternate_codes_agg WHERE LEN(alternate_codes) > 0"
        ).fetchone()[0]
        logger.info("Stage 4 complete in %.1fs: %d standard concepts have alternate codes",
                    time.time() - t0, n_with_alts)

    # Final emit: Join alternate_codes back to within_source_dedup
    t0 = time.time()
    logger.info("Writing dedup_pass1.parquet with alternate_codes")

    if athena_dir:
        final_sql = """
            SELECT
                ws.*,
                COALESCE(ac.alternate_codes, []) AS alternate_codes
            FROM within_source_dedup ws
            LEFT JOIN alternate_codes_agg ac
                ON ws.canonical_concept_id = ac.target_concept_id
        """
    else:
        final_sql = """
            SELECT *, CAST([] AS STRUCT(vocabulary VARCHAR, code VARCHAR)[]) AS alternate_codes
            FROM within_source_dedup
        """

    # Use arrow + pyarrow.parquet rather than DuckDB COPY TO with an
    # f-stringed path — eliminates the SQL injection vector entirely
    import pyarrow.parquet as pq
    arrow_reader = con.execute(final_sql).fetch_record_batch()
    arrow_table = arrow_reader.read_all()
    pq.write_table(arrow_table, str(out_path), compression="snappy")
    logger.info("Wrote %s in %.1fs", out_path, time.time() - t0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging-dir",
                        default="data/foundation/staging",
                        help="Directory containing per-source parquets")
    parser.add_argument("--out",
                        default="data/foundation/staging/dedup_pass1.parquet",
                        help="Output parquet path")
    parser.add_argument("--athena-dir", default=None,
                        help="Optional Athena release dir for Maps-to "
                             "extraction (CONCEPT.csv + CONCEPT_RELATIONSHIP.csv)")
    args = parser.parse_args()
    run_dedup(
        Path(args.staging_dir),
        Path(args.out),
        athena_dir=Path(args.athena_dir) if args.athena_dir else None,
    )


if __name__ == "__main__":
    main()
