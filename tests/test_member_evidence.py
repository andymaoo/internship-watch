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
    ({"title": "Junior Software Engineer - Entry Level"}, "new-grad-swe"),
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


@pytest.mark.parametrize(("title", "description", "route"), [
    ("Software Engineer — University Grad", "", "new-grad-swe"),
    ("Software Engineer - New College Graduate", "", "new-grad-swe"),
    ("Graduate Quantitative Researcher, PhD (2027 Start)", "", None),
    ("Data Engineer — Early Career", "This role is open to recent college graduates.", "new-grad-data"),
    ("Investment Banking Full-Time Analyst", "This program is designed for recent graduates.", "new-grad-ib"),
    ("Software Engineer, Early Career", "You will mentor recent graduates.", None),
    ("Graduate Student Research Intern — Machine Learning", "", "intern-ml-ai"),
    ("Software Engineer — New Grad Internship", "", None),
])
def test_additional_early_career_evidence(title, description, route):
    row = dict(title=title,description=description,location="New York, NY",
               posting_status="open",application_status="unverified")
    assert preview_member_listing(row)["route"] == route
