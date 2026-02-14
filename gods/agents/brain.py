"""
Gods Platform - Brain Module (Dynamic API Version)
Manages LLM instances using runtime configuration.
"""
from gods.config import runtime_config
from langchain_core.messages import AIMessage


class GodBrain:
    """
    Inference Engine using OpenRouter API.
    Model settings are fetched from runtime_config.
    """
    def __init__(self, agent_id: str = "default", project_id: str = None):
        self.agent_id = agent_id
        self.project_id = project_id
        
    def get_llm(self):
        """Dynamically build the LLM based on current config"""
        # Delay import to avoid heavy optional deps at module import time.
        from langchain_openai import ChatOpenAI
        
        # Get current project's agent settings
        current_project = self.project_id or getattr(runtime_config, 'current_project', 'default')
        projects = getattr(runtime_config, 'projects', {})
        proj = projects.get(current_project)
        
        if proj and hasattr(proj, 'agent_settings') and self.agent_id in proj.agent_settings:
            model = proj.agent_settings[self.agent_id].model
        else:
            model = "stepfun/step-3.5-flash:free"
        
        api_key = runtime_config.openrouter_api_key
        
        return ChatOpenAI(
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

    def think(self, context: str) -> str:
        """Perform inference"""
        if not runtime_config.openrouter_api_key:
            return "❌ ERROR: OPENROUTER_API_KEY is not set. Please configure via settings."

        try:
            llm = self.get_llm()
            response = llm.invoke(context)
            return response.content
        except Exception as e:
            return f"Error in reasoning: {str(e)}"

    def think_with_tools(self, messages: list, tools: list) -> AIMessage:
        """Perform inference with official structured tool-calling."""
        if not runtime_config.openrouter_api_key:
            return AIMessage(content="❌ ERROR: OPENROUTER_API_KEY is not set. Please configure via settings.")

        try:
            llm = self.get_llm().bind_tools(tools)
            response = llm.invoke(messages)
            if isinstance(response, AIMessage):
                return response
            return AIMessage(content=str(getattr(response, "content", response)))
        except Exception as e:
            return AIMessage(content=f"Error in reasoning: {str(e)}")
    
    def __repr__(self):
        current_project = self.project_id or runtime_config.current_project
        proj = runtime_config.projects.get(current_project)
        model = "default"
        if proj and self.agent_id in proj.agent_settings:
            model = proj.agent_settings[self.agent_id].model
        return f"GodBrain(agent={self.agent_id}, project={current_project}, model={model})"
