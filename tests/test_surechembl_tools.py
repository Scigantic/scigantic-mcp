"""Live tests for the surechembl_* tool layer. These call SureChEMBL and
UniChem for real (through scigantic-surechembl, whose own suite is live
for the same reason: the API's miss/error behaviour is uneven enough that
a fixture would only prove the fixture). Runs under plain pytest via
asyncio.run(), like test_tools.py.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scigantic_mcp import surechembl as S  # noqa: E402


def run(coro):
    return asyncio.run(coro)


def test_compound_by_every_identifier_form_resolves_to_aspirin():
    for ident in ("SCHEMBL1353", "1353", "CHEMBL25", "pubchem:2244", "BSYNRYMUTXBXSQ-UHFFFAOYSA-N", "CC(=O)Oc1ccccc1C(=O)O", "aspirin"):
        out = run(S.surechembl_compound(ident))
        assert "SCHEMBL1353" in out, ident
        assert "BSYNRYMUTXBXSQ-UHFFFAOYSA-N" in out
        assert "patent document(s)" in out
    assert "ChEMBL CHEMBL25" in out and "PubChem CID 2244" in out


def test_compound_miss_and_bad_input_are_messages_not_exceptions():
    assert run(S.surechembl_compound("zzqqxx")).startswith("No SureChEMBL compound")
    assert run(S.surechembl_compound("")).startswith("No SureChEMBL compound")
    assert run(S.surechembl_compound("nope:123")).startswith("Error:")


def test_patents_for_compound_reports_total_and_hint():
    out = run(S.surechembl_patents_for_compound("CHEMBL113", limit=3))
    assert "SCHEMBL5671" in out
    assert "https://www.surechembl.org/patent/" in out
    assert "Only the first 3" in out  # caffeine is in ~200k documents


def test_patent_document_and_text_toggle():
    short = run(S.surechembl_patent("US10000000B2"))
    assert short.startswith("US-10000000-B2  Coherent LADAR")
    assert "RAYTHEON" in short and "Abstract:" in short and "Claims:" not in short
    full = run(S.surechembl_patent("US-10000000-B2", include_text=True))
    assert "Claims:" in full and "What is claimed" in full and "Description:" in full
    assert "Family: 55456961" in short and "Compounds named in the text: 0" in short
    assert "PDF: https://www.surechembl.org/api/patent/pdf/US-10000000-B2" in short
    assert "CPC:" not in short and "Citations" not in short  # gone from the API, not shown as zero
    assert "has no document" in run(S.surechembl_patent("US-99999999999-B2"))
    assert run(S.surechembl_patent("notanumber")).startswith("Error:")


def test_patent_chemistry_lists_and_truncates():
    out = run(S.surechembl_patent_chemistry("US-5399578-A", limit=3))
    head = out.splitlines()[0]
    n = int(head.split()[0].replace(",", ""))
    assert n > 300 and "named in the text of US-5399578-A" in head
    assert "images or attachments are not included" in head
    assert out.count("SCHEMBL") == 3
    assert f"{n - 3:,} more" in out
    assert "found no compounds" in run(S.surechembl_patent_chemistry("US-10000000-B2"))


def test_search_patents_solr_and_errors():
    out = run(S.surechembl_search_patents("ttl:aspirin AND pdyear:2024", limit=2))
    assert "match" in out and "2024" in out and "US, EP, WO, JP and CN" in out
    err = run(S.surechembl_search_patents("ttl:", limit=2))
    assert err.startswith("Error:") and "\n" not in err.strip()  # trimmed to Solr's first line
    assert run(S.surechembl_search_patents("", 5)).startswith("Error: query is required")


def test_structure_search_modes_and_guard():
    out = run(S.surechembl_structure_search("CC(=O)Oc1ccccc1C(=O)O", "similarity", 3))
    assert "similarity hit(s)" in out and "similarity 1.00" in out
    assert "C9H8O4" in out  # full records, not bare ids
    assert run(S.surechembl_structure_search("C1CC(((", "identical", 3)).startswith("Error:")
    assert run(S.surechembl_structure_search("C", "substructure", 3)).startswith("Error: substructure query")
    assert run(S.surechembl_structure_search("CCO", "fuzzy", 3)).startswith("Error: mode must be")
