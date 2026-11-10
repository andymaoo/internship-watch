"""Build a bounded, isolated member pilot from the reviewed source registry."""
from copy import deepcopy

PILOT = (
    "greenhouse-databricks", "ashby-notion", "lever-zoox",
    "greenhouse-point72", "bankofamerica-campus",
    "workday-capital-one", "workday-morgan-stanley",
)
WORKDAY_QUERIES = (
    "intern", "new grad", "graduate program",
    "investment banking summer analyst", "investment banking summer associate",
)

TRUIST = {
    "id": "workday-truist-member-campus", "type": "workday", "employer": "Truist Securities",
    "url": "https://truist.wd1.myworkdayjobs.com/LDP", "queries": ["investment banking"],
    "member_opportunities": True, "country_scope": ["US"], "max_pages": 15,
}


def pilot_config(registry: dict, database: str) -> dict:
    """Create explicit candidate queries, leaving the private config untouched."""
    by_id = {source["id"]: source for source in registry["sources"]}
    sources = [deepcopy(by_id[key]) for key in PILOT]
    for source in sources:
        if source["type"] == "workday":
            source["queries"] = list(WORKDAY_QUERIES)
            source["member_opportunities"] = True
            source["country_scope"] = ["US"]
    sources.append(deepcopy(TRUIST))
    return {
        "member_feed": True, "database": database, "initial_run": "silent",
        "sources": sources, "notifications": {"channel": "discord"},
        "http": deepcopy(registry.get("http", {})),
        "poll_seconds": 900, "source_seconds": 180, "collection_workers": 1,
        "validation_seconds": 120, "validation_workers": 1, "validation_budget": 30,
    }
