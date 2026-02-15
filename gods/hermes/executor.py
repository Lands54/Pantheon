"""Hermes invocation executor (sync + async)."""
from __future__ import annotations

import concurrent.futures
import threading
import time
import uuid
from typing import Any

from gods.hermes.errors import HermesError, HERMES_TIMEOUT
from gods.hermes.limits import HermesLimiter
from gods.hermes.models import InvokeRequest, InvokeResult, JobRecord
from gods.hermes.registry import HermesRegistry
from gods.hermes.router import route_provider
from gods.hermes.schema import validate_schema
from gods.hermes import store
from gods.hermes.events import hermes_events
from gods.hermes.policy import allow_agent_tool_provider


class HermesExecutor:
    """
    Executor component responsible for both synchronous and asynchronous protocol invocations.
    """
    def __init__(self):
        """
        Initializes the executor with registry, limiter, and thread pool.
        """
        self.registry = HermesRegistry()
        self.limiter = HermesLimiter()
        self._pool = concurrent.futures.ThreadPoolExecutor(max_workers=8, thread_name_prefix="hermes")
        self._jobs_lock = threading.Lock()

    def _append_invocation(
        self,
        req: InvokeRequest,
        ok: bool,
        status: str,
        latency_ms: int,
        result: Any = None,
        error: dict | None = None,
        job_id: str = "",
    ):
        """
        Records an invocation result in the persistent store and publishes an event.
        """
        store.append_invocation(
            req.project_id,
            {
                "project_id": req.project_id,
                "caller_id": req.caller_id,
                "name": req.name,
                "mode": req.mode,
                "ok": ok,
                "status": status,
                "latency_ms": latency_ms,
                "result": result,
                "error": error,
                "job_id": job_id,
            },
        )
        hermes_events.publish(
            "protocol_invoked",
            req.project_id,
            {
                "caller_id": req.caller_id,
                "name": req.name,
                "mode": req.mode,
                "ok": ok,
                "status": status,
                "latency_ms": latency_ms,
                "job_id": job_id,
            },
        )

    def invoke_sync(self, req: InvokeRequest) -> InvokeResult:
        """
        Performs a synchronous protocol invocation, including validation and rate limiting.
        """
        start = time.time()
        spec = self.registry.get(req.project_id, req.name)
        if spec.status != "active":
            raise HermesError("HERMES_PROTOCOL_DISABLED", f"Protocol {req.name} is {spec.status}")
        if spec.mode == "async":
            raise HermesError("HERMES_MODE_MISMATCH", "Protocol only supports async mode")
        if spec.provider.type == "agent_tool" and not allow_agent_tool_provider(req.project_id):
            raise HermesError(
                "HERMES_AGENT_TOOL_DISABLED",
                "agent_tool provider invocation is disabled for this project.",
                retryable=False,
            )

        self.limiter.acquire(req.project_id, req.name, spec.limits.max_concurrency, spec.limits.rate_per_minute)
        try:
            validate_schema(req.payload, spec.request_schema)

            future = self._pool.submit(
                route_provider,
                spec,
                req.project_id,
                req.payload,
                int(spec.limits.timeout_sec),
            )
            try:
                provider_result = future.result(timeout=max(1, int(spec.limits.timeout_sec)))
            except concurrent.futures.TimeoutError:
                future.cancel()
                raise HermesError(HERMES_TIMEOUT, f"Invoke timeout after {spec.limits.timeout_sec}s", retryable=True)

            validate_schema(provider_result, spec.response_schema)
            latency_ms = int((time.time() - start) * 1000)
            self._append_invocation(req, ok=True, status="succeeded", latency_ms=latency_ms, result=provider_result)
            return InvokeResult(
                ok=True,
                project_id=req.project_id,
                name=req.name,
                mode="sync",
                result=provider_result,
                latency_ms=latency_ms,
            )
        except HermesError as e:
            latency_ms = int((time.time() - start) * 1000)
            self._append_invocation(req, ok=False, status="failed", latency_ms=latency_ms, error=e.to_dict())
            return InvokeResult(
                ok=False,
                project_id=req.project_id,
                name=req.name,
                mode="sync",
                error=e.to_dict(),
                latency_ms=latency_ms,
            )
        finally:
            self.limiter.release(req.project_id, req.name)

    def _save_job(self, job: JobRecord):
        """
        Saves a job record to the persistent store.
        """
        store.save_job(job.project_id, job.job_id, job.model_dump())

    def _run_job(self, project_id: str, job_id: str):
        """
        Internal worker function that executes an asynchronous job.
        """
        raw = store.load_job(project_id, job_id)
        if not raw:
            return
        job = JobRecord(**raw)
        req = InvokeRequest(
            project_id=job.project_id,
            caller_id=job.caller_id,
            name=job.name,
            mode="sync",
            payload=job.payload,
        )
        job.status = "running"
        job.updated_at = time.time()
        self._save_job(job)
        hermes_events.publish(
            "job_updated",
            job.project_id,
            {"job_id": job.job_id, "name": job.name, "status": job.status},
        )

        result = self.invoke_sync(req)
        job.updated_at = time.time()
        if result.ok:
            job.status = "succeeded"
            job.result = result.result
            job.error = None
        else:
            job.status = "failed"
            job.result = None
            job.error = result.error
        self._save_job(job)
        hermes_events.publish(
            "job_updated",
            job.project_id,
            {"job_id": job.job_id, "name": job.name, "status": job.status},
        )

        # also write async envelope invocation
        self._append_invocation(
            InvokeRequest(**{
                "project_id": job.project_id,
                "caller_id": job.caller_id,
                "name": job.name,
                "mode": "async",
                "payload": job.payload,
            }),
            ok=result.ok,
            status=job.status,
            latency_ms=result.latency_ms,
            result=result.result,
            error=result.error,
            job_id=job.job_id,
        )

    def invoke_async(self, req: InvokeRequest) -> InvokeResult:
        """
        Performs an asynchronous protocol invocation by creating a background job.
        """
        spec = self.registry.get(req.project_id, req.name)
        if spec.mode == "sync":
            raise HermesError("HERMES_MODE_MISMATCH", "Protocol only supports sync mode")

        job = JobRecord(
            job_id=f"job_{uuid.uuid4().hex[:16]}",
            project_id=req.project_id,
            caller_id=req.caller_id,
            name=req.name,
            payload=req.payload,
            status="queued",
        )
        self._save_job(job)
        hermes_events.publish(
            "job_updated",
            job.project_id,
            {"job_id": job.job_id, "name": job.name, "status": job.status},
        )
        self._pool.submit(self._run_job, job.project_id, job.job_id)
        return InvokeResult(
            ok=True,
            project_id=req.project_id,
            name=req.name,
            mode="async",
            job_id=job.job_id,
        )

    def get_job(self, project_id: str, job_id: str) -> JobRecord | None:
        """
        Retrieves a job record by its ID.
        """
        raw = store.load_job(project_id, job_id)
        if not raw:
            return None
        return JobRecord(**raw)

    def list_invocations(self, project_id: str, name: str = "", limit: int = 100) -> list[dict]:
        """
        Lists invocation records with optional filtering and limit.
        """
        return store.list_invocations(project_id, name=name, limit=limit)
