"""Tests for rop.equivalence — xref harvest from per-source metadata."""
from __future__ import annotations

import json
import pytest

from rop.equivalence import (
    EquivalenceEdge,
    harvest_xrefs_from_row,
    normalize_vocab,
    parse_xref_token,
)


class TestNormalizeVocab:
    def test_canonical_passthrough(self):
        assert normalize_vocab("OMIM") == "OMIM"
        assert normalize_vocab("MONDO") == "MONDO"
        assert normalize_vocab("HP") == "HP"

    def test_alias_mapping(self):
        assert normalize_vocab("HPO") == "HP"
        assert normalize_vocab("MIM") == "OMIM"
        assert normalize_vocab("ICD-10") == "ICD10"
        assert normalize_vocab("ICD-10-CM") == "ICD10CM"
        assert normalize_vocab("SNOMED CT") == "SNOMED"
        assert normalize_vocab("SCTID") == "SNOMED"

    def test_case_insensitive(self):
        assert normalize_vocab("omim") == "OMIM"
        assert normalize_vocab("loinc") == "LOINC"
        assert normalize_vocab("snomed") == "SNOMED"

    def test_unrecognized_returns_none(self):
        # Drop unknown vocabularies to keep the edge graph clean
        assert normalize_vocab("UNKNOWN_VOCAB") is None
        assert normalize_vocab("") is None
        assert normalize_vocab(None) is None


class TestParseXrefToken:
    def test_basic(self):
        assert parse_xref_token("OMIM:168600") == ("OMIM", "168600")
        assert parse_xref_token("HP:0001234") == ("HP", "0001234")
        assert parse_xref_token("MONDO:0005180") == ("MONDO", "0005180")

    def test_loinc_with_hyphen(self):
        # LOINC codes are like '12345-6' — preserve the suffix
        assert parse_xref_token("LOINC:12345-6") == ("LOINC", "12345-6")

    def test_aliased_prefix(self):
        # 'HPO:' should normalize to 'HP'
        assert parse_xref_token("HPO:0001234") == ("HP", "0001234")
        # 'ICD-10-CM:' should normalize to 'ICD10CM'
        assert parse_xref_token("ICD-10-CM:E11.9") == ("ICD10CM", "E11.9")

    def test_whitespace_tolerance(self):
        assert parse_xref_token("  OMIM:168600  ") == ("OMIM", "168600")
        assert parse_xref_token("OMIM: 168600") == ("OMIM", "168600")

    def test_unknown_vocab_returns_none(self):
        assert parse_xref_token("FOOBAR:999") is None

    def test_no_colon_returns_none(self):
        assert parse_xref_token("just-a-string") is None
        assert parse_xref_token("") is None

    def test_empty_code_returns_none(self):
        assert parse_xref_token("OMIM:") is None
        assert parse_xref_token("OMIM:  ") is None


class TestHarvestFromRow:
    def test_hpo_row(self):
        row = {
            "source_authority": "HPO",
            "source_code": "HP:0001234",
            "metadata_": {
                # HPO OBO carries UMLS xrefs in the wild. We expect those
                # to be DROPPED during normalization since UMLS is not in
                # the RoP open-source corpus.
                "hpo_xrefs": ["OMIM:168600", "MONDO:0005180", "UMLS:C0030567"],
            },
        }
        edges = list(harvest_xrefs_from_row(row))
        # UMLS dropped → 2 edges, not 3
        assert len(edges) == 2
        assert all(e.src_authority == "HPO" for e in edges)
        assert all(e.src_code == "HP:0001234" for e in edges)
        assert all(e.evidence == "hpo_xref" for e in edges)
        targets = [(e.target_vocab, e.target_code) for e in edges]
        assert ("OMIM", "168600") in targets
        assert ("MONDO", "0005180") in targets
        # UMLS should NOT be present in the edge graph
        assert not any(t[0] == "UMLS" for t in targets)

    def test_mondo_row(self):
        row = {
            "source_authority": "Mondo",
            "source_code": "MONDO:0005180",
            "metadata_": {
                "mondo_xrefs": ["OMIM:168600", "ICD-10:G20", "MeSH:D010300"],
            },
        }
        edges = list(harvest_xrefs_from_row(row))
        assert len(edges) == 3
        targets = [(e.target_vocab, e.target_code) for e in edges]
        assert ("OMIM", "168600") in targets
        assert ("ICD10", "G20") in targets
        assert ("MESH", "D010300") in targets

    def test_ninds_row(self):
        row = {
            "source_authority": "NINDS-CDE",
            "source_code": "C12345",
            "metadata_": {
                "ninds_xrefs": ["LOINC:1234-5", "SNOMED:73211009",
                                "caDSR:3192017", "CDISC:C25347"],
            },
        }
        edges = list(harvest_xrefs_from_row(row))
        assert len(edges) == 4
        targets = [(e.target_vocab, e.target_code) for e in edges]
        assert ("LOINC", "1234-5") in targets
        assert ("SNOMED", "73211009") in targets
        assert ("caDSR", "3192017") in targets
        assert ("CDISC", "C25347") in targets

    def test_no_xrefs_yields_nothing(self):
        row = {
            "source_authority": "HPO",
            "source_code": "HP:0001234",
            "metadata_": {},
        }
        edges = list(harvest_xrefs_from_row(row))
        assert edges == []

    def test_unknown_source_yields_nothing(self):
        row = {
            "source_authority": "OMOP",
            "source_code": "12345",
            "metadata_": {"hpo_xrefs": ["OMIM:168600"]},
        }
        # OMOP doesn't have hpo_xrefs in its registered mapping — no edges
        edges = list(harvest_xrefs_from_row(row))
        assert edges == []

    def test_skips_invalid_xref_tokens(self):
        row = {
            "source_authority": "HPO",
            "source_code": "HP:0001234",
            "metadata_": {
                "hpo_xrefs": [
                    "OMIM:168600",      # valid
                    "FOOBAR:999",       # unknown vocab → dropped
                    "no-colon-here",    # invalid format → dropped
                    "",                 # empty → dropped
                ],
            },
        }
        edges = list(harvest_xrefs_from_row(row))
        assert len(edges) == 1
        assert edges[0].target_vocab == "OMIM"
