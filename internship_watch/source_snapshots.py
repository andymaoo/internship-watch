"""Atomic local copies of complete collections, shared without duplicate requests.

These are source observations, never evidence that an individual job is open.
Expired, missing, malformed and incompatible snapshots fail visibly.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from datetime import datetime, timezone

from .sources import SourceError


def source_key(source):
    return hashlib.sha256(json.dumps(source,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def snapshot_collector(config, collector):
    options = config.get('source_snapshots')
    if not options:
        return collector
    mode = options.get('mode')
    age = options.get('max_age_seconds', 600)
    if mode not in {'read','write'} or not isinstance(age,int) or not 60 <= age <= 3600:
        raise ValueError('Invalid source snapshot mode or freshness interval')
    directory = Path(options['directory'])
    ids = set(options['sources'])
    observations = {}
    if mode == 'write':
        directory.mkdir(parents=True,exist_ok=True,mode=0o750)

    def wrapped(source, client):
        if source['id'] not in ids:
            return collector(source,client)
        key = source_key(source)
        path = directory / (key + '.json')
        if mode == 'read':
            try:
                payload=json.loads(path.read_text(encoding='utf-8'))
                elapsed=time.time()-payload['collected_at']
                if payload['version']!=1 or payload['source_key']!=key or not 0<=elapsed<=age:
                    raise ValueError('expired or incompatible')
                jobs=payload['jobs']
                if not isinstance(jobs,list) or any(not isinstance(j,dict) or not j.get('source_id') or not j.get('title') for j in jobs):
                    raise ValueError('invalid collection')
            except (OSError,ValueError,KeyError,TypeError) as exc:
                raise SourceError('Shared collection unavailable/stale; producer must complete a fresh poll') from exc
            observations[source['id']]=dict(collected_at=datetime.fromtimestamp(payload['collected_at'],timezone.utc).isoformat(timespec='seconds'),via='shared_snapshot')
            return jobs
        jobs=collector(source,client)
        # Collection failures never overwrite the last successful observation.
        payload=dict(version=1,source_key=key,collected_at=time.time(),jobs=jobs)
        observations[source['id']]=dict(collected_at=datetime.fromtimestamp(payload['collected_at'],timezone.utc).isoformat(timespec='seconds'),via='direct_collection')
        fd,name=tempfile.mkstemp(dir=directory,prefix='.snapshot-')
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as handle:
                os.fchmod(handle.fileno(),0o600) if hasattr(os,'fchmod') else None
                json.dump(payload,handle,ensure_ascii=False)
                handle.flush();os.fsync(handle.fileno())
            os.replace(name,path)
        finally:
            Path(name).unlink(missing_ok=True)
        return jobs
    wrapped.observations = observations
    return wrapped
