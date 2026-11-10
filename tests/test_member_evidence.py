import pytest

from internship_watch.member_evidence import preview_member_listing


@pytest.mark.parametrize(("fields", "route"), [
    ({"location": "Remote"}, "intern-swe"),
    ({"location": "", "is_remote": True}, "intern-swe"),
    ({"location": "Remote", "country": "AU"}, None),
    ({"location": "Remote", "countries": ["US", "CA"]}, "intern-swe"),
    ({"location": "Hybrid", "is_remote": True}, None),
    ({"location": "Remote - Worldwide"}, "intern-swe"),
    ({"location": "Remote - Canada only"}, None),
    ({"location": "Remote", "description": "You must be based in Canada."}, None),
    ({"location": "Remote", "description": "We hire worldwide, excluding the United States."}, None),
    ({"location": "Toronto, Canada (Hybrid)"}, None),
    ({"location": "Springfield"}, None),
    ({"location": "San Francisco, CA (Hybrid)"}, "intern-swe"),
    ({"title": "Investment Banking Summer Analyst", "employment_type": "Internship"}, "intern-ib"),
    ({"title": "Investment Banking Summer Analyst"}, None),
    ({"title": "Software Engineer - University Graduate", "employment_type": "Full Time"}, "new-grad-swe"),
    ({"title": "Junior Software Engineer - Entry Level"}, None),
    ({"title": "Software Engineering Intern / New Grad"}, None),
    ({"title": "Software Engineer Intern", "description": "This role is not an internship."}, None),
    ({"description": "No visa sponsorship. Clearance required."}, "intern-swe"),
    ({"title": "Hardware Engineering Intern"}, None),
    ({"posting_status": "unverified"}, None),
    ({"application_status": "closed"}, None),
])
def test_preview_from_normalized_listing(fields, route):
    job = dict(title="Software Engineer Intern", location="New York, NY",
               posting_status="open", application_status="unverified")
    assert preview_member_listing(job | fields)["route"] == route
