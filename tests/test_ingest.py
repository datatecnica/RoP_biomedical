"""Tests for the source-authority ingest parsers.

These tests use small inline fixtures to verify each parser produces
valid RoPElement instances. Real bulk ingests run during Sprint 1 Monday.
"""
from __future__ import annotations

import csv
import io
import tempfile
from datetime import date
from pathlib import Path

import pytest

from rop.schema import RoPElement, SourceAuthority
from rop.ingest._common import (
    normalize_pipe_delimited,
    parse_obo,
    obo_extract_synonyms,
    obo_extract_xrefs,
    obo_extract_definition,
)


# ---------------------------------------------------------------------------
# _common helpers
# ---------------------------------------------------------------------------

class TestNormalizePipeDelimited:
    def test_basic(self):
        assert normalize_pipe_delimited("a|b|c") == "a|b|c"

    def test_dedup(self):
        assert normalize_pipe_delimited("a|b|a|c|b") == "a|b|c"

    def test_strip(self):
        assert normalize_pipe_delimited("  a  | b  | c") == "a|b|c"

    def test_multiple_inputs(self):
        assert normalize_pipe_delimited("a|b", "b|c") == "a|b|c"

    def test_tolerates_semicolons_and_commas(self):
        assert normalize_pipe_delimited("a;b,c") == "a|b|c"

    def test_none_inputs(self):
        assert normalize_pipe_delimited(None, "a", None) == "a"

    def test_empty(self):
        assert normalize_pipe_delimited(None, "", "  ") is None


class TestObOParser:
    OBO_FIXTURE = """format-version: 1.2
data-version: hp/releases/2026-01-01
ontology: hp

[Term]
id: HP:0001234
name: Test phenotype
def: "A test phenotype for unit-test purposes." [PMID:12345]
synonym: "Test phenotype synonym" EXACT [HPO:doc]
synonym: "Alternate name" RELATED [HPO:doc]
xref: OMIM:168600
xref: MONDO:0005180
is_a: HP:0000001 ! All

[Term]
id: HP:0001235
name: Obsolete term
is_obsolete: true
replaced_by: HP:0001234

[Term]
id: HP:0001236
name: Another phenotype
def: "Another test phenotype." [PMID:67890]
"""

    def test_parses_terms(self, tmp_path):
        obo = tmp_path / "test.obo"
        obo.write_text(self.OBO_FIXTURE)
        terms = list(parse_obo(obo))
        assert len(terms) == 3
        assert terms[0]["id"] == "HP:0001234"
        assert terms[0]["name"] == "Test phenotype"
        assert len(terms[0].get("synonym", [])) == 2
        assert len(terms[0].get("xref", [])) == 2

    def test_extract_synonyms(self, tmp_path):
        obo = tmp_path / "test.obo"
        obo.write_text(self.OBO_FIXTURE)
        terms = list(parse_obo(obo))
        syns = obo_extract_synonyms(terms[0])
        assert "Test phenotype synonym" in syns
        assert "Alternate name" in syns

    def test_extract_xrefs(self, tmp_path):
        obo = tmp_path / "test.obo"
        obo.write_text(self.OBO_FIXTURE)
        terms = list(parse_obo(obo))
        xrefs = obo_extract_xrefs(terms[0])
        assert "OMIM:168600" in xrefs
        assert "MONDO:0005180" in xrefs

    def test_extract_definition(self, tmp_path):
        obo = tmp_path / "test.obo"
        obo.write_text(self.OBO_FIXTURE)
        terms = list(parse_obo(obo))
        defn = obo_extract_definition(terms[0])
        assert defn == "A test phenotype for unit-test purposes."


# ---------------------------------------------------------------------------
# Per-source ingest smoke tests — verify they produce valid RoPElements
# ---------------------------------------------------------------------------

class TestHPOIngest:
    def test_ingests_test_obo(self, tmp_path):
        from rop.ingest.hpo import ingest_hpo

        obo = tmp_path / "hp.obo"
        obo.write_text(TestObOParser.OBO_FIXTURE)

        elements = list(ingest_hpo(obo_path=obo, source_version="HPO-test"))
        # 3 terms in fixture; one is obsolete → expect 2
        assert len(elements) == 2
        assert all(isinstance(e, RoPElement) for e in elements)
        assert all(str(e.source_authority) in ("SourceAuthority.HPO", "HPO")
                  or e.source_authority == SourceAuthority.HPO
                  or e.source_authority == "HPO"
                  for e in elements)
        first = elements[0]
        assert first.source_code == "HP:0001234"
        assert first.item == "Test phenotype"


class TestMondoIngest:
    MONDO_FIXTURE = """format-version: 1.2

[Term]
id: MONDO:0005180
name: Parkinson disease
def: "A neurodegenerative disorder." [Mondo:nicole]
synonym: "PD" EXACT [Mondo:nicole]
xref: OMIM:168600
xref: ICD10:G20
"""

    def test_ingests_basic(self, tmp_path):
        from rop.ingest.mondo import ingest_mondo

        obo = tmp_path / "mondo.obo"
        obo.write_text(self.MONDO_FIXTURE)
        elements = list(ingest_mondo(obo_path=obo, source_version="Mondo-test"))
        assert len(elements) == 1
        e = elements[0]
        assert e.source_code == "MONDO:0005180"
        assert e.item == "Parkinson disease"
        # Cross-references captured in metadata
        assert e.metadata_ is not None
        assert "mondo_xrefs" in e.metadata_


class TestLOINCIngest:
    LOINC_FIXTURE = (
        "LOINC_NUM,COMPONENT,PROPERTY,TIME_ASPCT,SYSTEM,SCALE_TYP,METHOD_TYP,"
        "CLASS,LONG_COMMON_NAME,SHORTNAME,RELATEDNAMES2,EXAMPLE_UCUM_UNITS,"
        "EXAMPLE_UNITS,STATUS\n"
        '"2345-7","Glucose","MCnc","Pt","Ser/Plas","Qn",,'
        '"CHEM","Glucose [Mass/volume] in Serum or Plasma","Glucose SerPl-mCnc",'
        '"Blood sugar|Sugar, blood","mg/dL","mg/dL","ACTIVE"\n'
        '"4544-3","Hematocrit","VFr","Pt","Bld","Qn","Automated count",'
        '"HEM/BC","Hematocrit [Volume Fraction] of Blood by Automated count",'
        '"Hct VFr Bld Auto","Volume fraction|VFr","%","%","ACTIVE"\n'
        '"99999-9","Retired item","",,"","","","","Retired test","","","",,"DEPRECATED"\n'
    )

    def test_ingests_active_terms_only(self, tmp_path):
        from rop.ingest.loinc import ingest_loinc

        csv_path = tmp_path / "Loinc.csv"
        csv_path.write_text(self.LOINC_FIXTURE)
        elements = list(ingest_loinc(csv_path=csv_path, source_version="2.78"))
        assert len(elements) == 2  # the deprecated row is filtered
        glucose = elements[0]
        assert glucose.source_code == "2345-7"
        assert glucose.unit_of_measure == "mg/dL"
        assert glucose.unit_vocabulary == "UCUM"
        # Six-axis preserved in metadata
        assert glucose.metadata_["axis_component"] == "Glucose"
        assert glucose.metadata_["axis_property"] == "MCnc"
        assert glucose.metadata_["axis_system"] == "Ser/Plas"


class TestPhenXIngest:
    PHENX_FIXTURE = (
        "Variable_Name,Variable_Description,Variable_Type,Variable_Unit,"
        "Variable_Min,Variable_Max,Protocol_ID,Protocol_Name,Domain_Name,"
        "Variable_Values\n"
        "AGE_AT_VISIT,Age at study visit in years,numeric,years,18,90,"
        "10101,Demographics,Demographics,\n"
        "SEX_REPORTED,Self-reported sex,categorical,,,,10101,Demographics,"
        "Demographics,1=Male|2=Female|3=Other\n"
    )

    def test_ingests_csv(self, tmp_path):
        from rop.ingest.phenx import ingest_phenx

        csv_path = tmp_path / "phenx.csv"
        csv_path.write_text(self.PHENX_FIXTURE)
        elements = list(ingest_phenx(csv_path=csv_path, source_version="PhenX-test"))
        assert len(elements) == 2
        age = elements[0]
        assert age.item == "AGE_AT_VISIT"
        assert age.plausible_min == 18.0
        assert age.plausible_max == 90.0
        assert age.unit_of_measure == "years"


class TestNINDS_CDE_Ingest:
    NINDS_FIXTURE = (
        "CDE ID,CDE Name,Definition,Data Type,Permissible Values,Variable Name,"
        "Sub-Domain\n"
        "C12345,UPDRS Total Score,Sum of UPDRS items,numeric,,UPDRS_TOTAL,Motor\n"
        "C12346,Diagnosis Confirmed,Was diagnosis confirmed,alphanumeric,"
        "1=Yes;2=No;3=Unknown,DX_CONFIRMED,General\n"
    )

    def test_ingests_csv(self, tmp_path):
        from rop.ingest.ninds_cde import ingest_ninds_cde

        ninds_dir = tmp_path / "parkinson"
        ninds_dir.parent.mkdir(parents=True, exist_ok=True)
        csv_path = tmp_path / "parkinson.csv"
        csv_path.write_text(self.NINDS_FIXTURE)
        elements = list(ingest_ninds_cde(csv_paths=[csv_path],
                                         source_version="NINDS-test"))
        assert len(elements) == 2
        updrs = elements[0]
        assert updrs.source_code == "C12345"
        assert updrs.item == "UPDRS_TOTAL"


class TestCDISCIngest:
    CDISC_FIXTURE = (
        "Code\tCodelist Code\tCodelist Extensible (Yes/No)\tCodelist Name\t"
        "CDISC Submission Value\tCDISC Synonym(s)\tCDISC Definition\t"
        "NCI Preferred Term\n"
        "C25347\tC66731\tNo\tSex\tF\tFemale\t"
        "A person who has the female sex.\tFemale\n"
        "C20197\tC66731\tNo\tSex\tM\tMale\t"
        "A person who has the male sex.\tMale\n"
    )

    def test_ingests_tsv(self, tmp_path):
        from rop.ingest.cdisc import ingest_cdisc

        cdisc_dir = tmp_path / "cdisc"
        cdisc_dir.mkdir()
        path = cdisc_dir / "SDTM_Terminology_2026-03-27.txt"
        path.write_text(self.CDISC_FIXTURE)
        elements = list(ingest_cdisc(csv_path=path,
                                    source_version="CDISC-SDTM-test"))
        assert len(elements) == 2
        female = elements[0]
        assert female.source_code == "C25347"
        assert female.item == "F"
        assert female.metadata_["cdisc_codelist"] == "Sex"


class TestAthenaSixAxisRecovery:
    """LOINC six-axis recovery from CONCEPT_RELATIONSHIP.

    Athena ships LOINC concepts in CONCEPT.csv as flat rows; the six-axis
    decomposition (Component / Property / Time / System / Scale / Method)
    lives in CONCEPT_RELATIONSHIP edges from the LOINC observable concept
    to LOINC Part concepts. This test verifies the parser correctly walks
    those edges and populates axis_* metadata fields.
    """

    CONCEPT_TSV = (
        "concept_id\tconcept_name\tdomain_id\tvocabulary_id\tconcept_class_id\t"
        "standard_concept\tconcept_code\tvalid_start_date\tvalid_end_date\t"
        "invalid_reason\n"
        # The LOINC observable concept
        "3000001\tGlucose [Mass/volume] in Serum or Plasma\tMeasurement\tLOINC\t"
        "Lab Test\tS\t2345-7\t1970-01-01\t2099-12-31\t\n"
        # The LOINC Part concepts referenced by the six-axis edges
        "4000001\tGlucose\tObservation\tLOINC\tLOINC Component\t\tLP14635-4\t"
        "1970-01-01\t2099-12-31\t\n"
        "4000002\tMass concentration\tObservation\tLOINC\tLOINC Property\t\t"
        "LP6831-3\t1970-01-01\t2099-12-31\t\n"
        "4000003\tPoint in time\tObservation\tLOINC\tLOINC Time\t\tLP6960-0\t"
        "1970-01-01\t2099-12-31\t\n"
        "4000004\tSerum or Plasma\tObservation\tLOINC\tLOINC System\t\t"
        "LP7567-2\t1970-01-01\t2099-12-31\t\n"
        "4000005\tQuantitative\tObservation\tLOINC\tLOINC Scale\t\tLP7753-9\t"
        "1970-01-01\t2099-12-31\t\n"
    )

    REL_TSV = (
        "concept_id_1\tconcept_id_2\trelationship_id\tvalid_start_date\t"
        "valid_end_date\tinvalid_reason\n"
        "3000001\t4000001\tHas component\t1970-01-01\t2099-12-31\t\n"
        "3000001\t4000002\tHas property\t1970-01-01\t2099-12-31\t\n"
        "3000001\t4000003\tHas time aspect\t1970-01-01\t2099-12-31\t\n"
        "3000001\t4000004\tHas system\t1970-01-01\t2099-12-31\t\n"
        "3000001\t4000005\tHas scale type\t1970-01-01\t2099-12-31\t\n"
        # Note: no Has method type edge (this is normal — many LOINC
        # concepts lack a method axis). Parser should handle absence.
    )

    VOCAB_TSV = (
        "vocabulary_id\tvocabulary_name\tvocabulary_reference\t"
        "vocabulary_version\tvocabulary_concept_id\n"
        "LOINC\tLOINC\thttp://loinc.org\tLOINC 2.78\t44819102\n"
    )

    def _make_athena_dir(self, tmp_path):
        athena_dir = tmp_path / "athena_release"
        athena_dir.mkdir()
        (athena_dir / "CONCEPT.csv").write_text(self.CONCEPT_TSV)
        (athena_dir / "CONCEPT_RELATIONSHIP.csv").write_text(self.REL_TSV)
        (athena_dir / "VOCABULARY.csv").write_text(self.VOCAB_TSV)
        return athena_dir

    def test_six_axis_map_built_correctly(self, tmp_path):
        from rop.ingest.athena import _build_loinc_six_axis_map

        athena_dir = self._make_athena_dir(tmp_path)
        result = _build_loinc_six_axis_map(athena_dir)

        # The observable concept should have an entry
        assert 3000001 in result
        axes = result[3000001]
        assert axes["axis_component"] == "Glucose"
        assert axes["axis_property"] == "Mass concentration"
        assert axes["axis_time"] == "Point in time"
        assert axes["axis_system"] == "Serum or Plasma"
        assert axes["axis_scale"] == "Quantitative"
        # No method axis edge in fixture — should not appear
        assert "axis_method" not in axes

    def test_ingest_athena_populates_axis_fields_in_metadata(self, tmp_path):
        from rop.ingest.athena import ingest_athena

        athena_dir = self._make_athena_dir(tmp_path)
        # skip_loinc=False (the new default) so LOINC rows are emitted
        elements = [
            e for e in ingest_athena(athena_dir=athena_dir, skip_loinc=False)
            if e.metadata_ and e.metadata_.get("omop_vocabulary_id") == "LOINC"
        ]
        # Find the observable concept
        glucose = next(
            (e for e in elements if e.source_code == "2345-7"), None
        )
        assert glucose is not None, "LOINC observable concept not yielded"
        assert glucose.metadata_.get("axis_component") == "Glucose"
        assert glucose.metadata_.get("axis_property") == "Mass concentration"
        assert glucose.metadata_.get("axis_system") == "Serum or Plasma"

    def test_six_axis_skipped_when_concept_relationship_absent(self, tmp_path):
        """Graceful degradation: missing CONCEPT_RELATIONSHIP shouldn't break ingest."""
        from rop.ingest.athena import _build_loinc_six_axis_map

        athena_dir = tmp_path / "athena_no_rel"
        athena_dir.mkdir()
        (athena_dir / "CONCEPT.csv").write_text(self.CONCEPT_TSV)
        # Note: no CONCEPT_RELATIONSHIP.csv

        result = _build_loinc_six_axis_map(athena_dir)
        assert result == {}
