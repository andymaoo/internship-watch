"""Small live contracts and bounded source telemetry, before filtering/storage."""
import hashlib
import json
from urllib.parse import urlsplit


class ContractError(ValueError):
    pass


def source_revision(source):
    return hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()[:20]


def collection_profile(jobs):
    if not isinstance(jobs, list):
        raise ContractError('Collection is not a list')
    identifiers, descriptions, locations, urls = set(), 0, 0, 0
    partial_records = 0
    hosts = set()
    for index, job in enumerate(jobs):
        if not isinstance(job, dict):
            raise ContractError(f'Record {index} is not an object')
        for field in ('source_id', 'title', 'employer'):
            if not isinstance(job.get(field), (str, int)) or not str(job[field]).strip():
                raise ContractError(f'Record {index} lacks a usable {field}')
        identifier = str(job['source_id'])
        if identifier in identifiers:
            raise ContractError(f'Duplicate source identifier at record {index}; check pagination')
        identifiers.add(identifier)
        evidence = job.get('evidence') if isinstance(job.get('evidence'), dict) else {}
        reported_partial = evidence.get('source_partial_records', 0)
        if not isinstance(reported_partial, int) or isinstance(reported_partial, bool) or reported_partial < 0:
            raise ContractError(f'Record {index} has invalid source_partial_records')
        partial_records = max(partial_records, reported_partial)
        descriptions += len(str(job.get('description') or '').strip()) >= 80
        locations += bool(job.get('location') or job.get('locations'))
        good = False
        for field in ('description_url', 'application_url'):
            try:
                parsed = urlsplit(job.get(field) or '')
                if parsed.scheme in ('http', 'https') and parsed.hostname and not (parsed.username or parsed.password):
                    good = True
                    hosts.add(parsed.hostname.lower())
            except (ValueError, TypeError):
                pass
        urls += good
    count = len(jobs)
    return {'count': count, 'description_fraction': descriptions / count if count else 0,
            'location_fraction': locations / count if count else 0,
            'url_fraction': urls / count if count else 0,
            'identity_hash': hashlib.sha256('\n'.join(sorted(identifiers)).encode()).hexdigest(),
            'partial_records': partial_records,
            'hosts': sorted(hosts)[:40]}


def record_sample(store, source, run_id, profile=None, error=None):
    from .storage import dump, now
    store.db.execute('INSERT INTO source_samples(source,revision,run_id,checked_at,profile,error) VALUES(?,?,?,?,?,?)',
                     (source['id'], source_revision(source), run_id, now(), dump(profile) if profile is not None else None,
                      error[:500] if error else None))
    # Eight hours at the configured five-minute polling interval. The separate
    # maintenance DB retains accepted baselines and incident evidence longer.
    store.db.execute('DELETE FROM source_samples WHERE source=? AND id NOT IN '
                     '(SELECT id FROM source_samples WHERE source=? ORDER BY id DESC LIMIT 96)',
                     (source['id'], source['id']))
