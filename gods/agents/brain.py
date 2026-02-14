"""
Gods Platform - Brain Module (Dynamic API Version)
Manages LLM instances using runtime configuration.
"""
import os
from langchain_openai import ChatOpenAI
from gods.config import runtime_config


class GodBrain:
    """
    Inference Engine using OpenRouter API.
    Model settings are fetched from runtime_config.
    """
    def __init__(self, agent_id: str = "default"):
        self.agent_id = agent_id
        
    def get_llm(self):
        """Dynamically build the LLM based on current config"""
        # Get current project's agent settings
        current_project = runtime_config.current_project
        proj = runtime_config.projects.get(current_project)
        
        if proj and self.agent_id in proj.agent_settings:
            model = proj.agent_settings[self.agent_id].model
        else:
            model = "google/gemini-2.0-flash-exp:free"
        
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
    
    def __repr__(self):
        current_project = runtime_config.current_project
        proj = runtime_config.projects.get(current_project)
        model = "default"
        if proj and self.agent_id in proj.agent_settings:
            model = proj.agent_settings[self.agent_id].model
        return f"GodBrain(agent={self.agent_id}, model={model})"
