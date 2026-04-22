"""Unit tests for LiveKit worker registration names.

The MVP uses explicit AgentDispatch, so workers must register with the same
agent_name that scripts/test_client.py dispatches.
"""

from __future__ import annotations

from unittest.mock import patch


class TestPipelineWorkerOptions:
    def test_pipeline_main_registers_default_agent_name(self, monkeypatch):
        from apps.pipeline import agent as pipeline_agent

        monkeypatch.delenv("AGENT_NAME", raising=False)

        with patch.object(pipeline_agent.cli, "run_app") as run_app:
            pipeline_agent.main()

        options = run_app.call_args.args[0]
        assert options.agent_name == "pipeline-agent"

    def test_pipeline_agent_name_can_be_overridden(self, monkeypatch):
        from apps.pipeline import agent as pipeline_agent

        monkeypatch.setenv("AGENT_NAME", "clinic-agent")

        with patch.object(pipeline_agent.cli, "run_app") as run_app:
            pipeline_agent.main()

        options = run_app.call_args.args[0]
        assert options.agent_name == "clinic-agent"


class TestRealtimeWorkerOptions:
    def test_realtime_main_registers_default_agent_name(self, monkeypatch):
        from apps.realtime import agent as realtime_agent

        monkeypatch.delenv("AGENT_NAME", raising=False)

        with patch.object(realtime_agent.cli, "run_app") as run_app:
            realtime_agent.main()

        options = run_app.call_args.args[0]
        assert options.agent_name == "realtime-agent"

    def test_realtime_agent_name_can_be_overridden(self, monkeypatch):
        from apps.realtime import agent as realtime_agent

        monkeypatch.setenv("AGENT_NAME", "clinic-realtime")

        with patch.object(realtime_agent.cli, "run_app") as run_app:
            realtime_agent.main()

        options = run_app.call_args.args[0]
        assert options.agent_name == "clinic-realtime"
