import pytest

from internship_watch.member_routes import member_route


BASE = dict(us_eligible=True, opportunity_type="internship",
            category="investment_banking", posting_status="open",
            application_status="unverified")


@pytest.mark.parametrize(("changes", "expected"), [
    ({}, "intern-ib"),
    ({"opportunity_type": "new_grad", "category": "ml_ai"}, "new-grad-ml-ai"),
    ({"category": "data_engineering"}, "intern-data"),
    ({"us_eligible": None}, None),
    ({"us_eligible": False}, None),
    ({"us_eligible": None, "remote": True}, "intern-ib"),
    ({"us_eligible": False, "remote": True}, None),
    ({"us_eligible": True, "remote": True}, "intern-ib"),
    ({"us_eligible": None, "remote": True, "posting_status": "unverified"}, None),
    ({"opportunity_type": "full_time"}, None),
    ({"category": "ambiguous"}, None),
    ({"posting_status": "unverified"}, None),
    ({"application_status": "closed"}, None),
])
def test_member_route(changes, expected):
    assert member_route(**(BASE | changes)) == expected
