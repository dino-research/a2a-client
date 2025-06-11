"""
Gemini Research Agent using Google Agent Development Kit.
"""

from .server import app
from .prompts import get_research_prompt, get_model_config

__all__ = ["app", "get_research_prompt", "get_model_config"]
