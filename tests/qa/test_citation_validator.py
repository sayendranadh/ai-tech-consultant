import pytest
from task1_knowledge_brain.qa.citation_validator import CitationError, validate_citations
from task1_knowledge_brain.schemas.qa import SourceRef


def test_valid_citations_pass():
    validate_citations([SourceRef(chunk_id=1, url="x")], {1, 2})


def test_unretrieved_citation_rejected():
    with pytest.raises(CitationError):
        validate_citations([SourceRef(chunk_id=99, url="x")], {1, 2})


def test_empty_sources_ok():
    validate_citations([], {1, 2})
