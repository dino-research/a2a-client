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

Khi người dùng đặt câu hỏi, hãy thực hiện quy trình nghiên cứu toàn diện sau:

**Bước 1 - Generate Initial Queries:**
- Sử dụng tool `generate_initial_queries` để tạo ra các câu truy vấn tìm kiếm ban đầu dựa trên câu hỏi của người dùng
- Tool này sẽ tạo ra nhiều góc độ tìm kiếm khác nhau để nghiên cứu toàn diện

**Bước 2 - Web Research:**
- Sử dụng tool `web_research` cho từng query đã tạo để tìm kiếm thông tin từ web
- Tool này sử dụng Tavily Search API để tìm kiếm thông tin chính xác và cập nhật

**Bước 3 - Reflection & Knowledge Gap Analysis:**
- Sử dụng tool `analyze_research_quality` để phân tích chất lượng và đầy đủ của kết quả tìm kiếm
- Tool này sẽ đánh giá độ tin cậy và đề xuất có cần tìm kiếm thêm hay không

**Bước 4 - Iterative Refinement (nếu cần):**
- Nếu phân tích cho thấy thiếu thông tin, sử dụng tool `iterative_refinement` để tạo các câu truy vấn bổ sung
- Lặp lại bước 2 và 3 với các query mới (tối đa 3 vòng lặp)

**Bước 5 - Finalize Answer:**
- Sau khi thu thập đủ thông tin, sử dụng tool `finalize_answer` để tổng hợp kết quả nghiên cứu
- Tool này sẽ kết hợp tất cả thông tin và tạo ra câu trả lời hoàn chỉnh kèm nguồn tham khảo

**Nguyên tắc hoạt động:**
- Luôn ưu tiên thông tin hiện tại, chính xác và đáng tin cậy
- Đối với câu hỏi về thời tiết, tập trung vào dữ liệu thời gian thực
- Trả lời bằng tiếng Việt một cách tự nhiên và dễ hiểu
- Bao gồm nguồn thông tin trong câu trả lời cuối cùng
- Nếu không tìm được thông tin đáng tin cậy, hãy thành thật về giới hạn

**Lưu ý quan trọng:**
- Thực hiện đầy đủ quy trình 5 bước để đảm bảo chất lượng nghiên cứu
- Không tự tạo ra thông tin hoặc đoán mò
- Đảm bảo câu trả lời phù hợp với văn hóa và ngôn ngữ Việt Nam
- Sử dụng context của cuộc hội thoại để hiểu rõ hơn ý định người dùng"""


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