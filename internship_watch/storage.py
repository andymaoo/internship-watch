"""SQLite transactions, conservative identities, and durable delivery history."""
import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .classify import classify
from .google_source import apply_google_eligibility


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def employer_identity(value):
    """Reviewed display-name aliases; never used to merge job identities."""
    name = re.sub(r'[^a-z0-9]', '', str(value or '').casefold())
    return {'andurilindustries':'anduril', 'togetherai':'together',
            'scaleai':'scale', 'tiktok':'bytedance'}.get(name, name)


def custom_greenhouse_identity(job):
    """Recognize an observed custom employer URL, never guess an ATS board."""
    evidence = job.get("evidence") or {}
    if evidence.get("provider") != "greenhouse":
        return None
    match = re.fullmatch(r"gh-([A-Za-z0-9_.-]+)-(\d+)", str(job.get("source_id", "")))
    if not match or match.group(1) in {".", ".."} or str(evidence.get("provider_job_id")) != match.group(2):
        return None
    try:
        parsed = urlsplit(job.get("description_url") or "")
        ids = [value for key, value in parse_qsl(parsed.query) if key == "gh_jid"]
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.hostname in {"boards.greenhouse.io", "job-boards.greenhouse.io"}
                or ids != [match.group(2)]):
            return None
    except (TypeError, ValueError):
        return None
    return match.groups()


def split_statuses(result, historical=False):
    """Keep posting evidence independent of application failures during migration."""
    valid = {"open", "closed", "unverified"}
    checks = result.get("checks", [])
    if historical and result.get("validator_version", 0) < 4:
        return "unverified", "unverified"
    def status(field, kind):
        value = result.get(field)
        if value not in valid:
            matching = [c.get("status") for c in checks if c.get("kind") == kind]
            value = matching[-1] if matching else (result.get("status") if not any(c.get("kind") for c in checks) else "unverified")
        return value if value in valid else "unverified"
    return status("posting_status", "description"), status("application_status", "application")


def url_identity(url):
    """Only exact job URLs/ATS requisitions; never merge by title or company."""
    try:
        u = urlsplit(url or "")
        if u.scheme not in ("http", "https") or not u.hostname:
            return None
        host, path = u.hostname.lower(), re.sub(r"/+", "/", u.path).rstrip("/")
        query = dict(parse_qsl(u.query))
        jibe_boards = {
            'careers.amd.com':'amd','campus-amd.icims.com':'amd','campuscanada-amd.icims.com':'amd',
            'careers-amd.icims.com':'amd','globalcampus-amd.icims.com':'amd',
            'global-external-amd.icims.com':'amd','canadacareers-amd.icims.com':'amd',
            'www.github.careers':'github','careers-githubinc.icims.com':'github'}
        if host in jibe_boards:
            match=re.match(r'/(?:careers-home/)?jobs/(\d+)(?:/|$)',path)
            if match:
                return 'jibe:'+jibe_boards[host]+':'+match[1]
        from .platform_sources import ATLASSIAN_PORTALS
        if host in ATLASSIAN_PORTALS:
            match = re.match(r'/jobs/(\d+)(?:/|$)',path)
            if match:
                return 'atlassian:'+match[1]
        if host=='www.atlassian.com':
            match=re.fullmatch(r'/company/careers/details/(\d+)',path)
            if match:
                return 'atlassian:'+match[1]
        if host=='eeho.fa.us2.oraclecloud.com':
            match=re.fullmatch(r'/hcmUI/CandidateExperience/[a-z-]+/sites/(?:CX_45001|jobsearch)/job/(\d+)',path,re.I)
            if match:
                return 'oracle:CX_45001:'+match[1]
        if host in {'lifeattiktok.com','careers.tiktok.com'}:
            match=re.fullmatch(r'/(?:search/|(?:[a-z-]+/)?position/)(\d+)(?:/detail)?',path)
            if match:
                # These public supplier hosts returned identical content for
                # all 885 shared global posting IDs in the live expansion audit.
                return 'bytedance:'+match[1]
        if host == 'jobs.smartrecruiters.com':
            match = re.fullmatch(r'/([^/]+)/(\d+)(?:-[^/]*)?', path)
            if match:
                return f'smartrecruiters:{match[1].lower()}:{match[2]}'
        if host in {'amazon.jobs', 'www.amazon.jobs'}:
            match = re.match(r'/[a-z-]+/jobs/(\d+)(?:/|$)', path)
            if match:
                return 'amazon:' + match[1]
        if host in {'joinbytedance.com', 'www.joinbytedance.com', 'jobs.bytedance.com'}:
            match = re.fullmatch(r'/(?:search/|(?:en/)?position/)(\d+)(?:/detail)?', path)
            if match:
                return 'bytedance:' + match[1]
        if host == 'nvidia.wd5.myworkdayjobs.com' and '/NVIDIAExternalCareerSite/job/' in path:
            match = re.search(r'_(JR\d+)(?:-\d+)?(?:/apply)?$', path)
            if match:
                return 'workday:nvidia:' + match[1]
        if re.fullmatch(r'[a-z0-9-]+\.wd\d+\.myworkdayjobs\.com', host):
            # Strip only the known locale/apply wrappers. Preserve posting
            # instance suffixes and tenant/site so distinct roles never collapse.
            match = re.fullmatch(r'/(?:[a-z]{2}-[A-Z]{2}/)?([^/]+)/job/(?:[^/]+/)*[^/]+_([^/]+?)(?:/apply)?', path)
            if match:
                return 'workday:' + host + ':' + match[1] + ':' + match[2]
        if host == 'wd1.myworkdaysite.com' and path.startswith('/recruiting/snapchat/snap/job/'):
            match = re.search(r'_([A-Z]\d+[A-Z0-9]*)(?:-\d+)?(?:/apply)?$', path)
            if match:
                return 'snap:' + match[1]
        if host == 'careers.snap.com' and path == '/job' and re.fullmatch(r'[A-Z]\d+[A-Z0-9]*', query.get('id','')):
            return 'snap:' + query['id']
        job_query = any(value for key, value in query.items() if key.casefold() in
                        {"gh_jid", "jobid", "job_id", "job", "jid", "requisitionid", "requisition_id"})
        if host in ("boards.greenhouse.io", "job-boards.greenhouse.io"):
            match = re.fullmatch(r"/([^/]+)/jobs/(\d+)(?:/application)?", path)
            if match:
                return f"gh:{match[1].lower()}:{match[2]}"
            if path == "/embed/job_app" and query.get("for") and query.get("token", "").isdigit():
                return f"gh:{query['for'].lower()}:{query['token']}"
            return None
        if host in ("jobs.lever.co", "jobs.eu.lever.co"):
            match = re.fullmatch(r"/([^/]+)/([0-9a-fA-F-]{36})(?:/apply)?", path)
            if match:
                return f"lever:{match[1].lower()}:{match[2].lower()}"
            return None
        if host == "jobs.ashbyhq.com":
            match = re.fullmatch(r"/([^/]+)/([0-9a-fA-F-]{36})(?:/application)?", path)
            if match:
                return f"ashby:{match[1].lower()}:{match[2].lower()}"
            return None
        # Localized roots and shared application/search pages are not identities.
        # A real requisition query can identify a role on a careers root.
        generic_endings = {"", "career", "careers", "job", "jobs", "search", "apply", "application",
                           "applications", "positions", "openings", "opportunities", "listings"}
        if not job_query and path.lower().rsplit("/", 1)[-1] in generic_endings:
            return None
        kept = [(k, v) for k, v in parse_qsl(u.query)
                if not k.lower().startswith("utm_") and k.lower() not in
                ("lever-source", "gh_src", "trackingid") and not
                (k.lower() in ("source", "ref", "referrer", "src") and v.casefold() == "simplify")]
        # Unknown providers may encode the requisition in ref/source or a SPA
        # fragment. Preserve these unless their tracking semantics are known.
        return urlunsplit(("https", host, path, urlencode(sorted(kept)), u.fragment))
    except ValueError:
        return None


SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY,started_at TEXT NOT NULL,
 finished_at TEXT,status TEXT NOT NULL,summary TEXT);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,employer TEXT NOT NULL,title TEXT NOT NULL,
 category TEXT,location TEXT,description TEXT,employment_type TEXT,posting_date TEXT,
 original_url TEXT,application_url TEXT,final_url TEXT,final_application_url TEXT,
 status TEXT NOT NULL DEFAULT 'unverified',classification TEXT NOT NULL,
 evidence TEXT NOT NULL,payload TEXT NOT NULL,first_seen TEXT NOT NULL,last_seen TEXT NOT NULL,
 last_checked TEXT,next_check TEXT,baseline INTEGER NOT NULL DEFAULT 0,
 posting_status TEXT NOT NULL DEFAULT 'unverified',application_status TEXT NOT NULL DEFAULT 'unverified',
 first_qualifying_at TEXT,notification_decided_at TEXT);
CREATE TABLE IF NOT EXISTS identities(identity TEXT PRIMARY KEY,job_id TEXT NOT NULL REFERENCES jobs(id));
CREATE TABLE IF NOT EXISTS source_records(source TEXT NOT NULL,source_id TEXT NOT NULL,
 job_id TEXT NOT NULL REFERENCES jobs(id),first_seen TEXT NOT NULL,last_seen TEXT NOT NULL,
 payload TEXT NOT NULL,PRIMARY KEY(source,source_id));
CREATE TABLE IF NOT EXISTS observations(id INTEGER PRIMARY KEY,run_id INTEGER,job_id TEXT NOT NULL,
 source TEXT NOT NULL,observed_at TEXT NOT NULL,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS link_checks(id INTEGER PRIMARY KEY,job_id TEXT NOT NULL,
 checked_at TEXT NOT NULL,result TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS source_state(source TEXT PRIMARY KEY,initialized INTEGER NOT NULL DEFAULT 0,
 failures INTEGER NOT NULL DEFAULT 0,empty_runs INTEGER NOT NULL DEFAULT 0,
 last_success TEXT,last_attempt TEXT,last_count INTEGER,last_error TEXT);
CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY,dedupe_key TEXT UNIQUE NOT NULL,
 kind TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending',attempts INTEGER NOT NULL DEFAULT 0,
 next_attempt TEXT NOT NULL,last_error TEXT,delivered_at TEXT,receipt_id TEXT);
CREATE TABLE IF NOT EXISTS digest_jobs(outbox_id INTEGER NOT NULL REFERENCES outbox(id),
 job_id TEXT NOT NULL REFERENCES jobs(id),PRIMARY KEY(outbox_id,job_id),UNIQUE(job_id));
CREATE TABLE IF NOT EXISTS incidents(key TEXT PRIMARY KEY,generation INTEGER NOT NULL DEFAULT 1,
 active INTEGER NOT NULL DEFAULT 1,opened_at TEXT NOT NULL,resolved_at TEXT,detail TEXT);
CREATE TABLE IF NOT EXISTS legacy_seen(source_id TEXT PRIMARY KEY,imported_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS classification_cache(source TEXT NOT NULL,source_id TEXT NOT NULL,
 fingerprint TEXT NOT NULL,result TEXT NOT NULL,last_seen TEXT NOT NULL,PRIMARY KEY(source,source_id));
CREATE INDEX IF NOT EXISTS outbox_due ON outbox(status,next_attempt);
CREATE INDEX IF NOT EXISTS jobs_due ON jobs(next_check);
CREATE INDEX IF NOT EXISTS observations_job ON observations(job_id,observed_at);
CREATE INDEX IF NOT EXISTS observations_source ON observations(job_id,source,id);
CREATE INDEX IF NOT EXISTS link_checks_job ON link_checks(job_id,id);
"""


class Store:
    def __init__(self, path):
        self.classifier_revision = hashlib.sha256(Path(__file__).with_name('classify.py').read_bytes()).hexdigest()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA foreign_keys=ON")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1, 2):
            raise RuntimeError(f"Unsupported database schema {version}")
        self.db.executescript(SCHEMA)
        columns = {r[1] for r in self.db.execute("PRAGMA table_info(jobs)")}
        for name, declaration in {
            "posting_status": "TEXT NOT NULL DEFAULT 'unverified'",
            "application_status": "TEXT NOT NULL DEFAULT 'unverified'",
            "first_qualifying_at": "TEXT", "notification_decided_at": "TEXT",
        }.items():
            if name not in columns:
                self.db.execute(f"ALTER TABLE jobs ADD COLUMN {name} {declaration}")
        if "receipt_id" not in {r[1] for r in self.db.execute("PRAGMA table_info(outbox)")}:
            self.db.execute("ALTER TABLE outbox ADD COLUMN receipt_id TEXT")
        if version < 2:
            self.db.execute("UPDATE jobs SET status='unverified'")
            for row in self.db.execute("SELECT j.id,c.result FROM jobs j JOIN link_checks c ON "
                                       "c.id=(SELECT MAX(id) FROM link_checks WHERE job_id=j.id) "
                                       "WHERE j.last_checked=c.checked_at").fetchall():
                posting, application = split_statuses(json.loads(row["result"]), historical=True)
                combined = "closed" if "closed" in (posting, application) else "open" if posting == application == "open" else "unverified"
                self.db.execute("UPDATE jobs SET posting_status=?,application_status=?,status=? WHERE id=?",
                                (posting, application, combined, row["id"]))
                if json.loads(row["result"]).get("validator_version", 0) < 4:
                    self.db.execute("UPDATE jobs SET next_check=NULL WHERE id=?", (row["id"],))
            # Old data has no recorded first qualification/decision timestamp.
            # Do not manufacture latency measurements from first_seen.
        self.db.execute("PRAGMA user_version=2")
        if not self.db.execute("SELECT 1 FROM meta WHERE key='company_url_aliases_v1'").fetchone():
            # Add aliases to historical rows before new sources arrive. Never
            # merge existing rows or overwrite a conflicting identity/receipt.
            rows = self.db.execute('SELECT id,original_url FROM jobs').fetchall() if 'original_url' in columns else []
            for row in rows:
                identity = url_identity(row['original_url'])
                if identity and identity.startswith(('smartrecruiters:', 'amazon:', 'bytedance:', 'workday:nvidia:', 'snap:')):
                    self.db.execute('INSERT OR IGNORE INTO identities(identity,job_id) VALUES(?,?)', ('url:'+identity,row['id']))
            self.db.execute("INSERT INTO meta VALUES('company_url_aliases_v1',?)", (now(),))
        if {'original_url','application_url'} <= columns and not self.db.execute("SELECT 1 FROM meta WHERE key='platform_url_aliases_v1'").fetchone():
            for row in self.db.execute('SELECT id,original_url,application_url FROM jobs').fetchall():
                original = url_identity(row['original_url'])
                for field in ('original_url','application_url'):
                    identity = url_identity(row[field])
                    if field=='application_url' and original and not original.startswith('https:') and original!=identity:
                        continue
                    if identity and identity.startswith(('workday:','atlassian:','oracle:','bytedance:','jibe:')):
                        self.db.execute('INSERT OR IGNORE INTO identities(identity,job_id) VALUES(?,?)',('url:'+identity,row['id']))
            self.db.execute("INSERT INTO meta VALUES('platform_url_aliases_v1',?)",(now(),))
        self.db.commit()

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def import_legacy(self, path):
        """Unknown historical delivery: suppress old IDs, never label delivered."""
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        ids = data.get("ids")
        if not isinstance(ids, list) or not all(isinstance(x, str) for x in ids):
            raise ValueError("Legacy seen.json must contain a string ids list")
        with self.transaction():
            self.db.executemany("INSERT OR IGNORE INTO legacy_seen VALUES(?,?)", [(x, now()) for x in ids])
            self.db.execute("INSERT OR REPLACE INTO meta VALUES('legacy_import',?)",
                            (dump({"count": len(ids), "seed_run": bool(data.get("seed_run")), "at": now()}),))
        return len(ids)

    def source_state(self, source):
        row = self.db.execute("SELECT * FROM source_state WHERE source=?", (source,)).fetchone()
        return dict(row) if row else {"source": source, "initialized": 0, "failures": 0,
                                    "empty_runs": 0, "last_count": None}

    def classify_cached(self, source, job, filters, classifier=classify):
        """Reuse an unchanged decision; invalidate on any job/filter/code change."""
        fingerprint = hashlib.sha256(dump([self.classifier_revision, filters, job]).encode()).hexdigest()
        sid = str(job['source_id'])
        row = self.db.execute('SELECT fingerprint,result FROM classification_cache WHERE source=? AND source_id=?',
                              (source,sid)).fetchone()
        if row and row['fingerprint']==fingerprint:
            result=json.loads(row['result'])
            self.db.execute('UPDATE classification_cache SET last_seen=? WHERE source=? AND source_id=?',(now(),source,sid))
            return result
        result=classifier(job,filters)
        self.db.execute('INSERT OR REPLACE INTO classification_cache VALUES(?,?,?,?,?)',
                        (source,sid,fingerprint,dump(result),now()))
        return result

    def record_source(self, source, count=None, error=None):
        prior = self.source_state(source)
        stamp = now()
        self.db.execute("INSERT OR IGNORE INTO source_state(source) VALUES(?)", (source,))
        if error:
            self.db.execute("UPDATE source_state SET failures=failures+1,last_attempt=?,last_error=? WHERE source=?",
                            (stamp, error, source))
        else:
            self.db.execute("UPDATE source_state SET initialized=1,failures=0,empty_runs=?,last_attempt=?,"
                            "last_success=?,last_count=?,last_error=NULL WHERE source=?",
                            (prior["empty_runs"] + 1 if count == 0 else 0, stamp, stamp, count, source))
        return self.source_state(source)

    def upsert_job(self, source, job, classification, run_id, baseline=False, filters=None):
        sid, stamp = str(job["source_id"]), now()
        keys = [f"source:{source}:{sid}"]
        description_key = url_identity(job.get("description_url"))
        application_key = url_identity(job.get("application_url"))
        if description_key:
            keys.append("url:" + description_key)
        evidence = job.get('evidence') or {}
        if (evidence.get('provider') == 'eightfold' and evidence.get('domain') == 'nvidia.com' and
                job.get('employer', '').casefold() == 'nvidia' and
                re.fullmatch(r'JR\d+', str(evidence.get('ats_job_id', ''))) and
                job.get('description_url') == 'https://jobs.nvidia.com/careers/job/' + str(evidence.get('provider_job_id'))):
            keys.append('url:workday:nvidia:' + evidence['ats_job_id'])
        known_ats = lambda key: bool(key and key.startswith(("gh:", "lever:", "ashby:", "smartrecruiters:", "workday:", "snap:", "atlassian:", "oracle:", "bytedance:", "jibe:")))
        # Application destinations often share a login/form. Only known ATS
        # requisitions can add an alias; conflicting requisitions cannot merge.
        if application_key and application_key != description_key and known_ats(application_key):
            if not known_ats(description_key):
                keys.append("url:" + application_key)
        found = {r[0] for key in keys for r in self.db.execute("SELECT job_id FROM identities WHERE identity=?", (key,))}
        if len(found) > 1:
            # Conflicting URLs are preserved as separate records for inspection.
            found = {r[0] for r in self.db.execute("SELECT job_id FROM identities WHERE identity=?", (keys[0],))}
            keys = keys[:1]
        jid = next(iter(found), hashlib.sha256(keys[0].encode()).hexdigest()[:24])
        old = self.db.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
        incoming_ats = custom_greenhouse_identity(job)
        prior_ats = custom_greenhouse_identity(json.loads(old["payload"])) if old else None
        if incoming_ats and prior_ats and incoming_ats != prior_ats and not self.db.execute(
                "SELECT 1 FROM identities WHERE identity=?", (keys[0],)).fetchone():
            # A coincident custom URL cannot merge distinct observed ATS boards.
            # Keep the ambiguous URL alias with its first record; the new source
            # identity safely addresses the separate record on subsequent polls.
            keys = keys[:1]
            jid = hashlib.sha256(keys[0].encode()).hexdigest()[:24]
            old = self.db.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
            prior_ats = custom_greenhouse_identity(json.loads(old["payload"])) if old else None
        prior_source = self.db.execute("SELECT payload FROM source_records WHERE source=? AND source_id=?",
                                       (source, sid)).fetchone()
        identity_changed = False
        if prior_source:
            prior_job = json.loads(prior_source["payload"])
            normalized = lambda value: re.sub(r"\W+", " ", str(value or "").casefold()).strip()
            identity_changed = any(normalized(prior_job.get(key)) != normalized(job.get(key))
                                   for key in ("title", "employer"))
        if incoming_ats and prior_ats and incoming_ats != prior_ats:
            identity_changed = True
        if old and employer_identity(old["employer"]) != employer_identity(job.get("employer")):
            identity_changed = True
        legacy = self.db.execute("SELECT 1 FROM legacy_seen WHERE source_id=?", (sid,)).fetchone()
        payload = dict(job)
        # Both reviewed supplier hosts expose the same group index. Retain the
        # readable parent posting when the TikTok mirror has exactly matching
        # content and requisition identity. A changed description is not stale-
        # copied: it must still affect filtering. Keep both raw observations.
        if old and not identity_changed and evidence.get('provider') == 'tiktok':
            parent = json.loads(old['payload'])
            parent_evidence = parent.get('evidence') or {}
            if (parent_evidence.get('provider') == 'bytedance'
                    and evidence.get('provider_job_id') == parent_evidence.get('provider_job_id')
                    and description_key and description_key.startswith('bytedance:')
                    and description_key == url_identity(parent.get('description_url'))
                    and application_key == url_identity(parent.get('application_url'))
                    and all(job.get(field) == parent.get(field) for field in
                            ('title', 'description', 'employment_type', 'locations', 'posting_date'))):
                payload = dict(parent)
        # A community URL alias must not alternate the stored destination with
        # its direct employer record every poll. Preserve the direct payload
        # only for unchanged role identity and already-known exact aliases.
        # Raw community observations are still recorded independently below.
        if old and not identity_changed and evidence.get('provider') == 'simplify':
            direct_payload = json.loads(old['payload'])
            direct_provider = (direct_payload.get('evidence') or {}).get('provider')
            direct_providers = {'greenhouse','lever','ashby','apple','google','eightfold',
                                'smartrecruiters','snap','amazon','rippling','bloomberg','bytedance',
                                'workday','jibe','atlassian','jobvite','oracle','tiktok'}
            incoming_destinations = [url_identity(job.get(field)) for field in ('description_url','application_url') if job.get(field)]
            known_aliases = bool(incoming_destinations) and all(key and self.db.execute(
                'SELECT 1 FROM identities WHERE identity=? AND job_id=?', ('url:'+key,jid)).fetchone()
                for key in incoming_destinations)
            if direct_provider in direct_providers and known_aliases:
                payload = dict(direct_payload)
        def same_destination(before, after):
            if (before or "") == (after or ""):
                return True
            before_key, after_key = url_identity(before), url_identity(after)
            return before_key is not None and before_key == after_key

        # Keep a richer directly obtained description when a feed omits it.
        # A changed role identity needs fresh evidence, even at the same URL.
        if old and not identity_changed and same_destination(old["original_url"], job.get("description_url")):
            old_payload = json.loads(old["payload"])
            if (prior_ats and (job.get("evidence") or {}).get("provider") == "simplify"
                    and old_payload.get("employer", "").casefold() == job.get("employer", "").casefold()
                    and same_destination(old["application_url"], job.get("application_url"))):
                # Exact employer/requisition provenance from the direct board
                # includes the authoritative title, qualifications, employment
                # type and board slug. A community alias/summary cannot erase
                # it. Its untouched raw record is still saved below.
                payload = dict(old_payload)
            for key in ("description", "employment_type", "posting_date"):
                if not payload.get(key) and old_payload.get(key):
                    payload[key] = old_payload[key]
            old_kind = (old_payload.get("evidence") or {}).get("description_kind")
            new_kind = (payload.get("evidence") or {}).get("description_kind")
            same_validated_posting = (old_kind == "validated_destination" and bool(old_payload.get("description")) and
                                      same_destination(old["original_url"], job.get("description_url")))
            retained_google_detail = (same_validated_posting and apply_google_eligibility(
                payload, (old_payload.get("evidence") or {}).get("validated_google_eligibility")))
            if same_validated_posting and (retained_google_detail or not job.get("description") or new_kind == "employer_search_summary"):
                # Employer search summaries omit qualifications. Preserve the
                # richer validated destination across subsequent summary polls.
                payload["description"] = old_payload["description"]
                payload["evidence"] = dict(payload.get("evidence") or {})
                payload["evidence"]["description_kind"] = "validated_destination"
        if filters is not None:
            # Classification must use retained enrichment and today's policy.
            # A sparse source refresh cannot erase a known PhD-only restriction,
            # and yesterday's inclusion cannot override a newly ambiguous role.
            classification = classify(payload, filters)
        decision = classification.get("decision", "ambiguous")
        values = (payload["employer"], payload["title"], classification.get("category"), payload.get("location", ""),
                  payload.get("description", ""), payload.get("employment_type", ""), payload.get("posting_date"),
                  payload.get("description_url", ""), payload.get("application_url", ""), decision,
                  dump(classification), dump(payload), stamp)
        if not old:
            self.db.execute("INSERT INTO jobs(employer,title,category,location,description,employment_type,posting_date,"
                            "original_url,application_url,classification,evidence,payload,last_seen,id,first_seen,baseline)"
                            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", values + (jid, stamp, int(baseline or bool(legacy))))
        else:
            self.db.execute("UPDATE jobs SET employer=?,title=?,category=?,location=?,description=?,employment_type=?,"
                            "posting_date=?,original_url=?,application_url=?,classification=?,evidence=?,payload=?,last_seen=? WHERE id=?",
                            values + (jid,))
            if legacy:
                # Another source may have introduced this canonical job first.
                # Legacy suppression must not depend on collection order.
                self.db.execute("UPDATE jobs SET baseline=1 WHERE id=?", (jid,))
                self.db.execute("UPDATE outbox SET status='cancelled',last_error='Suppressed by imported legacy seen ID' "
                                "WHERE dedupe_key=? AND status='pending'", ("new:" + jid,))
            if identity_changed or not (same_destination(old["original_url"], payload.get("description_url")) and
                    same_destination(old["application_url"], payload.get("application_url"))):
                # Previous validation belongs to the previous destinations.
                # Preserve its historical evidence, but require a new check.
                self.db.execute("UPDATE jobs SET status='unverified',posting_status='unverified',application_status='unverified',final_url=NULL,final_application_url=NULL,"
                                "last_checked=NULL,next_check=NULL WHERE id=?", (jid,))
        if decision == "include":
            self.db.execute("UPDATE jobs SET first_qualifying_at=COALESCE(first_qualifying_at,?) WHERE id=?", (stamp, jid))
        for key in keys:
            self.db.execute("INSERT OR IGNORE INTO identities VALUES(?,?)", (key, jid))
        self.db.execute("INSERT INTO source_records VALUES(?,?,?,?,?,?) ON CONFLICT(source,source_id) DO UPDATE SET "
                        "last_seen=excluded.last_seen,payload=excluded.payload", (source, sid, jid, stamp, stamp, dump(job)))
        snapshot = dump({"job": job, "classification": classification})
        prior_snapshot = self.db.execute(
            "SELECT payload FROM observations WHERE job_id=? AND source=? "
            "AND CAST(json_extract(payload,'$.job.source_id') AS TEXT)=? ORDER BY id DESC LIMIT 1",
            (jid, source, sid)).fetchone()
        if not prior_snapshot or prior_snapshot["payload"] != snapshot:
            # last_seen updates on every poll; history stores changes, not an
            # identical full-board description snapshot every few minutes.
            self.db.execute("INSERT INTO observations(run_id,job_id,source,observed_at,payload) VALUES(?,?,?,?,?)",
                            (run_id, jid, source, stamp, snapshot))
        return jid, old is None

    def record_check(self, jid, result, next_check):
        checked_at = result.get("checked_at") or now()
        self.db.execute("INSERT INTO link_checks(job_id,checked_at,result) VALUES(?,?,?)", (jid, checked_at, dump(result)))
        posting, application = split_statuses(result)
        self.db.execute("UPDATE jobs SET status=?,last_checked=?,next_check=?,final_url=?,final_application_url=?,"
                        "posting_status=?,application_status=? WHERE id=?",
                        (result["status"], checked_at, next_check, result.get("final_description_url"),
                         result.get("final_application_url"), posting, application, jid))

    def queue(self, key, kind, payload):
        self.db.execute("INSERT INTO outbox(dedupe_key,kind,payload,created_at,next_attempt) VALUES(?,?,?,?,?) "
                        "ON CONFLICT(dedupe_key) DO UPDATE SET status='pending',payload=excluded.payload,"
                        "next_attempt=excluded.next_attempt,last_error=NULL WHERE outbox.kind='job' AND outbox.status='cancelled'",
                        (key, kind, dump(payload), now(), now()))

    def incident(self, key, active, detail):
        previous = self.db.execute("SELECT * FROM incidents WHERE key=?", (key,)).fetchone()
        if not active:
            if previous:
                delivered = self.db.execute("SELECT 1 FROM outbox WHERE dedupe_key=? AND status='delivered'",
                    (f"incident:{key}:{previous['generation']}",)).fetchone()
                if previous["active"] and delivered:
                    self.queue(f"recovery:{key}:{previous['generation']}", "incident",
                               {"title": "Internship watcher recovered", "body": f"Resolved incident: {key}. The latest check passed."})
                self.db.execute("UPDATE outbox SET status='cancelled',last_error='Incident recovered before delivery' "
                                "WHERE status='pending' AND dedupe_key=?", (f"incident:{key}:{previous['generation']}",))
            self.db.execute("UPDATE incidents SET active=0,resolved_at=? WHERE key=? AND active=1", (now(), key))
            return
        generation = (previous["generation"] + 1) if previous and not previous["active"] else (previous["generation"] if previous else 1)
        if previous and previous["active"]:
            self.db.execute("UPDATE incidents SET detail=? WHERE key=?", (detail, key))
            return
        if previous:
            self.db.execute("UPDATE outbox SET status='cancelled',last_error='Incident recurred before recovery delivery' "
                            "WHERE status='pending' AND dedupe_key=?", (f"recovery:{key}:{previous['generation']}",))
        self.db.execute("INSERT INTO incidents VALUES(?,?,1,?,NULL,?) ON CONFLICT(key) DO UPDATE SET "
                        "generation=excluded.generation,active=1,opened_at=excluded.opened_at,resolved_at=NULL,detail=excluded.detail",
                        (key, generation, now(), detail))
        self.queue(f"incident:{key}:{generation}", "incident", {"title": "Internship watcher needs attention", "body": detail})

    def rows(self, query, args=()):
        return [dict(r) for r in self.db.execute(query, args)]

    def backup(self, path):
        target = sqlite3.connect(path)
        try:
            self.db.backup(target)
        finally:
            target.close()
