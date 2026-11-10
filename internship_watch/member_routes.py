"""Stage-one routing contract for the US member feed; no delivery side effects."""

CATEGORIES = {
    "product_management": "pm",
    "investment_banking": "ib",
    "quantitative": "quant",
    "software_engineering": "swe",
    "ml_ai": "ml-ai",
    "data_science": "data",
    "data_engineering": "data",
    "data_analysis": "data",
}
KINDS = {"internship": "intern", "new_grad": "new-grad"}


def member_route(*, us_eligible: bool | None, opportunity_type: str,
                 category: str, posting_status: str,
                 application_status: str, remote: bool = False) -> str | None:
    """Route confirmed US jobs and remote jobs without evidence excluding the US."""
    # False means affirmative evidence that the role cannot be done from the US.
    if us_eligible is False or (us_eligible is None and not remote):
        return None
    if posting_status != "open" or application_status == "closed":
        return None
    kind = KINDS.get(opportunity_type)
    topic = CATEGORIES.get(category)
    return f"{kind}-{topic}" if kind and topic else None
