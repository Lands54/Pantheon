from __future__ import annotations

from gods.hermes.facade import HermesClient


class _Resp:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_hermes_client_route(monkeypatch):
    seen = {}

    def fake_request(method, url, json=None, timeout=0, **kwargs):
        seen["method"] = method
        seen["url"] = url
        seen["json"] = json
        seen["timeout"] = timeout
        return _Resp({"ok": True, "result": {"status_code": 200, "result": {"state_patch": {"x": 1}}}})

    monkeypatch.setattr("requests.request", fake_request)

    c = HermesClient(base_url="http://localhost:8000", timeout_sec=12)
    out = c.route(
        project_id="p1",
        caller_id="ground",
        target_agent="fire_god",
        function_id="check_fire_speed",
        payload={"v": 3},
        mode="sync",
    )
    assert out.get("ok") is True
    assert seen["method"] == "POST"
    assert seen["url"].endswith("/hermes/route")
    assert seen["json"]["target_agent"] == "fire_god"
    assert seen["timeout"] == 12


def test_hermes_client_wait_job(monkeypatch):
    seq = [
        {"project_id": "p1", "job": {"status": "queued"}},
        {"project_id": "p1", "job": {"status": "running"}},
        {"project_id": "p1", "job": {"status": "succeeded", "result": {"ok": True}}},
    ]

    def fake_get_job(self, project_id, job_id):
        return seq.pop(0)

    monkeypatch.setattr(HermesClient, "get_job", fake_get_job)
    c = HermesClient()
    out = c.wait_job("p1", "job_1", timeout_sec=5, poll_sec=0.01)
    assert out["job"]["status"] == "succeeded"
