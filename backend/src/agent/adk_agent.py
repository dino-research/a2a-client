"""
ADK-based research agent that performs web research and provides comprehensive answers.
"""
import os
import json
from datetime import datetime
from typing import Dict, List
from google.adk.agents import LlmAgent
from google.genai import Client

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

def get_current_date() -> str:
    """Get current date in a readable format."""
    return datetime.now().strftime("%B %d, %Y")

def web_research(query: str) -> Dict:
    """
    Performs comprehensive web research on a given query using Google Search.
    
    Args:
        query: The search query to research
        
    Returns:
        Dictionary containing research results and sources
    """
    try:
        # Initialize the Google GenAI client for grounded search
        client = Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        current_date = get_current_date()
        prompt = f"""Conduct comprehensive research on: "{query}"

Instructions:
- Use Google Search to find the most current and relevant information
- The current date is {current_date}
- Provide detailed information with proper citations
- Focus on factual, verifiable information
- Include multiple sources when possible

Research Query: {query}"""

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config={
                "tools": [{"google_search": {}}],
                "temperature": 0.1,
            },
        )
        
        # Extract sources from grounding metadata if available
        sources = []
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                if hasattr(candidate.grounding_metadata, 'grounding_chunks'):
                    for chunk in candidate.grounding_metadata.grounding_chunks:
                        if hasattr(chunk, 'web') and chunk.web:
                            sources.append({
                                "title": chunk.web.title,
                                "url": chunk.web.uri,
                                "snippet": getattr(chunk.web, 'snippet', '')
                            })
        
        return {
            "status": "success",
            "query": query,
            "content": response.text,
            "sources": sources,
            "research_date": current_date
        }
        
    except Exception as e:
        return {
            "status": "error",
            "query": query,
            "error": str(e),
            "research_date": current_date
        }

def analyze_research_quality(research_results: List[Dict]) -> Dict:
    """
    Analyzes the quality and completeness of research results.
    
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

def generate_final_answer(question: str, research_results: List[Dict]) -> Dict:
    """
    Generates a comprehensive final answer based on research results.
    
    Args:
        question: The original user question
        research_results: List of research result dictionaries
        
    Returns:
        Dictionary containing the final answer and metadata
    """
    try:
        # Compile all research content
        research_content = []
        all_sources = []
        
        for result in research_results:
            if result.get("status") == "success":
                research_content.append(result.get("content", ""))
                all_sources.extend(result.get("sources", []))
        
        if not research_content:
            return {
                "status": "error",
                "answer": "Xin lỗi, tôi không thể tìm được thông tin để trả lời câu hỏi của bạn.",
                "sources": [],
                "confidence": 0.0
            }
        
        # Use Gemini to synthesize the final answer
        client = Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        current_date = get_current_date()
        synthesis_prompt = f"""Based on the research findings below, provide a comprehensive answer to the user's question.

User Question: {question}
Current Date: {current_date}

Research Findings:
{chr(10).join(research_content)}

Instructions:
- Provide a clear, accurate answer in Vietnamese
- Include relevant details and context
- Cite sources when possible
- Be informative but concise
- If the question is about current events or weather, emphasize the most recent information
"""

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=synthesis_prompt,
            config={
                "temperature": 0.2,
            },
        )
        
        # Remove duplicate sources
        unique_sources = []
        seen_urls = set()
        for source in all_sources:
            if source.get("url") not in seen_urls:
                unique_sources.append(source)
                seen_urls.add(source.get("url"))
        
        return {
            "status": "success",
            "answer": response.text,
            "sources": unique_sources[:10],  # Limit to top 10 sources
            "confidence": min(1.0, len(unique_sources) * 0.15 + 0.4)
        }
        
    except Exception as e:
        return {
            "status": "error",
            "answer": f"Xin lỗi, đã có lỗi xảy ra khi tổng hợp thông tin: {str(e)}",
            "sources": [],
            "confidence": 0.0
        }

# Create the main research agent
research_agent = LlmAgent(
    name="research_assistant",
    model="gemini-2.0-flash", 
    tools=[web_research, analyze_research_quality, generate_final_answer],
    instruction="""You are a comprehensive research assistant that helps users find accurate, up-to-date information.

Your workflow:
1. When a user asks a question, use web_research() to gather information
2. Use analyze_research_quality() to assess if you have enough information
3. If more research is needed, perform additional web_research() with refined queries
4. Once you have sufficient information, use generate_final_answer() to provide a comprehensive response

Guidelines:
- Always prioritize current, factual information
- For weather questions, focus on real-time data
- For Vietnamese questions, provide answers in Vietnamese
- Include sources when possible
- Be thorough but concise
- If you cannot find reliable information, be honest about limitations""",
    description="AI research assistant that conducts web research and provides comprehensive answers"
) 