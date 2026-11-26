from unittest.mock import Mock
import json
import pytest
from internship_watch.source_snapshots import snapshot_collector
from internship_watch.sources import SourceError

def configs(tmp_path):
    shared=dict(directory=str(tmp_path),sources=['board'],max_age_seconds=600)
    return ({'source_snapshots':shared|{'mode':'write'}},{'source_snapshots':shared|{'mode':'read'}})

def test_shared_collection_reuses_raw_excluded_and_included_rows(tmp_path):
    write,read=configs(tmp_path)
    jobs=[dict(source_id='1',title='Senior Consultant'),dict(source_id='2',title='New Grad Consultant')]
    upstream=Mock(return_value=jobs);network=Mock(side_effect=AssertionError('duplicate request'))
    source=dict(id='board',type='greenhouse',slug='observed')
    assert snapshot_collector(write,upstream)(source,None)==jobs
    assert snapshot_collector(read,network)(source,None)==jobs
    network.assert_not_called()

def test_failure_retains_snapshot_but_staleness_and_source_change_fail(tmp_path):
    write,read=configs(tmp_path);source=dict(id='board',slug='one')
    snapshot_collector(write,Mock(return_value=[]))(source,None)
    with pytest.raises(RuntimeError):snapshot_collector(write,Mock(side_effect=RuntimeError('outage')))(source,None)
    assert snapshot_collector(read,Mock())(source,None)==[]
    with pytest.raises(SourceError):snapshot_collector(read,Mock())(source|{'slug':'two'},None)
    path=next(tmp_path.glob('*.json'));data=json.loads(path.read_text());data['collected_at']-=601;path.write_text(json.dumps(data))
    with pytest.raises(SourceError):snapshot_collector(read,Mock())(source,None)

def test_missing_corrupt_snapshot_and_unshared_source(tmp_path):
    _,read=configs(tmp_path);network=Mock(return_value=[])
    with pytest.raises(SourceError):snapshot_collector(read,network)({'id':'board'},None)
    assert snapshot_collector(read,network)({'id':'other'},None)==[]
    network.assert_called_once()

def test_per_source_cadence_survives_restart_without_repolling(tmp_path,monkeypatch):
    from internship_watch.runner import run_once
    monkeypatch.setattr('internship_watch.runner.heartbeat',Mock())
    cfg=dict(database=str(tmp_path/'cadence.sqlite3'),sources=[{'id':'slow'},{'id':'fast'}],source_poll_seconds={'slow':1800},validation_budget=0)
    collector=Mock(return_value=[])
    run_once(cfg,collector=collector,client=Mock(),sender=Mock())
    assert collector.call_count==2
    result=run_once(cfg,collector=collector,client=Mock(),sender=Mock())
    assert collector.call_count==3
    assert result['sources']['slow']['status']=='deferred'
    assert result['sources']['fast']['status']=='ok'

def test_snapshot_source_health_keeps_actual_collection_time(tmp_path):
    from internship_watch.storage import Store
    store=Store(tmp_path/'jobs.sqlite3')
    with store.transaction():store.record_source('board',count=3,observed_at='2026-01-01T00:00:00+00:00')
    assert store.source_state('board')['last_success']=='2026-01-01T00:00:00+00:00'
    assert store.source_state('board')['last_attempt']!='2026-01-01T00:00:00+00:00'
    store.close()


def test_producer_retries_overlap_without_waiting_full_poll(monkeypatch):
    from internship_watch import cli
    from internship_watch.locking import AlreadyRunning
    monkeypatch.setattr(cli,'load_config',lambda _:dict(poll_seconds=300))
    run=Mock(side_effect=[AlreadyRunning(),{}]);monkeypatch.setattr(cli,'run_once',run)
    monkeypatch.setattr(cli.time,'monotonic',lambda:0)
    delays=[]
    def sleep(seconds):
        delays.append(seconds)
        if len(delays)==2:raise KeyboardInterrupt
    monkeypatch.setattr(cli.time,'sleep',sleep)
    with pytest.raises(KeyboardInterrupt):cli.main(['--config','unused','daemon'])
    assert run.call_count==2
    assert delays==[15,300]
