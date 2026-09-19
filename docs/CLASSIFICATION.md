# Classification and link evidence

The reviewed baseline was commit `2a776814a993fd74e92cc91aa15e90fb0f99424a`.
Its `scrape.py:124` keyword matcher accepted ordinary Software Engineer roles and
Hardware Engineering Intern roles, and rejected Product Manager Intern because
`manager` was an unconditional exclusion. Tests replay the matcher from that
commit via AST without importing or running its scraper. Before replacement, all
three desired outcomes failed. `tests/test_classify.py` retains the baseline
observations alongside tests of the corrected outcomes.

`internship_watch/classify.py` produces an explicit `include`, `exclude`, or
`ambiguous` decision, a category, opportunity kind, evidence, reasons, and
eligibility details. The seven category values are `software_engineering`,
`data_analysis`, `data_engineering`, `data_science`, `ml_ai`, `quantitative`, and
`product_management`. Backend/full-stack belong to software; algorithmic trading
belongs to quantitative; ML/AI research belongs to ML/AI. Category aliases
`software`, `ml`, `ai`, `quant`, and `product` are accepted in configuration.

Positive internship evidence can be a word-bounded title, structured employment
type, or an affirmative description statement about this role. Prior internship
experience and the word “international” do not establish an internship. A
Simplify internship-feed context is recorded as a reason to inspect a listing,
but does not independently prove that the particular role is an internship.
Ordinary full-time/new-graduate and senior career roles are excluded. A full-time
schedule does not disqualify a clearly identified internship. Conflicting
permanent and internship evidence is sent to review.

The user's later request also enables relevant research fellowships/programs.
Set `include_research_programs: true`; qualifying records carry
`opportunity_kind: research_program`. This does not admit ordinary Research
Scientist or Research Program Manager employment. Legal, medical, clinical, and
user/UX research are outside these software/data/AI/quant families.

Hardware exclusions examine the role title and explicit circuit/ASIC/RTL/FPGA/
mechanical/electrical duties. Employer name is never a hardware exclusion.
Qualifying software/AI work at hardware employers is retained. Mixed software
and physical-design duties are ambiguous instead of guessed.
Verified device-fabrication, RFIC, physical component-evaluation, hardware test-lab,
and mechatronics duties are excluded even when they mention data analysis or
software colleagues. A mixed-signal role with substantive ML duties stays under
review; device-software and AI-model roles do not inherit a company-level ban.

## Configurable preferences

Filters support `categories`, `countries`, `remote_policy` (`any`, `only`,
`exclude`), `remote_eligible_countries`, `seasons`, `include_coop`, `degrees`,
`graduation_years`, `student_years`, `requires_sponsorship`,
`include_research_programs`, `companies`, `exclude_companies`, `citizenships`,
`has_security_clearance`, and
`allow_unstated_eligibility`. Company lists use exact names case-insensitively.
Empty lists impose
no restriction. Season values can be `summer2027`, `summer 2027`, or `summer`.
No year/season is inferred from today's date. Explicit graduation ranges are
expanded; a job's listing year is never treated as its graduation requirement.

For the expressed preferences use United States, bachelor, junior,
`requires_sponsorship: false`, all seasons, co-ops allowed, research programs
allowed, and `allow_unstated_eligibility: true`. The last setting allows roles
without stated degree/class-year requirements while recording that uncertainty.
It does not waive unknown geography or invent internship evidence. Junior-only
selection excludes explicitly freshman/sophomore-only programs and retains
programs that include juniors. No sponsorship requirement means employers that
do not sponsor remain eligible. Citizenship/security-clearance requirements are
ambiguous when the corresponding eligibility is unset; work authorization is not
proof of citizenship. Set `citizenships` to confirmed country codes and
`has_security_clearance` only when confirmed. An explicit incompatible citizenship
or lack of required active clearance is excluded. EEO citizenship boilerplate and
an optional ability to obtain clearance do not restrict results. Mandatory
ability-to-obtain requirements still need review. Citizenship-or-permanent-residence
alternatives remain explicit.
References to senior engineers/researchers as colleagues do not establish a
student-year requirement. “Rising senior” is mapped to current junior status and
the original phrase is recorded; analogous rising-year mappings are explicit.

US geography uses stated countries and explicit US city/state location evidence.
Recognized city/state inference is recorded. Unrecognized city-only listings are
ambiguous, and remote alone never means US work eligibility. Locations with an
explicit foreign country are not reinterpreted as US due to a shared city name.
Descriptions and source-provided degree metadata are considered together with
degree markers in titles. A PhD-only internship is excluded for a bachelor
candidate; an unstated requirement is left visible under the configured policy.
Description statements such as “No PhD required” and optional/preferred degree
qualifications are recorded separately from required/allowed degrees. Title and
structured-feed degree constraints remain authoritative classification evidence.
Application dropdown choices and voluntary demographic/disability text are not
degree eligibility evidence. A “Graduate Intern” title alone does not override
an employer's explicit inclusion of current bachelor students.

The classifier is an auditable rule system, not a guarantee of applicant
eligibility. Unusual wording, qualification preferences versus requirements,
non-English listings, broad research titles, and ambiguous locations can require
review. `positive_opportunity_evidence` lets the runner prioritize link enrichment
for plausible opportunities rather than ordinary career listings.

## Link validation

`internship_watch/links.py` checks description and application destinations,
following the HTTP client's bounded redirects, timeouts, retries, pacing,
public-address restrictions, and robots policy. Identical destination URLs are
fetched once and assessed for both purposes. Every check records original/final
URLs, observed HTTP status when available, status, and evidence.

An open description needs expected job identity and meaningful description
content, preferring JobPosting, article/main, and explicit description content.
Navigation, footer text, the expected title, and application-form questions cannot
substitute for a description. Form contents remain available only for application
verification, not description extraction.
Identity uses matching JobPosting JSON-LD or expected title plus job ID or employer
evidence; a redirect to another identified requisition is unverified even if its
title is the same. An application destination requires a matching job-specific
application form. HTTP 200 or a description alone is never sufficient.

When the source supplies only a description URL, validator version 4 inspects
Apply links or known embedded application frames and follows up to three further
public, permitted destinations. It verifies the resulting form without submitting
anything. An inline form on the description page also qualifies. A missing form,
JavaScript-only apply action, generic application destination, or required login
remains unverified. Source and final application URLs remain separate in records.

Explicit closure text, HTTP 404/410, expired JobPosting `validThrough`, and a
redirect to a recognizable generic careers page produce closed evidence.
Malformed URLs, wrong-job redirects, missing descriptions, login requirements,
robots restrictions, access challenges, timeouts, 429s, and server failures are
unverified. An unverified destination cannot establish closure. Original employer
posting dates are never guessed from a page's crawl/update timestamp.

JavaScript-only job pages may remain unverified even when a structured source
provides a good description. Robots restrictions are not bypassed. When a
destination changes to another job or employer, automatic verification is
withheld. These limitations are part of the saved per-listing evidence and live
report; manual review or a permitted documented detail API can resolve them.
