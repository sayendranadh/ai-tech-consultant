from src.matcher import match_requirements
from src.schemas_3c import BaselineRequirement, FollowupRequirement


def _br(rid: str, quote: str) -> BaselineRequirement:
    return BaselineRequirement(requirement_id=rid, description=quote, source_quote=quote)


def _fr(rid: str, quote: str) -> FollowupRequirement:
    return FollowupRequirement(
        requirement_id=rid, description=quote, source_quote=quote,
        turn_id="turn-001", provenance="client_stated",
    )


def test_identical_quote_is_confirmed_match():
    m = match_requirements(
        [_br("B1", "We must redesign the homepage to reflect the new brand.")],
        [_fr("F1", "We must redesign the homepage to reflect the new brand.")],
    )[0]
    assert m.match_status == "confirmed"
    assert m.baseline_requirement_id == "B1"


def test_no_overlap_is_none_match():
    m = match_requirements(
        [_br("B1", "Redesign homepage.")],
        [_fr("F1", "Build a mobile application for Android and iOS devices.")],
    )[0]
    assert m.match_status == "none"
    assert m.baseline_requirement_id is None


def test_partial_overlap_is_ambiguous_or_confirmed():
    m = match_requirements(
        [_br("B1", "we must add a contact form that routes submissions to our sales team")],
        [_fr("F1", "we must route contact form submissions to our support team")],
    )[0]
    assert m.match_status in ("confirmed", "ambiguous")


def test_false_positive_not_confirmed():
    m = match_requirements(
        [_br("B1", "homepage redesign brand colors")],
        [_fr("F1", "payment gateway integration stripe")],
    )[0]
    assert m.match_status == "none"
