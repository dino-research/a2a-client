"""
ADK-based research agent using Workflow Agents pattern.
Implements specialized LlmAgents for each research task and orchestrates them using Sequential/Loop Agents.
Updated to follow ADK v1.0.0 best practices with Workflow Agents.
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Optional
from google.adk.agents import LlmAgent, SequentialAgent, LoopAgent
from tavily import TavilyClient

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Import prompts
from prompts import (
    get_web_research_prompt,
    get_synthesis_prompt,
    get_research_agent_instruction
)

# Global variable to store current effort settings
_current_effort_settings = {
    "initial_search_query_count": 3,
    "max_research_loops": 3
}

def set_effort_settings(initial_search_query_count: int, max_research_loops: int):
    """Set global effort settings for this research session."""
    global _current_effort_settings
    _current_effort_settings = {
        "initial_search_query_count": initial_search_query_count,
        "max_research_loops": max_research_loops
    }

def get_current_date() -> str:
    """Get current date in a readable format."""
    return datetime.now().strftime("%B %d, %Y")

# ============================================================================
# COORDINATOR AGENT FOR DETERMINING RESEARCH APPROACH
# ============================================================================

def create_coordinator_agent(model: str = "gemini-2.0-flash") -> LlmAgent:
    """
    Create an LlmAgent that coordinates and decides whether web research is needed.
    """
    
    def tavily_research_tool(query: str) -> Dict:
        """Tool function for Tavily research"""
        try:
            tavily_api_key = os.getenv("TAVILY_API_KEY")
            if not tavily_api_key:
                return {
                    "status": "error",
                    "query": query,
                    "error": "TAVILY_API_KEY not found in environment variables",
                    "research_date": get_current_date()
                }
            
            tavily_client = TavilyClient(api_key=tavily_api_key)
            current_date = get_current_date()
            
            # Perform search with Tavily
            search_result = tavily_client.search(
                query=query,
                search_depth="advanced",
                max_results=5,
                include_answer=True,
                include_raw_content=False,
                include_domains=None,
                exclude_domains=None
            )
            
            # Extract sources from Tavily results
            sources = []
            search_content = ""
            
            if search_result.get("answer"):
                search_content = search_result["answer"]
            
            # Process search results
            if search_result.get("results"):
                for result in search_result["results"]:
                    sources.append({
                        "title": result.get("title", "Không có tiêu đề"),
                        "url": result.get("url", ""),
                        "snippet": result.get("content", "")[:300] + "..." if result.get("content") else ""
                    })
                    
                    # Append content for comprehensive research
                    if result.get("content"):
                        search_content += f"\n\n{result['content'][:500]}..."
            
            # If no answer was provided by Tavily, create summary from results
            if not search_content and sources:
                search_content = f"Kết quả tìm kiếm cho '{query}':\n\n"
                for i, source in enumerate(sources[:3], 1):
                    search_content += f"{i}. {source['title']}: {source['snippet']}\n\n"
            
            return {
                "status": "success",
                "query": query,
                "content": search_content,
                "sources": sources,
                "research_date": current_date,
                "search_engine": "Tavily"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "query": query,
                "error": str(e),
                "research_date": get_current_date()
            }
    
    instruction = f"""
Bạn là một AI assistant thông minh có khả năng phân tích câu hỏi và quyết định cách trả lời tối ưu. Ngày hiện tại: {get_current_date()}

**QUY TRÌNH XỬ LÝ:**

BƯỚC 1: Phân tích câu hỏi
- Câu hỏi cá nhân/chào hỏi/giới thiệu → Trả lời trực tiếp
- Kiến thức cơ bản không đổi theo thời gian → Trả lời trực tiếp  
- Thông tin cần cập nhật/tin tức/dữ liệu thời gian thực → Tìm kiếm web

BƯỚC 2: Thực hiện
- Nếu trả lời trực tiếp: Đưa ra câu trả lời hoàn chỉnh bằng tiếng Việt
- Nếu cần tìm kiếm: Sử dụng tavily_research_tool rồi tổng hợp kết quả

**VÍ DỤ:**

Câu hỏi: "Chào bạn, tôi là Thái"
→ Trả lời trực tiếp: "Chào bạn Thái! Tôi là AI assistant, rất vui được làm quen với bạn. Tôi có thể giúp bạn trả lời câu hỏi, tìm kiếm thông tin hoặc hỗ trợ trong nhiều công việc khác. Bạn cần tôi giúp gì không?"

Câu hỏi: "Thời tiết Hà Nội hôm nay thế nào?"
→ Tìm kiếm web với query "thời tiết Hà Nội hôm nay" rồi tổng hợp kết quả

Câu hỏi: "2 + 2 bằng bao nhiêu?"
→ Trả lời trực tiếp: "2 + 2 = 4"

**LƯU Ý:**
- Luôn trả lời bằng tiếng Việt
- Không trả về JSON, chỉ trả lời trực tiếp hoặc sử dụng tool
- Khi sử dụng tool, hãy tổng hợp kết quả thành câu trả lời hoàn chỉnh
"""
    
    return LlmAgent(
        name="coordinator",
        model=model,
        tools=[tavily_research_tool],
        instruction=instruction,
        description="Agent điều phối thông minh có khả năng trả lời trực tiếp hoặc tìm kiếm web"
    )

# ============================================================================
# SPECIALIZED LLM AGENTS FOR EACH RESEARCH TASK
# ============================================================================

def create_query_generator_agent(model: str = "gemini-2.0-flash") -> LlmAgent:
    """
    Create an LlmAgent specialized in generating search queries.
    """
    instruction = f"""
Bạn là chuyên gia tạo query tìm kiếm. Nhiệm vụ của bạn là tạo ra {_current_effort_settings['initial_search_query_count']} query tìm kiếm hiệu quả từ câu hỏi của người dùng.

Nguyên tắc:
1. Tạo query đa dạng để bao phủ nhiều góc độ
2. Bao gồm từ khóa chính và từ khóa phụ
3. Xem xét cả tiếng Việt và tiếng Anh nếu cần
4. Tối ưu cho search engine

Định dạng output: Trả về list các query dưới dạng JSON array
Ví dụ: ["query 1", "query 2", "query 3"]

Ngày hiện tại: {get_current_date()}
"""
    
    return LlmAgent(
        name="query_generator",
        model=model,
        instruction=instruction,
        description="Specialized agent for generating effective search queries"
    )

def create_web_research_agent(model: str = "gemini-2.0-flash") -> LlmAgent:
    """
    Create an LlmAgent specialized in web research using Tavily.
    """
    
    def tavily_research_tool(query: str) -> Dict:
        """Tool function for Tavily research"""
        try:
            tavily_api_key = os.getenv("TAVILY_API_KEY")
            if not tavily_api_key:
                return {
                    "status": "error",
                    "query": query,
                    "error": "TAVILY_API_KEY not found in environment variables",
                    "research_date": get_current_date()
                }
            
            tavily_client = TavilyClient(api_key=tavily_api_key)
            current_date = get_current_date()
            
            # Perform search with Tavily
            search_result = tavily_client.search(
                query=query,
                search_depth="advanced",
                max_results=5,
                include_answer=True,
                include_raw_content=False,
                include_domains=None,
                exclude_domains=None
            )
            
            # Extract sources from Tavily results
            sources = []
            search_content = ""
            
            if search_result.get("answer"):
                search_content = search_result["answer"]
            
            # Process search results
            if search_result.get("results"):
                for result in search_result["results"]:
                    sources.append({
                        "title": result.get("title", "Không có tiêu đề"),
                        "url": result.get("url", ""),
                        "snippet": result.get("content", "")[:300] + "..." if result.get("content") else ""
                    })
                    
                    # Append content for comprehensive research
                    if result.get("content"):
                        search_content += f"\n\n{result['content'][:500]}..."
            
            # If no answer was provided by Tavily, create summary from results
            if not search_content and sources:
                search_content = f"Kết quả tìm kiếm cho '{query}':\n\n"
                for i, source in enumerate(sources[:3], 1):
                    search_content += f"{i}. {source['title']}: {source['snippet']}\n\n"
            
            return {
                "status": "success",
                "query": query,
                "content": search_content,
                "sources": sources,
                "research_date": current_date,
                "search_engine": "Tavily"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "query": query,
                "error": str(e),
                "research_date": get_current_date()
            }
    
    instruction = """
Bạn là chuyên gia nghiên cứu web. Nhiệm vụ của bạn là thực hiện tìm kiếm web với các query được cung cấp.

Nguyên tắc:
1. Thực hiện tìm kiếm với từng query một cách kỹ lưỡng
2. Thu thập thông tin từ nhiều nguồn đáng tin cậy
3. Tổng hợp và phân tích thông tin thu được
4. Đánh giá chất lượng và độ tin cậy của nguồn

Định dạng output: Trả về kết quả nghiên cứu dưới dạng JSON với các trường:
- status: "success" hoặc "error"
- content: Nội dung nghiên cứu
- sources: Danh sách các nguồn
- summary: Tóm tắt thông tin chính

Sử dụng tool tavily_research_tool để thực hiện tìm kiếm.
"""
    
    return LlmAgent(
        name="web_researcher",
        model=model,
        tools=[tavily_research_tool],
        instruction=instruction,
        description="Specialized agent for conducting web research"
    )

def create_quality_analyzer_agent(model: str = "gemini-2.0-flash") -> LlmAgent:
    """
    Create an LlmAgent specialized in analyzing research quality.
    """
    instruction = """
Bạn là chuyên gia phân tích chất lượng nghiên cứu. Nhiệm vụ của bạn là đánh giá chất lượng và tính đầy đủ của kết quả nghiên cứu.

Tiêu chí đánh giá:
1. Số lượng nguồn tin đáng tin cậy
2. Tính đa dạng của thông tin
3. Độ mới của thông tin
4. Tính liên quan đến câu hỏi gốc
5. Tính đầy đủ để trả lời câu hỏi

Thang điểm:
- 0.8-1.0: Chất lượng cao, đủ thông tin
- 0.6-0.7: Chất lượng trung bình, cần thêm thông tin
- 0.0-0.5: Chất lượng thấp, cần nghiên cứu thêm nhiều

Định dạng output: JSON với các trường:
- confidence: Điểm tin cậy (0.0-1.0)
- is_sufficient: true/false
- recommendation: "finalize_answer", "additional_research", hoặc "need_more_research"
- gaps_identified: Danh sách các khoảng trống thông tin cần bổ sung
- reason: Lý do đưa ra đánh giá này
"""
    
    return LlmAgent(
        name="quality_analyzer",
        model=model,
        instruction=instruction,
        description="Specialized agent for analyzing research quality and completeness"
    )

def create_refinement_agent(model: str = "gemini-2.0-flash") -> LlmAgent:
    """
    Create an LlmAgent specialized in generating refinement queries.
    """
    max_queries = min(_current_effort_settings["initial_search_query_count"], 3)
    
    instruction = f"""
Bạn là chuyên gia tạo query bổ sung. Nhiệm vụ của bạn là tạo ra tối đa {max_queries} query bổ sung để lấp đầy khoảng trống thông tin.

Nguyên tắc:
1. Phân tích khoảng trống thông tin từ đánh giá chất lượng
2. Tạo query cụ thể để tìm thông tin còn thiếu
3. Tập trung vào các khía cạnh chưa được khám phá
4. Ưu tiên thông tin mới nhất và đáng tin cậy

Định dạng output: JSON array các query bổ sung
Ví dụ: ["query bổ sung 1", "query bổ sung 2"]

Nếu không cần thêm nghiên cứu, trả về array rỗng: []
"""
    
    return LlmAgent(
        name="refinement_specialist",
        model=model,
        instruction=instruction,
        description="Specialized agent for generating follow-up research queries"
    )

def create_answer_finalizer_agent(model: str = "gemini-2.0-flash") -> LlmAgent:
    """
    Create an LlmAgent specialized in synthesizing final answers.
    """
    instruction = """
Bạn là chuyên gia tổng hợp thông tin và viết câu trả lời cuối cùng. Nhiệm vụ của bạn là tạo ra câu trả lời toàn diện, chính xác và có trích dẫn nguồn.

Nguyên tắc:
1. Tổng hợp tất cả thông tin từ các nguồn đã nghiên cứu
2. Trả lời trực tiếp câu hỏi của người dùng
3. Sử dụng ngôn ngữ rõ ràng, dễ hiểu
4. Bao gồm trích dẫn nguồn đáng tin cậy
5. Cấu trúc câu trả lời logic và mạch lạc

Định dạng output:
- Câu trả lời chính (bằng tiếng Việt)
- Phần nguồn thông tin với format markdown links

Ví dụ:
Câu trả lời về chủ đề...

**Nguồn thông tin:**
1. [Tiêu đề nguồn 1](URL)
2. [Tiêu đề nguồn 2](URL)
"""
    
    return LlmAgent(
        name="answer_finalizer",
        model=model,
        instruction=instruction,
        description="Specialized agent for synthesizing comprehensive final answers"
    )

# ============================================================================
# WORKFLOW ORCHESTRATION
# ============================================================================

def create_research_workflow_agent(model: str = "gemini-2.0-flash") -> SequentialAgent:
    """
    Create a SequentialAgent that orchestrates the research workflow.
    """
    # Create specialized agents
    query_generator = create_query_generator_agent(model)
    web_researcher = create_web_research_agent(model)
    quality_analyzer = create_quality_analyzer_agent(model)
    answer_finalizer = create_answer_finalizer_agent(model)
    
    # Create sequential workflow
    research_workflow = SequentialAgent(
        name="research_workflow",
        sub_agents=[
            query_generator,
            web_researcher,
            quality_analyzer,
            answer_finalizer
        ],
        description="Sequential workflow for comprehensive research and answer generation"
    )
    
    return research_workflow

def create_iterative_research_agent(model: str = "gemini-2.0-flash") -> LoopAgent:
    """
    Create a LoopAgent for iterative research with quality checking.
    """
    max_loops = _current_effort_settings["max_research_loops"]
    
    # Create the research loop components
    query_generator = create_query_generator_agent(model)
    web_researcher = create_web_research_agent(model)
    quality_analyzer = create_quality_analyzer_agent(model)
    refinement_agent = create_refinement_agent(model)
    
    # Create a sequential sub-workflow for each iteration
    iteration_workflow = SequentialAgent(
        name="research_iteration",
        sub_agents=[
            query_generator,
            web_researcher,
            quality_analyzer,
            refinement_agent
        ],
        description="Single iteration of research, analysis, and refinement"
    )
    
    # Create loop agent (simplified without complex termination condition)
    iterative_researcher = LoopAgent(
        name="iterative_researcher",
        sub_agents=[iteration_workflow],
        max_iterations=max_loops,
        description=f"Iterative research loop with max {max_loops} iterations"
    )
    
    return iterative_researcher

# ============================================================================
# MAIN RESEARCH AGENT FACTORY
# ============================================================================

def create_simple_answer_agent(model: str = "gemini-2.0-flash") -> LlmAgent:
    """
    Create an LlmAgent for answering simple questions directly without web research.
    """
    instruction = """
Bạn là một AI assistant thông minh, có thể trả lời các câu hỏi cơ bản mà không cần tìm kiếm thông tin trên web.

Nhiệm vụ của bạn:
1. Trả lời các câu hỏi cá nhân, chào hỏi, giới thiệu
2. Giải đáp các câu hỏi kiến thức cơ bản
3. Thực hiện các phép toán đơn giản
4. Cung cấp định nghĩa và giải thích khái niệm cơ bản

Nguyên tắc:
- Trả lời một cách thân thiện và hữu ích
- Sử dụng ngôn ngữ rõ ràng, dễ hiểu
- Thừa nhận nếu không chắc chắn về thông tin
- Không đưa ra thông tin có thể lỗi thời

Định dạng: Trả lời trực tiếp bằng tiếng Việt, không cần format JSON.
"""
    
    return LlmAgent(
        name="simple_answer_agent",
        model=model,
        instruction=instruction,
        description="Agent trả lời trực tiếp các câu hỏi đơn giản"
    )

def create_coordinator_workflow_agent(model: str = "gemini-2.0-flash") -> LlmAgent:
    """
    Create an intelligent coordinator agent that uses LLM reasoning to decide response approach.
    """
    instruction = f"""
Bạn là một AI coordinator thông minh. Nhiệm vụ của bạn là phân tích câu hỏi của người dùng và quyết định cách trả lời phù hợp nhất.

**TRIẾT LÝ QUYẾT ĐỊNH:**

Sử dụng khả năng hiểu biết tự nhiên của bạn để đánh giá xem câu hỏi có cần thông tin mới nhất/cập nhật từ internet hay không.

**NGUYÊN TẮC QUYẾT ĐỊNH:**

🤔 **Tự hỏi bản thân:**
- Câu hỏi này có cần thông tin thời gian thực không?
- Tôi có thể trả lời chính xác bằng kiến thức hiện có không?
- Câu trả lời có thể thay đổi theo thời gian không?
- Đây có phải thông tin cá nhân/chào hỏi/toán cơ bản không?

**QUY TRÌNH QUYẾT ĐỊNH:**

1. **Phân tích bản chất câu hỏi** - Đây là loại thông tin gì?
2. **Đánh giá tính thời gian** - Thông tin này có "hết hạn" không?
3. **Cân nhắc độ chính xác** - Tôi có chắc chắn với câu trả lời không?
4. **Ra quyết định** - Trả lời trực tiếp hay cần web search?

**ĐỊNH DẠNG OUTPUT:**

🎯 **Nếu có thể trả lời ngay** (personal, greeting, basic knowledge):
Trả lời trực tiếp bằng văn bản tự nhiên

🔍 **Nếu cần thông tin cập nhật** (current events, real-time data):
{{
    "action": "web_research_needed",
    "query": "câu hỏi gốc của người dùng",
    "reasoning": "giải thích ngắn gọn tại sao cần web search"
}}

**VÍ DỤ MINH HỌA:**

💬 "Chào bạn, tôi là Thái" 
→ Trả lời trực tiếp (đây là lời chào/giới thiệu)

🧮 "2 + 2 bằng mấy?"
→ Trả lời trực tiếp (toán cơ bản, không đổi theo thời gian)

🌤️ "Thời tiết Hà Nội hôm nay như thế nào?"
→ JSON web search (thông tin thời gian thực, thay đổi hàng ngày)

📈 "Giá vàng hiện tại"
→ JSON web search (dữ liệu thời gian thực, biến động liên tục)

📰 "Tin tức mới nhất về AI"
→ JSON web search (thông tin mới, cần nguồn cập nhật)

🏛️ "Thủ đô của Việt Nam là gì?"
→ Trả lời trực tiếp (kiến thức cơ bản, không thay đổi)

**LƯU Ý:**
- Hãy tự tin với những gì bạn biết chắc chắn
- Thừa nhận khi cần thông tin mới nhất
- Ưu tiên trải nghiệm người dùng (nhanh khi có thể, chính xác khi cần thiết)
- Ngày hiện tại: {get_current_date()}
"""
    
    return LlmAgent(
        name="coordinator_workflow",
        model=model,
        instruction=instruction,
        description="Intelligent coordinator using LLM reasoning for decision making"
    )

def create_research_agent(
    model: str = "gemini-2.0-flash",
    initial_search_query_count: int = 3,
    max_research_loops: int = 3
) -> LlmAgent:
    """
    Create a comprehensive research agent using smart coordinator approach.
    
    Args:
        model: The Gemini model to use
        initial_search_query_count: Number of initial search queries to generate
        max_research_loops: Maximum number of research loops to perform
        
    Returns:
        LlmAgent: Smart coordinator agent that handles everything
    """
    # Set effort settings for this research session
    set_effort_settings(initial_search_query_count, max_research_loops)
    
    # Return the smart coordinator that handles everything
    return create_coordinator_workflow_agent(model)

# Create default agent for backward compatibility
research_agent = create_research_agent("gemini-2.0-flash", 3, 3) 