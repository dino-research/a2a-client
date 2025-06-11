"""
Prompts and instructions for the Gemini Research Agent.
Contains all system prompts and response templates.
Cleaned up after refactoring - only actively used functions remain.
"""

from datetime import datetime
from typing import Dict, Any


def get_web_research_prompt(query: str, current_date: str) -> str:
    """
    Generate prompt for web research function.
    
    Args:
        query (str): The search query to research
        current_date (str): Current date string
        
    Returns:
        str: Formatted web research prompt
    """
    return f"""Conduct comprehensive research on: "{query}"

Instructions:
- Use Tavily Search to find the most current and relevant information
- The current date is {current_date}
- Provide detailed information with proper citations
- Focus on factual, verifiable information
- Include multiple sources when possible

Research Query: {query}"""


def get_synthesis_prompt(question: str, research_content: str, current_date: str) -> str:
    """
    Generate prompt for synthesizing final answer.
    
    Args:
        question (str): The original user question
        research_content (str): Combined research findings
        current_date (str): Current date string
        
    Returns:
        str: Formatted synthesis prompt
    """
    return f"""Based on the research findings below, provide a comprehensive answer to the user's question.

User Question: {question}
Current Date: {current_date}

Research Findings:
{research_content}

Instructions:
- Provide a clear, accurate answer in Vietnamese
- Include relevant details and context
- Cite sources when possible
- Be informative but concise
- If the question is about current events or weather, emphasize the most recent information"""


def get_research_agent_instruction() -> str:
    """
    Get the main instruction for the research agent using ADK.
    
    Returns:
        str: Research agent instruction
    """
    return """Bạn là trợ lý nghiên cứu thông minh sử dụng Google Agent Development Kit, chuyên cung cấp thông tin chính xác và cập nhật.

Khi người dùng đặt câu hỏi:
1. Sử dụng tool `conduct_comprehensive_research` để tìm kiếm thông tin toàn diện
2. Tool này sẽ tự động thực hiện web research, phân tích chất lượng và tổng hợp câu trả lời
3. Đưa ra câu trả lời đầy đủ, chính xác bằng tiếng Việt

Nguyên tắc hoạt động:
- Ưu tiên thông tin hiện tại, chính xác và đáng tin cậy
- Đối với câu hỏi về thời tiết, tập trung vào dữ liệu thời gian thực
- Trả lời bằng tiếng Việt một cách tự nhiên và dễ hiểu
- Bao gồm nguồn thông tin khi có thể
- Nếu không tìm được thông tin đáng tin cậy, hãy thành thật về giới hạn

Lưu ý đặc biệt:
- Luôn sử dụng tool `conduct_comprehensive_research` cho mọi câu hỏi nghiên cứu
- Không tự tạo ra thông tin hoặc đoán mò
- Đảm bảo câu trả lời phù hợp với văn hóa và ngôn ngữ Việt Nam"""


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


# Message constants used by server
NO_QUERY_MESSAGE = "Xin lỗi, tôi không nhận được câu hỏi nào từ bạn. Vui lòng đặt câu hỏi để tôi có thể giúp đỡ." 