import json
from unittest.mock import Mock

import pytest

from internship_watch.delivery import configured_sender
from internship_watch.runner import run_once
from tests.test_notification_policy import listing, checked


@pytest.mark.parametrize(("title", "topic"), [
    ("Data Science Intern", "data"),
    ("Software Engineering Intern", "swe"),
    ("Machine Learning Engineer Intern", "ml-ai"),
])
def test_personal_worker_routes_verified_alert_without_legacy_fallback(tmp_path, monkeypatch, title, topic):
    config = dict(database=str(tmp_path/"personal.sqlite3"), sources=[{"id":"one"}],
                  notifications={"category_channels":True})
    monkeypatch.setenv("DISCORD_WEBHOOK_URL","https://discord.com/api/webhooks/123/old")
    monkeypatch.setenv("MEMBER_DISCORD_WEBHOOKS_JSON",json.dumps({
        "intern-"+topic: "https://discord.com/api/webhooks/456/"+topic}))
    response = Mock(status_code=200)
    response.json.return_value = {"id":"receipt"}
    post = Mock(return_value=response)
    monkeypatch.setattr("internship_watch.delivery.requests.post",post)
    monkeypatch.setattr("internship_watch.runner.heartbeat",Mock())
    rows = [listing(1)]
    def run():
        return run_once(config,collector=lambda *_:rows,client=Mock(),
                        validator=lambda job,_:checked(job),sender=configured_sender(config))
    run()
    rows.append(listing(2) | {"title":title})
    assert run()["delivery"]["delivered"] == 1
    assert post.call_args.args[0] == "https://discord.com/api/webhooks/456/"+topic
    run()
    post.assert_called_once()


def test_category_mode_keeps_digests_and_canaries_out_of_category_channels(monkeypatch):
    for key, suffix in [("OPS", "staff"), ("DIGEST", "digest")]:
        monkeypatch.setenv(key+"_DISCORD_WEBHOOK_URL","https://discord.com/api/webhooks/456/"+suffix)
    sender=configured_sender({"notifications":{"category_channels":True}})
    send=Mock(return_value="receipt")
    monkeypatch.setattr(sender,"_send_to",send)
    sender.send({"_delivery_key":"maintenance-canary:week"})
    assert send.call_args.args[0].endswith("/staff")
    sender.send({"_delivery_key":"awaiting:1","digest_type":"awaiting"})
    assert send.call_args.args[0].endswith("/digest")


def test_two_workers_suppress_only_acknowledged_category_duplicates(tmp_path, monkeypatch):
    from internship_watch.storage import Store
    main_db = str(tmp_path/"personal.sqlite3")
    member_db = str(tmp_path/"member.sqlite3")
    base = dict(sources=[{"id":"one"}])
    personal = base | dict(database=main_db, notifications={
        "category_channels":True,"category_peer_database":member_db})
    member = base | dict(database=member_db, member_feed=True,
                         notifications={"category_peer_database":main_db})
    monkeypatch.setenv("MEMBER_DISCORD_WEBHOOKS_JSON",
                       '{"intern-swe":"https://discord.com/api/webhooks/456/swe"}')
    response = Mock(status_code=200)
    response.json.return_value = {"id":"provider-receipt"}
    post = Mock(return_value=response)
    monkeypatch.setattr("internship_watch.delivery.requests.post",post)
    monkeypatch.setattr("internship_watch.runner.heartbeat",Mock())
    rows=[listing(1)]
    def run(cfg):
        return run_once(cfg,collector=lambda *_:rows,client=Mock(),
                        validator=lambda job,_:checked(job),sender=configured_sender(cfg))
    run(personal)
    run(member)
    rows.append(listing(2))
    assert run(member)["delivery"]["delivered"] == 1
    assert run(personal)["delivery"]["deduplicated"] == 1
    run(personal)
    post.assert_called_once()
    store=Store(main_db)
    try:
        row=store.rows("SELECT status,receipt_id,delivered_at FROM outbox")[0]
        assert row == {"status":"suppressed","receipt_id":"provider-receipt","delivered_at":None}
    finally:
        store.close()


def test_missing_main_category_destination_never_posts_to_legacy(monkeypatch):
    from internship_watch.delivery import NotConfigured
    monkeypatch.setenv("DISCORD_WEBHOOK_URL","https://discord.com/api/webhooks/123/old")
    monkeypatch.setenv("MEMBER_DISCORD_WEBHOOKS_JSON","{}")
    sender=configured_sender({"notifications":{"category_channels":True}})
    post=Mock()
    monkeypatch.setattr("internship_watch.delivery.requests.post",post)
    with pytest.raises(NotConfigured):
        sender.send({"_delivery_key":"new:id","_member_route":"intern-data"})
    post.assert_not_called()
