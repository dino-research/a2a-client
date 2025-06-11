"""
Prompts and instructions for the Gemini Research Agent.
Contains all system prompts and response templates.
"""

from datetime import datetime
from typing import Dict, Any


def get_research_prompt(query: str) -> str:
    """
    Generate the main research prompt for Gemini with grounded search.
    
    Args:
        query (str): User's question/query
        
    Returns:
        str: Formatted prompt for Gemini API
    """
    current_date = datetime.now().strftime("%B %d, %Y")
    
    return f"""Tìm hiểu và trả lời câu hỏi sau bằng tiếng Việt: {query}

Hướng dẫn:
- Sử dụng Google Search để tìm thông tin mới nhất và chính xác
- Ngày hiện tại là {current_date}
- Cung cấp câu trả lời chi tiết và hữu ích
- Nếu là câu hỏi về thời tiết, hãy tập trung vào dữ liệu thời gian thực
- Nếu là câu hỏi về tin tức, hãy cung cấp thông tin cập nhật nhất
- Trích dẫn nguồn khi có thể
- Trả lời bằng tiếng Việt một cách tự nhiên và dễ hiểu"""


def get_error_message(error: str) -> str:
    """
    Generate error message in Vietnamese.
    
    Args:
        error (str): Error description
        
    Returns:
        str: Formatted error message
    """
    return f"Xin lỗi, đã xảy ra lỗi khi tìm kiếm thông tin: {error}"


def get_system_instructions() -> Dict[str, Any]:
    """
    Get system-wide instructions and configurations.
    
    Returns:
        Dict[str, Any]: System instructions and configurations
    """
    return {
        "agent_description": "Gemini Research Agent using Google Agent Development Kit",
        "supported_languages": ["vi", "en"],
        "primary_language": "vi",
        "search_tools": ["google_search"],
        "response_format": "markdown",
        "temperature": 0.2,
        "max_tokens": 4096,
        "streaming": True
    }


def get_model_config() -> Dict[str, Any]:
    """
    Get Gemini model configuration.
    
    Returns:
        Dict[str, Any]: Model configuration parameters
    """
    return {
        "tools": [{"google_search": {}}],
        "temperature": 0.2,
        "top_p": 0.95,
        "top_k": 40,
        "candidate_count": 1,
        "max_output_tokens": 4096,
        "stop_sequences": []
    }


# Template messages for different scenarios
WELCOME_MESSAGE = """Xin chào! Tôi là trợ lý AI được hỗ trợ bởi Google Gemini và Agent Development Kit. 
Tôi có thể giúp bạn tìm kiếm thông tin, trả lời câu hỏi và nghiên cứu các chủ đề khác nhau. 
Hãy đặt câu hỏi cho tôi!"""

NO_QUERY_MESSAGE = "Xin lỗi, tôi không nhận được câu hỏi nào từ bạn. Vui lòng đặt câu hỏi để tôi có thể giúp đỡ."

PROCESSING_MESSAGE = "Đang xử lý câu hỏi của bạn và tìm kiếm thông tin..."

SUCCESS_MESSAGE_TEMPLATE = "Đã hoàn thành tìm kiếm và phân tích {source_count} nguồn thông tin."

# Event type descriptions for streaming
EVENT_DESCRIPTIONS = {
    "generate_query": "Generating search queries",
    "web_research": "Researching information from web sources", 
    "reflection": "Analyzing and reflecting on gathered information",
    "finalize_answer": "Finalizing and formatting the response",
    "message": "Sending final response",
    "error": "Error occurred during processing"
}


def get_health_check_response() -> Dict[str, Any]:
    """
    Get health check response data.
    
    Returns:
        Dict[str, Any]: Health check information
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "agent": "gemini_research_agent",
        "version": "1.0.0",
        "framework": "google_adk",
        "capabilities": [
            "web_search",
            "vietnamese_responses", 
            "real_time_information",
            "source_citation",
            "streaming_responses"
        ]
    }


def get_api_description() -> Dict[str, Any]:
    """
    Get API description and metadata.
    
    Returns:
        Dict[str, Any]: API description
    """
    return {
        "name": "Gemini Research Agent API",
        "description": "AI research assistant powered by Google Agent Development Kit",
        "version": "1.0.0",
        "framework": "Google ADK + Gemini API",
        "features": [
            "Real-time web search integration",
            "Vietnamese language support",
            "Streaming responses",
            "Source attribution",
            "Weather and news queries",
            "General knowledge Q&A"
        ],
        "endpoints": {
            "/assistants/{id}/runs": "Create and stream research responses",
            "/health": "Health check",
            "/docs": "API documentation"
        }
    } 