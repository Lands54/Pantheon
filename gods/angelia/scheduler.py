"""Angelia supervisor: worker lifecycle + timer injector."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

from . import policy, store
from gods.angelia.mailbox import angelia_mailbox
from gods.angelia.metrics import angelia_metrics
from gods.angelia.worker import WorkerContext, worker_loop
from gods.config import runtime_config
from gods.inbox.service import set_wake_enqueue

logger = logging.getLogger("GodsServer")


@dataclass
class _WorkerHandle:
    stop_event: threading.Event
    thread: threading.Thread


class AngeliaSupervisor:
    def __init__(self):
        self._lock = threading.Lock()
        self._running = False
        self._stop_event = threading.Event()
        self._manager_thread: threading.Thread | None = None
        self._workers: dict[tuple[str, str], _WorkerHandle] = {}
        self._last_timer_emit: dict[tuple[str, str], float] = {}

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
            self._stop_event.clear()
            set_wake_enqueue(self.enqueue_event)
            self._manager_thread = threading.Thread(target=self._manager_loop, name="angelia-manager", daemon=True)
            self._manager_thread.start()
            logger.info("Angelia supervisor started")

    def stop(self):
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._stop_event.set()
            workers = list(self._workers.items())
            self._workers.clear()

        for (_, _), h in workers:
            h.stop_event.set()
            h.thread.join(timeout=2.0)

        mt = self._manager_thread
        if mt:
            mt.join(timeout=2.0)
        set_wake_enqueue(None)
        logger.info("Angelia supervisor stopped")

    def notify(self, project_id: str, agent_id: str):
        angelia_mailbox.notify(project_id, agent_id)

    def wake_agent(self, project_id: str, agent_id: str) -> dict:
        self._ensure_worker(project_id, agent_id)
        self.notify(project_id, agent_id)
        return {"project_id": project_id, "agent_id": agent_id, "status": "notified"}

    def enqueue_event(
        self,
        project_id: str,
        agent_id: str,
        event_type: str,
        payload: dict | None = None,
        priority: int | None = None,
        dedupe_key: str = "",
    ) -> dict:
        self._validate_payload(event_type, payload or {})
        pri = int(priority if priority is not None else policy.default_priority(project_id, event_type))
        evt = store.enqueue_event(
            project_id=project_id,
            agent_id=agent_id,
            event_type=event_type,
            priority=pri,
            payload=payload or {},
            dedupe_key=dedupe_key,
            max_attempts=policy.event_max_attempts(project_id),
            dedupe_window_sec=policy.dedupe_window_sec(project_id),
        )
        self._ensure_worker(project_id, agent_id)
        self.notify(project_id, agent_id)
        angelia_metrics.inc("event_enqueued")
        return evt.to_dict()

    def _validate_payload(self, event_type: str, payload: dict):
        et = str(event_type or "").strip()
        if et == "inbox_event":
            if not isinstance(payload, dict):
                raise ValueError("inbox_event payload must be object")
            if not str(payload.get("inbox_event_id", "")).strip():
                raise ValueError("inbox_event payload.inbox_event_id is required")
            return
        if et in {"manual", "system"}:
            if not isinstance(payload, dict):
                raise ValueError(f"{et} payload must be object")
            return
        if et == "timer":
            if not isinstance(payload, dict):
                raise ValueError("timer payload must be object")
            if payload and (str(payload.get("reason", "")).strip() == ""):
                raise ValueError("timer payload.reason is required when payload is not empty")

    def tick_timer_once(self, project_id: str) -> dict:
        emitted = 0
        proj = runtime_config.projects.get(project_id)
        if not proj:
            return {"project_id": project_id, "emitted": 0}
        if not policy.timer_enabled(project_id):
            return {"project_id": project_id, "emitted": 0}
        idle_sec = policy.timer_idle_sec(project_id)
        now = time.time()
        for agent_id in list(getattr(proj, "active_agents", []) or []):
            self._ensure_worker(project_id, agent_id)
            if store.has_queued(project_id, agent_id):
                continue
            key = (project_id, agent_id)
            last = float(self._last_timer_emit.get(key, 0.0))
            if now - last < idle_sec:
                continue
            self.enqueue_event(
                project_id=project_id,
                agent_id=agent_id,
                event_type="timer",
                payload={"reason": "idle_heartbeat", "source": "angelia_timer"},
                priority=policy.default_priority(project_id, "timer"),
                dedupe_key=f"timer:{agent_id}",
            )
            self._last_timer_emit[key] = now
            emitted += 1
        return {"project_id": project_id, "emitted": emitted}

    def list_agent_status(self, project_id: str, active_agents: list[str]) -> list[dict]:
        rows = store.list_agent_status(project_id, active_agents)
        out = []
        for item in rows:
            row = item.to_dict()
            row["queued_events"] = store.count_queued(project_id, item.agent_id)
            out.append(row)
        return out

    def _ensure_worker(self, project_id: str, agent_id: str):
        key = (project_id, agent_id)
        with self._lock:
            h = self._workers.get(key)
            if h and h.thread.is_alive():
                return
            stop_event = threading.Event()
            ctx = WorkerContext(project_id=project_id, agent_id=agent_id, stop_event=stop_event)
            th = threading.Thread(target=worker_loop, args=(ctx,), name=f"angelia-{project_id}-{agent_id}", daemon=True)
            self._workers[key] = _WorkerHandle(stop_event=stop_event, thread=th)
            th.start()

    def _manager_loop(self):
        while not self._stop_event.is_set():
            try:
                enabled_projects: list[str] = []
                for pid, proj in runtime_config.projects.items():
                    if not bool(getattr(proj, "angelia_enabled", True)):
                        continue
                    if bool(getattr(proj, "simulation_enabled", False)):
                        enabled_projects.append(pid)
                        for aid in list(getattr(proj, "active_agents", []) or []):
                            self._ensure_worker(pid, aid)
                        self.tick_timer_once(pid)

                with self._lock:
                    stale = []
                    for (pid, aid), h in self._workers.items():
                        if pid not in enabled_projects:
                            stale.append((pid, aid, h))
                            continue
                        proj = runtime_config.projects.get(pid)
                        if not proj or aid not in list(getattr(proj, "active_agents", []) or []):
                            stale.append((pid, aid, h))
                    for pid, aid, h in stale:
                        h.stop_event.set()
                        h.thread.join(timeout=1.0)
                        self._workers.pop((pid, aid), None)
            except Exception as e:
                logger.warning(f"Angelia manager loop error: {e}")

            self._stop_event.wait(1.0)


angelia_supervisor = AngeliaSupervisor()
