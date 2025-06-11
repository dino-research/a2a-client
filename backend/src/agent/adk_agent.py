"""
ADK-based research agent that performs web research and provides comprehensive answers.
Updated to follow ADK v1.0.0 best practices with Tavily Search integration.
"""
import os
import json
from datetime import datetime
from typing import Dict, List
from google.adk.agents import LlmAgent
from google.genai import Client
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

def get_current_date() -> str:
    """Get current date in a readable format."""
    return datetime.now().strftime("%B %d, %Y")

def web_research(query: str) -> Dict:
    """
    Performs comprehensive web research on a given query using Tavily Search.
    This function will be used as a tool by the ADK agent.
    
    Args:
        query: The search query to research
        
    Returns:
        Dictionary containing research results and sources
    """
    try:
        # Initialize Tavily client
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
            search_depth="advanced",  # Use advanced search for more comprehensive results
            max_results=5,  # Get top 5 results
            include_answer=True,  # Include AI-generated answer
            include_raw_content=False,  # Don't include full page content
            include_domains=None,  # Search all domains
            exclude_domains=None  # Don't exclude any domains
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

def analyze_research_quality(research_results: List[Dict]) -> Dict:
    """
    Analyzes the quality and completeness of research results.
    This function will be used as a tool by the ADK agent.
    
    Args:
        research_results: List of research result dictionaries
        
    Returns:
        Dictionary with quality analysis and recommendations
    """
    if not research_results:
        return {
            "status": "insufficient",
            "confidence": 0.0,
            "recommendation": "need_more_research",
            "reason": "No research results available"
        }
    
    successful_results = [r for r in research_results if r.get("status") == "success"]
    
    if not successful_results:
        return {
            "status": "insufficient", 
            "confidence": 0.0,
            "recommendation": "need_more_research",
            "reason": "All research attempts failed"
        }
    
    # Simple quality metrics
    total_sources = sum(len(r.get("sources", [])) for r in successful_results)
    avg_content_length = sum(len(r.get("content", "")) for r in successful_results) / len(successful_results)
    
    # Determine confidence based on sources and content
    confidence = min(1.0, (total_sources * 0.2) + (avg_content_length / 1000))
    
    if confidence >= 0.7 and total_sources >= 3:
        status = "sufficient"
        recommendation = "finalize_answer"
    elif confidence >= 0.5:
        status = "partial"
        recommendation = "additional_research"
    else:
        status = "insufficient"
        recommendation = "need_more_research"
    
    return {
        "status": status,
        "confidence": confidence,
        "recommendation": recommendation,
        "total_sources": total_sources,
        "research_count": len(successful_results),
        "avg_content_length": int(avg_content_length)
    }

def conduct_comprehensive_research(query: str) -> str:
    """
    Main research function that the agent will use to conduct research and provide answers.
    This combines web research, analysis, and final answer generation.
    
    Args:
        query: The user's research query
        
    Returns:
        String containing the comprehensive research answer
    """
    try:
        # Step 1: Perform web research
        research_result = web_research(query)
        
        if research_result.get("status") != "success":
            return f"Xin lỗi, tôi gặp khó khăn khi tìm kiếm thông tin: {research_result.get('error', 'Lỗi không xác định')}"
        
        # Step 2: Analyze research quality
        quality_analysis = analyze_research_quality([research_result])
        
        # Step 3: Generate final answer using the research content
        research_content = research_result.get("content", "")
        sources = research_result.get("sources", [])
        
        if not research_content:
            return "Xin lỗi, tôi không thể tìm được thông tin phù hợp để trả lời câu hỏi của bạn."
        
        # Use Gemini to synthesize the final answer
        client = Client(api_key=os.getenv("GEMINI_API_KEY"))
        current_date = get_current_date()
        
        synthesis_prompt = get_synthesis_prompt(query, research_content, current_date)
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=synthesis_prompt,
            config={"temperature": 0.2}
        )
        
        # Format the final answer with confidence information
        final_answer = response.text
        
        # Add source information if available
        if sources:
            final_answer += "\n\n**Nguồn thông tin:**\n"
            for i, source in enumerate(sources[:5], 1):  # Limit to 5 sources
                final_answer += f"{i}. [{source.get('title', 'Không có tiêu đề')}]({source.get('url', '#')})\n"
        
        return final_answer
        
    except Exception as e:
        return f"Xin lỗi, đã có lỗi xảy ra khi nghiên cứu thông tin: {str(e)}"

# Create the main research agent following ADK v1.0.0 best practices
research_agent = LlmAgent(
    name="research_assistant",
    model="gemini-2.0-flash", 
    tools=[conduct_comprehensive_research],
    instruction=get_research_agent_instruction(),
    description="AI research assistant that conducts web research and provides comprehensive answers in Vietnamese"
) 