"""Offline tests for opt-in model-version logging in m1b_live.run_trial.

No Solari, browser, or OpenAI calls: the agent, browser session, and Solari
client are fakes, and every HTTP request goes to an httpx.MockTransport.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs

import httpx

import m1b_live
from browser_use.llm.messages import UserMessage
from m1b_campaign import CampaignInfrastructureError, validate_trial

SHOP_URL = "https://shop.invalid/?pt_token=redacted"
_RealAsyncClient = httpx.AsyncClient


class FakeSolari:
    def __init__(self) -> None:
        self.sessions = SimpleNamespace(
            create=self._create,
            release_and_wait=self._noop,
            get_replay_url=self._replay,
        )

    async def _create(self, recording: bool):
        return SimpleNamespace(id="session-1", cdp_endpoint="fake-endpoint")

    async def _noop(self, session_id: str) -> None:
        return None

    async def _replay(self, session_id: str) -> str:
        return "replay-ready"


class FakeBrowserSession:
    def __init__(self, cdp_url: str) -> None:
        self.cdp_url = cdp_url

    async def stop(self) -> None:
        return None


class FakeAgent:
    """Makes `calls` LLM calls through the real browser-use ChatOpenAI, honoring the stop callback."""

    calls = 5
    raise_on_stop = False
    instances: list["FakeAgent"] = []

    def __init__(self, task, llm, browser_session, register_should_stop_callback=None) -> None:
        self.llm = llm
        self.should_stop = register_should_stop_callback
        self.calls_made = 0
        FakeAgent.instances.append(self)

    async def run(self, max_steps: int) -> None:
        for _ in range(FakeAgent.calls):
            if self.should_stop is not None and await self.should_stop():
                if FakeAgent.raise_on_stop:
                    raise InterruptedError
                return
            await self.llm.ainvoke([UserMessage(content="next step")])
            self.calls_made += 1


class RunTrialModelLogTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.log_path = Path(self._tmp.name) / "model_calls.jsonl"
        self.versions: list[str | None] = []
        FakeAgent.instances = []
        FakeAgent.calls = 5
        FakeAgent.raise_on_stop = False

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/chat/completions"):
            version = self.versions.pop(0) if self.versions else "gpt-5-2025-08-07"
            body = {
                "id": f"chatcmpl-{len(self.versions)}",
                "object": "chat.completion",
                "created": 0,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
            if version is not None:
                body["model"] = version
            return httpx.Response(200, json=body)
        if parse_qs(request.url.query.decode()).get("oracle") == ["state"]:
            return httpx.Response(200, json={"passed": True, "stage": "review", "events": ["review_reached"]})
        return httpx.Response(404, json={"error": "not found"})

    async def run_trial(self, **kwargs):
        handler = self.handler

        class MockedAsyncClient(_RealAsyncClient):
            def __init__(self, *args, **client_kwargs) -> None:
                client_kwargs["transport"] = httpx.MockTransport(handler)
                super().__init__(*args, **client_kwargs)

        with patch.object(httpx, "AsyncClient", MockedAsyncClient), patch.object(
            m1b_live, "Agent", FakeAgent
        ), patch.object(m1b_live, "BrowserSession", FakeBrowserSession), patch.dict(
            os.environ, {"OPENAI_API_KEY": "test-not-a-real-key", "OPENAI_BASE_URL": "https://llm.invalid/v1"}
        ):
            return await m1b_live.run_trial(FakeSolari(), SHOP_URL, ("review_rollback",), **kwargs)

    def rows(self) -> list[dict]:
        return [json.loads(line) for line in self.log_path.read_text(encoding="utf-8").splitlines()]

    def test_real_browser_use_api_accepts_the_wiring(self) -> None:
        import inspect

        from browser_use import Agent, ChatOpenAI

        self.assertIn("register_should_stop_callback", inspect.signature(Agent.__init__).parameters)
        self.assertIn("http_client", ChatOpenAI.__dataclass_fields__)

    async def test_default_path_is_unchanged(self) -> None:
        FakeAgent.calls = 0
        trial = await self.run_trial()
        self.assertIsNone(trial.model_version_valid)
        self.assertIsNone(trial.error)
        self.assertTrue(trial.passed)
        self.assertIsNone(FakeAgent.instances[0].should_stop)
        self.assertIsNone(FakeAgent.instances[0].llm.http_client)
        self.assertFalse(self.log_path.exists())

    async def test_stable_version_logs_every_call_and_stays_valid(self) -> None:
        trial = await self.run_trial(model_version_log_path=self.log_path)
        rows = self.rows()
        calls = [r for r in rows if r["record_type"] == "model_call"]
        self.assertEqual(len(calls), 5)
        self.assertEqual({r["returned_version"] for r in calls}, {"gpt-5-2025-08-07"})
        self.assertEqual({r["requested_model"] for r in calls}, {m1b_live.MODEL})
        self.assertEqual(len({r["run_id"] for r in calls}), 1)
        self.assertEqual(rows[-1]["record_type"], "model_version_summary")
        self.assertTrue(trial.model_version_valid)
        self.assertIsNone(trial.error)
        validate_trial(trial)

    async def test_restart_policy_stops_agent_and_invalidates_trial(self) -> None:
        self.versions = ["gpt-5-2025-08-07", "gpt-5-2025-08-07", "gpt-5-2026-01-15"]
        trial = await self.run_trial(model_version_log_path=self.log_path, model_version_policy="restart")
        self.assertEqual(FakeAgent.instances[0].calls_made, 3, "agent stopped after the change")
        self.assertTrue(trial.error.startswith("ModelVersionChanged"))
        self.assertFalse(trial.model_version_valid)
        with self.assertRaises(CampaignInfrastructureError):
            validate_trial(trial)

    async def test_restart_reports_cause_when_agent_raises_on_stop(self) -> None:
        FakeAgent.raise_on_stop = True
        self.versions = ["gpt-5-2025-08-07", None]
        trial = await self.run_trial(model_version_log_path=self.log_path)
        self.assertTrue(trial.error.startswith("ModelVersionMissing"))
        self.assertFalse(trial.model_version_valid)

    async def test_mark_invalid_policy_keeps_going_and_flags_trial(self) -> None:
        self.versions = ["gpt-5-2025-08-07", "gpt-5-2026-01-15"]
        trial = await self.run_trial(model_version_log_path=self.log_path, model_version_policy="mark_invalid")
        self.assertEqual(FakeAgent.instances[0].calls_made, 5)
        self.assertIsNone(trial.error)
        self.assertFalse(trial.model_version_valid)
        summary = self.rows()[-1]
        self.assertFalse(summary["run_valid"])
        self.assertEqual(summary["invalid_reasons"], ["model_version_changed"])


if __name__ == "__main__":
    unittest.main()
