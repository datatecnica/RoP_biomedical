"""Cross-source equivalence harvest.

Each source-authority parser deposits xrefs into the row's `metadata_`
JSONB field. This module unifies those into a single edge table that the
Tuesday dedup pass joins back onto rows to populate the
`equivalent_rop_ids` arrays.

The xrefs come from four streams:

1. **HPO** — `metadata_['hpo_xrefs']` lists OMIM:NNNNNN, MONDO:NNNNNNN,
   SNOMED:NNNNNNN entries from the HPO OBO `xref:` lines. (HPO also
   carries UMLS xrefs but those are dropped during normalization since
   UMLS itself is not in the RoP open-source corpus.)
2. **Mondo** — `metadata_['mondo_xrefs']` carries OMIM, ICD-10, ICD-9-CM,
   MeSH, Orphanet, NCIT, DOID xrefs from the Mondo OBO.
3. **NINDS-CDE** — `metadata_['ninds_xrefs']` ships built-in to the bulk
   export with prefixed identifiers (LOINC:NNNNN-N, SNOMED:NNNNNN,
   caDSR:NNNNNNN, CDISC:CNNNNN).
4. **Athena CONCEPT_RELATIONSHIP** — handled separately by the dedup pass
   via DuckDB SQL (the edge table itself is the cross-source map for OMOP).

Output schema (parquet):

    src_authority    str   — source authority of the row carrying the xref
    src_code         str   — source-vocabulary identifier of that row
    target_vocab     str   — normalized vocabulary name of the xref
    target_code      str   — identifier in the target vocabulary
    evidence         str   — provenance tag ('hpo_xref', 'mondo_xref', etc.)

Vocabulary names are normalized to a canonical set:
    OMIM, MONDO, HP, ICD10, ICD10CM, ICD9CM, MESH, SNOMED, NCIT,
    LOINC, RxNorm, ATC, MEDDRA, ORPHANET, DOID, caDSR, CDISC, HGNC

Note: UMLS CUIs are intentionally NOT in the canonical set. UMLS license
terms preclude redistribution of CUIs in an open-source bundle, and we
have no UMLS source authority in the corpus, so UMLS xref tokens
encountered in upstream OBO files (HPO carries some) are dropped during
normalization.

SNOMED appears in the canonical list because cross-source xrefs from
Mondo and NINDS-CDE reference SNOMED IDs by code. Those references stay
even though we don't redistribute SNOMED *content* — the IDs themselves
are integers, not licensed text.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

logger = logging.getLogger(__name__)


# Canonical vocabulary names. Source-authority output uses these.
# Additional aliases below in `VOCAB_ALIASES` get normalized to these.
CANONICAL_VOCABS = {
    "OMIM", "MONDO", "HP", "ICD10", "ICD10CM", "ICD10PCS", "ICD9CM",
    "ICD9Proc", "MESH", "SNOMED", "NCIT", "LOINC", "RxNorm",
    "ATC", "MEDDRA", "ORPHANET", "DOID", "caDSR", "CDISC", "HGNC",
    "ENSEMBL", "EFO", "NCBIGENE", "UniProtKB", "PubMed", "PMID",
}

VOCAB_ALIASES = {
    # Direct aliases → canonical
    "HPO": "HP",
    "OMIM-PS": "OMIM",
    "MIM": "OMIM",
    "MONDO_GENETIC": "MONDO",
    "ICD-10": "ICD10",
    "ICD-10-CM": "ICD10CM",
    "ICD-10-PCS": "ICD10PCS",
    "ICD-9-CM": "ICD9CM",
    "ICD9": "ICD9CM",
    "ICD-9": "ICD9CM",
    "MSH": "MESH",
    "MESHA": "MESH",
    "SCTID": "SNOMED",
    "SNOMEDCT": "SNOMED",
    "SNOMED_CT": "SNOMED",
    "SNOMED CT": "SNOMED",
    "SCT": "SNOMED",
    "NCI": "NCIT",
    "NCI_THESAURUS": "NCIT",
    "MEDDRAID": "MEDDRA",
    "DiseasesDB": "DiseasesDB",  # leave as-is for now; downstream can drop
    "Orphanet": "ORPHANET",
    "ORDO": "ORPHANET",
    "DO": "DOID",
    "Disease_Ontology": "DOID",
    "Cadsr": "caDSR",
    "CADSR": "caDSR",
    "Cdisc": "CDISC",
    "RXNORM": "RxNorm",
    "Rxnorm": "RxNorm",
    "EnsEMBL": "ENSEMBL",
    "Ensembl": "ENSEMBL",
    "Hgnc": "HGNC",
    "PMID": "PubMed",
    "Pubmed": "PubMed",
}


def normalize_vocab(raw: str) -> str | None:
    """Map a raw vocabulary name to its canonical form. Returns None for
    unrecognized vocabularies that we don't want to clutter the edge graph."""
    if not raw:
        return None
    raw = raw.strip()
    # Direct hit
    if raw in CANONICAL_VOCABS:
        return raw
    # Alias hit
    if raw in VOCAB_ALIASES:
        return VOCAB_ALIASES[raw]
    # Case-insensitive alias hit
    upper = raw.upper()
    for vocab in CANONICAL_VOCABS:
        if upper == vocab.upper():
            return vocab
    for alias, target in VOCAB_ALIASES.items():
        if upper == alias.upper():
            return target
    # Otherwise drop the prefix — the edge graph stays clean
    return None


# Regex for parsing 'VOCAB:CODE' tokens. Tolerates whitespace around colon
# and codes that contain hyphens, dots, slashes (LOINC '12345-6', MIM
# numbers, etc.).
_XREF_PATTERN = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_\- ]*?)\s*:\s*(.+?)\s*$")


def parse_xref_token(token: str) -> tuple[str, str] | None:
    """Parse a 'VOCAB:CODE' token into (canonical_vocab, code). Returns None
    for tokens that don't match the format or have unrecognized vocabularies."""
    if not token:
        return None
    m = _XREF_PATTERN.match(token)
    if not m:
        return None
    raw_vocab, raw_code = m.group(1), m.group(2)
    vocab = normalize_vocab(raw_vocab)
    if vocab is None:
        return None
    code = raw_code.strip()
    if not code:
        return None
    return (vocab, code)


@dataclass
class EquivalenceEdge:
    """A single cross-source equivalence assertion."""
    src_authority: str
    src_code: str
    target_vocab: str
    target_code: str
    evidence: str  # 'hpo_xref', 'mondo_xref', 'ninds_xref', 'manual', etc.

    def to_dict(self) -> dict:
        return {
            "src_authority": self.src_authority,
            "src_code": self.src_code,
            "target_vocab": self.target_vocab,
            "target_code": self.target_code,
            "evidence": self.evidence,
        }


# Map from source-authority name to (metadata_ key, evidence tag).
# Each source's parser populates metadata_[<key>] with a list of xref tokens.
XREF_FIELD_BY_SOURCE = {
    "HPO": ("hpo_xrefs", "hpo_xref"),
    "Mondo": ("mondo_xrefs", "mondo_xref"),
    "MONDO": ("mondo_xrefs", "mondo_xref"),
    "NINDS-CDE": ("ninds_xrefs", "ninds_xref"),
    # Athena rows contribute equivalences via CONCEPT_RELATIONSHIP, handled
    # separately by the DuckDB pass — not via metadata_ xrefs here.
}


def harvest_xrefs_from_row(row: dict) -> Iterator[EquivalenceEdge]:
    """Yield EquivalenceEdges for one parsed row.

    The row is the dict-form of a RoPElement (e.g., from `model_dump()`).
    Reads source_authority + source_code + metadata_, looks up the
    appropriate xref field per the source registry, and emits one edge
    per parsed xref token.
    """
    src_auth = row.get("source_authority")
    src_code = row.get("source_code")
    metadata = row.get("metadata_") or {}

    if not src_auth or not src_code:
        return
    # source_authority may be the enum name or the value
    src_auth_str = str(src_auth).replace("SourceAuthority.", "")

    field_info = XREF_FIELD_BY_SOURCE.get(src_auth_str)
    if field_info is None:
        return

    field_name, evidence_tag = field_info
    raw_xrefs = metadata.get(field_name) or []
    if not raw_xrefs:
        return

    for token in raw_xrefs:
        if not isinstance(token, str):
            continue
        parsed = parse_xref_token(token)
        if parsed is None:
            continue
        target_vocab, target_code = parsed
        yield EquivalenceEdge(
            src_authority=src_auth_str,
            src_code=str(src_code),
            target_vocab=target_vocab,
            target_code=target_code,
            evidence=evidence_tag,
        )


def harvest_from_parquet(parquet_path: Path) -> Iterator[EquivalenceEdge]:
    """Stream EquivalenceEdges from a per-source parquet file."""
    try:
        import pyarrow.parquet as pq
    except ImportError:
        raise SystemExit("pyarrow required for equivalence harvest. "
                         "Install: pip install pyarrow")
    parquet_path = Path(parquet_path)
    if not parquet_path.exists():
        logger.warning("Parquet not found: %s", parquet_path)
        return
    pf = pq.ParquetFile(parquet_path)
    # Stream in batches to keep memory bounded
    for batch in pf.iter_batches(batch_size=10000):
        df = batch.to_pylist()
        for row in df:
            yield from harvest_xrefs_from_row(row)


def harvest_from_jsonl(jsonl_path: Path) -> Iterator[EquivalenceEdge]:
    """Stream EquivalenceEdges from a per-source JSONL file (fallback when
    pyarrow not available during ingest)."""
    jsonl_path = Path(jsonl_path)
    if not jsonl_path.exists():
        logger.warning("JSONL not found: %s", jsonl_path)
        return
    with jsonl_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            yield from harvest_xrefs_from_row(row)


def harvest_all(staging_dir: Path) -> Iterator[EquivalenceEdge]:
    """Walk all source parquets/JSONL in a staging dir and yield edges."""
    staging_dir = Path(staging_dir)
    seen_paths: set[Path] = set()
    for p in sorted(staging_dir.glob("*.parquet")):
        seen_paths.add(p)
        logger.info("Harvesting xrefs from %s", p.name)
        yield from harvest_from_parquet(p)
    for p in sorted(staging_dir.glob("*.jsonl")):
        if p.with_suffix(".parquet") in seen_paths:
            continue  # parquet takes precedence
        logger.info("Harvesting xrefs from %s", p.name)
        yield from harvest_from_jsonl(p)


def write_edges_parquet(
    edges: Iterable[EquivalenceEdge],
    out_path: Path,
) -> int:
    """Materialize edges to a parquet file. Returns count written."""
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        raise SystemExit("pyarrow required. Install: pip install pyarrow")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [e.to_dict() for e in edges]
    if not rows:
        logger.warning("No edges to write")
        return 0
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, out_path, compression="snappy")
    logger.info("Wrote %d edges to %s", len(rows), out_path)
    return len(rows)
