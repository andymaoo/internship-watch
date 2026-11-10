from unittest.mock import Mock

import pytest

from internship_watch.delivery import configured_sender, NotConfigured


@pytest.mark.parametrize(("payload", "operational", "destination"), [
    ({}, False, "jobs"),
    ({"digest_type": "initial"}, False, "digest"),
    ({"digest_type": "awaiting"}, False, "digest"),
    ({}, True, "staff"),
    ({"_delivery_key": "maintenance-reminder:week"}, False, "staff"),
])
def test_discord_split(monkeypatch, payload, operational, destination):
    base = "https://discord.com/api/webhooks/123/"
    for name, route in (("DISCORD", "jobs"), ("OPS_DISCORD", "staff"), ("DIGEST_DISCORD", "digest")):
        monkeypatch.setenv(name + "_WEBHOOK_URL", base + route)
    response = Mock(status_code=200)
    response.json.return_value = {"id": "receipt"}
    post = Mock(return_value=response)
    monkeypatch.setattr("internship_watch.delivery.requests.post", post)
    sender = configured_sender({"notifications": {"split_channels": True}})
    assert sender.send(payload, operational=operational) == "receipt"
    assert post.call_args.args[0] == base + destination
    assert post.call_args.kwargs["json"]["allowed_mentions"] == {"parse": []}


@pytest.mark.parametrize(("missing", "payload", "operational"), [
    ("OPS_DISCORD_WEBHOOK_URL", {}, True),
    ("DIGEST_DISCORD_WEBHOOK_URL", {"digest_type": "awaiting"}, False),
])
def test_no_fallback_to_jobs_in_split_mode(monkeypatch, missing, payload, operational):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/123/jobs")
    monkeypatch.delenv(missing, raising=False)
    post = Mock()
    monkeypatch.setattr("internship_watch.delivery.requests.post", post)
    sender = configured_sender({"notifications": {"split_channels": True}})
    with pytest.raises(NotConfigured, match=missing):
        sender.send(payload, operational=operational)
    post.assert_not_called()
