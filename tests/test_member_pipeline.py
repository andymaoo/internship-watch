import json
from unittest.mock import Mock

import pytest

from internship_watch.delivery import configured_sender
from internship_watch.runner import run_once
from internship_watch.storage import Store


def job(i, title, location='New York, NY', employment=''):
    return dict(source_id=str(i), employer='Example', title=title, location=location,
                employment_type=employment,
                description_url=f'https://job-boards.greenhouse.io/example/jobs/{i}')


def check(j, client):
    return dict(status='open', posting_status='open', application_status='unverified',
                final_description_url=j['description_url'], checks=[])


def test_full_member_pipeline_retry_and_restart(tmp_path, monkeypatch):
    cfg = dict(database=str(tmp_path/'member.sqlite3'), member_feed=True,
               notifications={'channel':'discord'}, sources=[{'id':'test'}], validation_budget=20)
    legacy = "https://discord.com/api/webhooks/123/personal"
    base = "https://discord.com/api/webhooks/456/"
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", legacy)
    monkeypatch.setenv("MEMBER_DISCORD_WEBHOOKS_JSON", json.dumps({"new-grad-swe":base+"swe"}))
    response = Mock(status_code=200)
    response.json.return_value = {"id":"receipt"}
    post = Mock(return_value=response)
    beat = Mock()
    monkeypatch.setattr("internship_watch.delivery.requests.post",post)
    monkeypatch.setattr("internship_watch.runner.heartbeat",beat)
    seed = [job(1,'Software Engineer Intern')]
    current = seed + [job(2,'Software Engineer - New Grad','Remote'),
                      job(3,'Investment Banking Summer Analyst',employment='Internship'),
                      job(4,'Software Engineer Intern','Remote - Canada only'),
                      job(5,'Junior Software Engineer')]
    def run(rows):
        return run_once(cfg,collector=lambda *_:rows,client=Mock(),validator=check,
                        sender=configured_sender(cfg))
    run(seed)
    post.assert_not_called()
    result = run(current)
    assert result['delivery'] == {'delivered':1,'failed':0,'unconfigured':1}
    assert post.call_args.args[0] == base+'swe'
    assert 'New grad opening' in post.call_args.kwargs['json']['content']
    assert 'location eligibility unspecified' in post.call_args.kwargs['json']['content']
    store=Store(cfg['database'])
    with store.transaction():
        store.db.execute("UPDATE outbox SET next_attempt='2000-01-01' WHERE status='pending'")
    store.close()
    monkeypatch.setenv("MEMBER_DISCORD_WEBHOOKS_JSON", json.dumps({"new-grad-swe":base+"swe","intern-ib":base+"ib"}))
    run(current)
    assert post.call_count == 2 and post.call_args.args[0] == base+'ib'
    run(current)
    assert post.call_count == 2
    beat.assert_not_called()


def test_cannot_switch_personal_db_to_member_mode(tmp_path, monkeypatch):
    cfg=dict(database=str(tmp_path/'personal.sqlite3'), sources=[{'id':'test'}],validation_budget=0)
    monkeypatch.setattr("internship_watch.runner.heartbeat",Mock())
    run_once(cfg,collector=lambda *_:[],client=Mock(),sender=Mock())
    with pytest.raises(ValueError,match='fresh dedicated database'):
        run_once(cfg|{'member_feed':True},collector=lambda *_:[],client=Mock(),sender=Mock())
def test_pilot_only_expands_workday_queries_in_copy():
    from internship_watch.member_pilot import PILOT, pilot_config
    sources = [
        dict(id=key, type='workday' if key.startswith('workday-') else 'other',
             queries=['intern'])
        for key in PILOT
    ]
    config = pilot_config({'sources': sources}, 'dedicated.sqlite3')
    assert config['member_feed'] and config['initial_run'] == 'silent'
    assert config['database'] == 'dedicated.sqlite3'
    assert all(row['queries'] == ['intern'] for row in sources)
    assert config['sources'][-1]['id'] == 'workday-truist-member-campus'
    assert config['sources'][-1]['queries'] == ['investment banking']
    for row in config['sources'][:-1]:
        if row['type'] == 'workday':
            assert row['country_scope'] == ['US'] and row['member_opportunities']
            assert {'intern','new grad','graduate program','investment banking summer analyst'} <= set(row['queries'])


def test_workday_member_scope_enriches_exact_early_career_posting():
    from internship_watch.member_evidence import classify_member
    from internship_watch.sources import collect
    from tests.test_platform_sources import BOARD, BothClient, wd_detail, wd_row

    title = "Investment Banking Summer Analyst"
    source = dict(id='wd',type='workday',url=BOARD,employer='Example',
                  queries=['investment banking summer analyst'])
    row = wd_row('R123', title)
    listing = dict(total=1,jobPostings=[row])
    detail = wd_detail()
    detail['jobPostingInfo'].update(title=title,jobDescription=(
        "Our summer internship program provides hands-on training in financial modeling."
    ))
    private = BothClient(listing)
    assert not collect(source, private)[0]['description']
    client = BothClient(listing, detail)
    job = collect(source | {'member_opportunities': True}, client)[0]
    result = classify_member(job)
    assert result['decision'] == 'include'
    assert result['category'] == 'investment_banking'
    assert result['opportunity_type'] == 'internship'
    assert all(call[1]['respect_robots'] for call in client.calls)
