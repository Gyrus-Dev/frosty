import os
import re
from google.adk.runners import Runner
from google.adk.apps.app import App, EventsCompactionConfig


class ADKRunner:
    # Compact when prompt reaches this many tokens — leaves a safe buffer below
    # the model's context limit (e.g. 262144 for gemma4:31b-cloud).
    # Override via COMPACTION_TOKEN_THRESHOLD env var.
    _TOKEN_THRESHOLD = int(os.environ.get("COMPACTION_TOKEN_THRESHOLD", "200000"))

    # Number of raw events to keep un-compacted after a token-based compaction.
    # Each tool round-trip produces ~2 events, so 15 preserves ~7 recent calls.
    _EVENT_RETENTION = int(os.environ.get("COMPACTION_EVENT_RETENTION", "15"))

    def __init__(self, agent, app_name, session_service, memory_service=None):
        self.agent = agent
        self.app_name = app_name
        self.session_service = session_service
        self.memory_service = memory_service

    @staticmethod
    def _to_identifier(name: str) -> str:
        """Convert an arbitrary string to a valid Python identifier for App.name."""
        sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name)
        if sanitized and sanitized[0].isdigit():
            sanitized = "_" + sanitized
        return sanitized or "frosty_app"

    def get_runner(self):
        compaction_config = EventsCompactionConfig(
            # Sliding-window params are required by the schema but we set the
            # interval high so only token-threshold compaction fires in practice.
            compaction_interval=999,
            overlap_size=1,
            token_threshold=self._TOKEN_THRESHOLD,
            event_retention_size=self._EVENT_RETENTION,
        )
        app = App(
            name=self._to_identifier(self.app_name),
            root_agent=self.agent,
            events_compaction_config=compaction_config,
        )
        # Pass the original app_name so Runner uses it for session lookup,
        # overriding the sanitized identifier stored in App.name.
        return Runner(
            app=app,
            app_name=self.app_name,
            session_service=self.session_service,
            memory_service=self.memory_service,
        )
