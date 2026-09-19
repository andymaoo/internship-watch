"""
Apple Careers job scraper.

Three-step flow:
  1. GET the careers page so the session picks up the `jobs` cookie
  2. GET /api/v1/CSRFToken — token returned in the `X-Apple-CSRF-Token` response
     header (NOT the body, which is empty)
  3. POST /api/v1/search with the token + JSON body. Paginate until done.

`query="internship"` narrows from ~1400 false positives (any role mentioning
"intern" in the description, e.g. "International Tax Manager") to ~44 real
intern listings. Server-side filtering is much cheaper than pulling everything.
"""

import requests


CAREERS_NAV_URL = "https://jobs.apple.com/en-us/search"
CSRF_URL = "https://jobs.apple.com/api/v1/CSRFToken"
SEARCH_URL = "https://jobs.apple.com/api/v1/search"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/147.0.0.0 Safari/537.36"
)

PAGE_SIZE = 20  # Apple's API returns up to 20 per page; not configurable.


def _prime_session(session: requests.Session) -> None:
    """Hit the careers HTML page so the session picks up `jobs` and `cs-id`
    cookies. Apple's CSRFToken endpoint will mint a fresh token without these,
    but the search endpoint sometimes 403s if the session looks bare."""
    response = session.get(
        CAREERS_NAV_URL,
        headers={
            "user-agent": USER_AGENT,
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.9",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
        },
        timeout=15,
    )
    response.raise_for_status()


def _get_csrf_token(session: requests.Session) -> str:
    resp = session.get(
        CSRF_URL,
        headers={
            "user-agent": USER_AGENT,
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "referer": CAREERS_NAV_URL,
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
        },
        timeout=15,
    )
    resp.raise_for_status()
    token = resp.headers.get("X-Apple-CSRF-Token")
    if not token:
        raise RuntimeError(
            "X-Apple-CSRF-Token header missing from CSRFToken response. "
            "Apple may have changed their auth flow."
        )
    return token


def _search_page(
    session: requests.Session, csrf_token: str, page: int, query: str = "internship",
    locations: list[str] | None = None,
) -> dict:
    body = {
        "query": query,
        "filters": {"locations": ["postLocation-USA"] if locations is None else locations},
        "page": page,
        "locale": "en-us",
        "sort": "relevance",
        "format": {"longDate": "MMMM D, YYYY", "mediumDate": "MMM D, YYYY"},
    }
    resp = session.post(
        SEARCH_URL,
        headers={
            "user-agent": USER_AGENT,
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "browserlocale": "en-us",
            "content-type": "application/json",
            "locale": "en_US",
            "origin": "https://jobs.apple.com",
            "referer": CAREERS_NAV_URL,
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "x-apple-csrf-token": csrf_token,
        },
        json=body,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict) or not isinstance(data.get("res"), dict) or not isinstance(data["res"].get("searchResults"), list):
        raise RuntimeError("Unexpected Apple search response; cannot establish an empty result")
    return data["res"]


def _format_url(position_id: str, transformed_title: str) -> str:
    # Apple's job-detail URL pattern: /en-us/details/{positionId}/{slug}
    return f"https://jobs.apple.com/en-us/details/{position_id}/{transformed_title}"


def fetch_apple_internships(max_pages: int = 100, locations: list[str] | None = None, session=None) -> list[dict]:
    """Convenience used by scrape.py: pull every active US Apple intern posting."""
    session = session or requests.Session()
    _prime_session(session)
    csrf = _get_csrf_token(session)

    jobs: list[dict] = []
    seen = set()
    for page in range(1, max_pages + 1):
        page_data = _search_page(session, csrf, page=page, locations=locations)
        results = page_data["searchResults"]
        if not results:
            return jobs
        for r in results:
            identity = r.get("id") or r.get("positionId")
            if not identity or not r.get("postingTitle") or not r.get("positionId"):
                raise RuntimeError("Apple job is missing id, title or positionId")
            if identity in seen:
                raise RuntimeError("Apple pagination repeated job IDs")
            seen.add(identity)
            jobs.append({
                "id": identity,
                "title": r.get("postingTitle", ""),
                "url": _format_url(
                    r.get("positionId", ""),
                    r.get("transformedPostingTitle", ""),
                ),
                "source_record": r,
            })
    raise RuntimeError(f"Apple pagination reached safety limit ({max_pages} pages)")


if __name__ == "__main__":
    jobs = fetch_apple_internships()
    print(f"Found {len(jobs)} internships\n")
    for j in jobs[:15]:
        print(f"- {j['title']}")
        print(f"  {j['url']}")
