"""
ADK-based research agent that performs web research and provides comprehensive answers.
Updated to follow ADK v1.0.0 best practices with Tavily Search integration.
"""
import os
import json
from datetime import datetime
from typing import Dict, List
from google.adk.agents import LlmAgent
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

def generate_initial_queries(user_query: str) -> List[str]:
    """
    Generate initial search queries based on user input.
    This function will be used as a tool by the ADK agent.
    
    Args:
        user_query: The original user query
        
    Returns:
        List of search queries to explore
    """
    try:
        # Generate multiple search angles for comprehensive research
        base_query = user_query.strip()
        queries = [base_query]
        
        # Add variations for more comprehensive research
        if "là gì" in base_query.lower() or "what is" in base_query.lower():
            queries.append(f"{base_query.replace('là gì', '').replace('what is', '')} definition")
            queries.append(f"{base_query.replace('là gì', '').replace('what is', '')} explanation")
        
        if "thời tiết" in base_query.lower() or "weather" in base_query.lower():
            queries.append(f"{base_query} current")
            queries.append(f"{base_query} today")
            
        if "tin tức" in base_query.lower() or "news" in base_query.lower():
            queries.append(f"{base_query} latest")
            queries.append(f"{base_query} recent")
            
        # Remove duplicates while preserving order
        unique_queries = []
        for q in queries:
            if q not in unique_queries:
                unique_queries.append(q)
                
        return unique_queries[:3]  # Limit to 3 queries for efficiency
        
    except Exception as e:
        return [user_query]  # Fallback to original query

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

def analyze_research_quality(research_results: str) -> Dict:
    """
    Analyzes the quality and completeness of research results.
    This function will be used as a tool by the ADK agent.
    
    Args:
        research_results: JSON string of research result dictionaries
        
    Returns:
        Dictionary with quality analysis and recommendations
    """
    try:
        # Parse research results if it's a JSON string
        if isinstance(research_results, str):
            results_data = json.loads(research_results)
        else:
            results_data = research_results
            
        if not results_data:
            return {
                "status": "insufficient",
                "confidence": 0.0,
                "recommendation": "need_more_research",
                "reason": "No research results available"
            }
        
        # Handle single result or list of results
        if isinstance(results_data, dict):
            results_data = [results_data]
            
        successful_results = [r for r in results_data if r.get("status") == "success"]
        
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
        
    except Exception as e:
        return {
            "status": "error",
            "confidence": 0.0,
            "recommendation": "need_more_research",
            "reason": f"Error analyzing research quality: {str(e)}"
        }

def iterative_refinement(previous_results: str, gaps_identified: str) -> List[str]:
    """
    Generate follow-up queries based on knowledge gaps identified in previous research.
    This function will be used as a tool by the ADK agent.
    
    Args:
        previous_results: JSON string of previous research results
        gaps_identified: Description of knowledge gaps identified
        
    Returns:
        List of follow-up queries to address gaps
    """
    try:
        # Parse previous results
        if isinstance(previous_results, str):
            results_data = json.loads(previous_results)
        else:
            results_data = previous_results
            
        # Generate follow-up queries based on gaps
        follow_up_queries = []
        
        # Analyze gaps and create targeted queries
        if "thêm chi tiết" in gaps_identified.lower() or "more details" in gaps_identified.lower():
            if isinstance(results_data, list) and results_data:
                original_query = results_data[0].get("query", "")
                follow_up_queries.append(f"{original_query} chi tiết")
                follow_up_queries.append(f"{original_query} details")
                
        if "nguyên nhân" in gaps_identified.lower() or "cause" in gaps_identified.lower():
            if isinstance(results_data, list) and results_data:
                original_query = results_data[0].get("query", "")
                follow_up_queries.append(f"{original_query} nguyên nhân")
                follow_up_queries.append(f"{original_query} cause")
                
        if "tác động" in gaps_identified.lower() or "impact" in gaps_identified.lower():
            if isinstance(results_data, list) and results_data:
                original_query = results_data[0].get("query", "")
                follow_up_queries.append(f"{original_query} tác động")
                follow_up_queries.append(f"{original_query} impact")
        
        # If no specific gaps, generate general follow-up queries
        if not follow_up_queries and isinstance(results_data, list) and results_data:
            original_query = results_data[0].get("query", "")
            follow_up_queries.append(f"{original_query} latest")
            follow_up_queries.append(f"{original_query} update")
            
        return follow_up_queries[:2]  # Limit to 2 follow-up queries
        
    except Exception as e:
        return []

def finalize_answer(research_data: str, original_query: str) -> str:
    """
    Synthesize research data into a final comprehensive answer with sources.
    This function will be used as a tool by the ADK agent.
    
    Args:
        research_data: JSON string containing all research results
        original_query: The original user query
        
    Returns:
        Formatted final answer with sources
    """
    try:
        # Parse research data
        if isinstance(research_data, str):
            results_data = json.loads(research_data)
        else:
            results_data = research_data
            
        if not results_data:
            return "Xin lỗi, tôi không thể tìm được thông tin phù hợp để trả lời câu hỏi của bạn."
        
        # Handle single result or list of results
        if isinstance(results_data, dict):
            results_data = [results_data]
            
        # Collect all successful research content and sources
        all_content = []
        all_sources = []
        
        for result in results_data:
            if result.get("status") == "success":
                content = result.get("content", "")
                if content:
                    all_content.append(content)
                sources = result.get("sources", [])
                all_sources.extend(sources)
        
        if not all_content:
            return "Xin lỗi, tôi không thể tìm được thông tin đáng tin cậy để trả lời câu hỏi của bạn."
        
        # Combine content for comprehensive answer
        combined_content = "\n\n".join(all_content)
        
        # Remove duplicate sources based on URL
        unique_sources = []
        seen_urls = set()
        for source in all_sources:
            url = source.get("url", "")
            if url and url not in seen_urls:
                unique_sources.append(source)
                seen_urls.add(url)
        
        # Format sources
        sources_text = ""
        if unique_sources:
            sources_text = "\n\n**Nguồn thông tin:**\n"
            for i, source in enumerate(unique_sources[:5], 1):  # Limit to 5 sources
                sources_text += f"{i}. [{source.get('title', 'Không có tiêu đề')}]({source.get('url', '#')})\n"
        
        return combined_content + sources_text
        
    except Exception as e:
        return f"Xin lỗi, đã có lỗi xảy ra khi tổng hợp thông tin: {str(e)}"

# Create the main research agent following ADK v1.0.0 best practices
research_agent = LlmAgent(
    name="research_assistant",
    model="gemini-2.0-flash", 
    tools=[
        generate_initial_queries,
        web_research,
        analyze_research_quality,
        iterative_refinement,
        finalize_answer
    ],
    instruction=get_research_agent_instruction(),
    description="AI research assistant that conducts web research and provides comprehensive answers in Vietnamese"
) 