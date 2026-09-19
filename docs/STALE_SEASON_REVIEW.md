# Unresolved cohort dates

Review snapshot: **2026-09-19 06:22:41 UTC**, using the 180 rows classified as
included with verified description/application destinations in
`work/final-link-audit.json` at that time. Subsequent classification refinements
may change that count. No confirmed past application deadline was found in this
snapshot. An available application form does not establish that a particular
internship cohort is still recruiting.

Two included opportunities need manual confirmation of their recruiting year:

| Employer and role | Evidence | Review needed |
| --- | --- | --- |
| [Evolver — Applied Data Science Intern](https://job-boards.greenhouse.io/evolver/jobs/4254540009) | The feed labels Summer 2026. Employer text describes ten weeks, June through early August, without a year. | Confirm the current cohort and whether applications are being accepted for a future intake. |
| [Phase2 — Software Engineer Intern](http://phase2.applytojob.com/apply/sQXYQC0QJw/Software-Engineer-Intern) | The feed labels Summer 2026. Employer text gives June 3–August 9 without a year. | Confirm the year and whether this remains an active recruiting opportunity. |

These are **potentially stale cohorts, not confirmed closed listings**. Keep them
under review rather than describe them as confirmed current-cohort matches.

Feed seasons also conflict with employer text in ways that make blanket exclusion
of old terms unreliable:

- [Amperesand — Software Intern](https://job-boards.greenhouse.io/amperesand/jobs/4381214009):
  the feed says Winter 2026; employer text explicitly says the internship session
  is Fall 2026.
- [Hiebing — AI Agent Developer Intern](http://hiebing.applytojob.com/apply/GYiQqWe8cL/AI-Agent-Developer-Intern):
  the feed says Summer 2026; employer text specifies an August 2026 start and
  December 2026 end.
- [DRW — Software Developer Intern](https://job-boards.greenhouse.io/drweng/jobs/7992936):
  the feed says Summer 2026; current employer text targets graduation between
  December 2027 and June 2028. The graduation window does not prove an internship
  season, but shows why the feed term alone should not establish currentness.

The user's all-seasons preference keeps seasons broad; it does not resolve these
cohort uncertainties. For a future configurable rule, consider
`past_application_deadline_policy: review`: use only an explicit application
deadline with a year, retain its source and timezone uncertainty, and flag passed
deadlines as ambiguous opportunity eligibility while preserving the separately
observed link status. Candidate offer deadlines, government-form expiration
dates, and inferred season-end dates must not trigger the rule. No such rule or
automatic closure was introduced by this review.
