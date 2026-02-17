"""
Gods Platform - Brain Module (Dynamic API Version)
Manages LLM instances using runtime configuration.
"""
import json
import time

from gods.config import runtime_config
from langchain_core.messages import AIMessage
from gods.mnemosyne.compaction import note_llm_token_io
from gods.paths import runtime_debug_dir


class GodBrain:
    """
    Inference Engine using OpenRouter API.
    Model settings are fetched from runtime_config.
    """
    def __init__(self, agent_id: str = "default", project_id: str = None):
        """
        Initializes a new GodBrain instance for a specific agent and project.
        """
        self.agent_id = agent_id
        self.project_id = project_id
    
    def _resolve_model(self) -> str:
        """
        Determines the appropriate LLM model for the agent based on project configuration.
        """
        current_project = self.project_id or getattr(runtime_config, 'current_project', 'default')
        projects = getattr(runtime_config, 'projects', {})
        proj = projects.get(current_project)
        if proj and hasattr(proj, 'agent_settings') and self.agent_id in proj.agent_settings:
            return proj.agent_settings[self.agent_id].model
        return "stepfun/step-3.5-flash:free"

    def _llm_trace_enabled(self) -> bool:
        """
        Checks if LLM tracing is enabled for the current project.
        """
        current_project = self.project_id or getattr(runtime_config, 'current_project', 'default')
        proj = getattr(runtime_config, "projects", {}).get(current_project)
        return bool(getattr(proj, "debug_llm_trace_enabled", True) if proj else True)

    def _serialize_message(self, msg):
        """
        Serializes a message object into a JSON-compatible dictionary for tracing.
        """
        payload = {
            "type": msg.__class__.__name__,
            "content": getattr(msg, "content", None),
            "name": getattr(msg, "name", None),
        }
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls is not None:
            payload["tool_calls"] = tool_calls
        tool_call_id = getattr(msg, "tool_call_id", None)
        if tool_call_id is not None:
            payload["tool_call_id"] = tool_call_id
        additional_kwargs = getattr(msg, "additional_kwargs", None)
        if additional_kwargs:
            payload["additional_kwargs"] = additional_kwargs
        response_metadata = getattr(msg, "response_metadata", None)
        if response_metadata:
            payload["response_metadata"] = response_metadata
        return payload

    def _write_llm_trace(
        self,
        mode: str,
        model: str,
        request_messages: list,
        request_raw: str | None = None,
        tools: list | None = None,
        response_message: AIMessage | None = None,
        error: str | None = None,
        trace_meta: dict | None = None,
    ):
        """
        Writes a trace of the LLM interaction to a persistent log file.
        """
        if not self._llm_trace_enabled():
            return

        meta = trace_meta or {}
        current_project = self.project_id or getattr(runtime_config, 'current_project', 'default')
        trace_dir = runtime_debug_dir(current_project, self.agent_id)
        trace_dir.mkdir(parents=True, exist_ok=True)
        trace_file = trace_dir / "llm_io.jsonl"

        payload = {
            "ts": time.time(),
            "project_id": current_project,
            "agent_id": self.agent_id,
            "pulse_id": meta.get("pulse_id", ""),
            "reason": meta.get("reason", ""),
            "mode": mode,
            "model": model,
            "request_messages": [self._serialize_message(m) for m in request_messages],
            "request_tools": [getattr(t, "name", str(t)) for t in (tools or [])],
        }
        estimated_context_tokens = 0
        for m in request_messages or []:
            estimated_context_tokens += max(1, len(str(getattr(m, "content", "") or "")) // 4)
        payload["estimated_context_tokens"] = int(estimated_context_tokens)
        if request_raw is not None:
            payload["request_raw"] = request_raw
        if response_message is not None:
            payload["response"] = self._serialize_message(response_message)
        if error is not None:
            payload["error"] = str(error)

        with open(trace_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        try:
            prompt_tokens = 0
            total_tokens = 0
            if response_message is not None:
                meta = getattr(response_message, "response_metadata", {}) or {}
                usage = meta.get("token_usage", {}) if isinstance(meta, dict) else {}
                if isinstance(usage, dict):
                    prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
                    total_tokens = int(usage.get("total_tokens", 0) or 0)
            note_llm_token_io(
                current_project,
                self.agent_id,
                mode=mode,
                estimated_context_tokens=estimated_context_tokens,
                prompt_tokens=prompt_tokens,
                total_tokens=total_tokens,
            )
        except Exception:
            pass

    def get_llm(self):
        """
        Dynamically initializes the LangChain ChatOpenAI instance based on configuration.
        """
        # Delay import to avoid heavy optional deps at module import time.
        from langchain_openai import ChatOpenAI
        
        model = self._resolve_model()
        
        api_key = runtime_config.openrouter_api_key
        
        llm = ChatOpenAI(
            model=model,
            openai_api_key=api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0.7,
            max_tokens=4096,
            default_headers={
                "HTTP-Referer": "https://github.com/GodsPlatform",
                "X-Title": "Gods Platform",
            }
        )
        return llm, model

    def think(self, context: str, trace_meta: dict | None = None) -> str:
        """
        Performs a plain text inference Request.
        """
        if not runtime_config.openrouter_api_key:
            return "❌ ERROR: OPENROUTER_API_KEY is not set. Please configure via settings."

        try:
            llm, model = self.get_llm()
            self._write_llm_trace(
                mode="plain",
                model=model,
                request_messages=[],
                request_raw=context,
                response_message=None,
                trace_meta=trace_meta,
            )
            response = llm.invoke(context)
            if isinstance(response, AIMessage):
                self._write_llm_trace(
                    mode="plain",
                    model=model,
                    request_messages=[],
                    request_raw=context,
                    response_message=response,
                    trace_meta=trace_meta,
                )
            return response.content
        except Exception as e:
            try:
                _, model = self.get_llm()
            except Exception:
                model = self._resolve_model()
            self._write_llm_trace(
                mode="plain",
                model=model,
                request_messages=[],
                request_raw=context,
                response_message=None,
                error=str(e),
                trace_meta=trace_meta,
            )
            return f"Error in reasoning: {str(e)}"

    def think_with_tools(self, messages: list, tools: list, trace_meta: dict | None = None) -> AIMessage:
        """
        Performs inference with support for structured tool-calling.
        """
        if not runtime_config.openrouter_api_key:
            return AIMessage(content="❌ ERROR: OPENROUTER_API_KEY is not set. Please configure via settings.")

        try:
            llm_raw, model = self.get_llm()
            self._write_llm_trace(
                mode="tools",
                model=model,
                request_messages=messages,
                request_raw=None,
                tools=tools,
                response_message=None,
                trace_meta=trace_meta,
            )
            llm = llm_raw.bind_tools(tools)
            response = llm.invoke(messages)
            if isinstance(response, AIMessage):
                self._write_llm_trace(
                    mode="tools",
                    model=model,
                    request_messages=messages,
                    request_raw=None,
                    tools=tools,
                    response_message=response,
                    trace_meta=trace_meta,
                )
                return response
            wrapped = AIMessage(content=str(getattr(response, "content", response)))
            self._write_llm_trace(
                mode="tools",
                model=model,
                request_messages=messages,
                request_raw=None,
                tools=tools,
                response_message=wrapped,
                trace_meta=trace_meta,
            )
            return wrapped
        except Exception as e:
            self._write_llm_trace(
                mode="tools",
                model=self._resolve_model(),
                request_messages=messages,
                request_raw=None,
                tools=tools,
                response_message=None,
                error=str(e),
                trace_meta=trace_meta,
            )
            return AIMessage(content=f"Error in reasoning: {str(e)}")
    
    def __repr__(self):
        """
        Returns a string representation of the GodBrain instance.
        """
        current_project = self.project_id or runtime_config.current_project
        proj = runtime_config.projects.get(current_project)
        model = "default"
        if proj and self.agent_id in proj.agent_settings:
            model = proj.agent_settings[self.agent_id].model
        return f"GodBrain(agent={self.agent_id}, project={current_project}, model={model})"
