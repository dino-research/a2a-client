"""
FastAPI server using Google Agent Development Kit with research_agent.
Refactored to use ADK agent instead of direct Gemini client.
"""
import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional, AsyncGenerator
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import prompts and configurations
from prompts import (
    get_health_check_response,
    get_api_description,
    NO_QUERY_MESSAGE
)

# Import the research functions directly
from adk_agent import web_research, generate_final_answer

try:
    from app import create_frontend_router
except ImportError:
    # If import fails, create a simple fallback
    def create_frontend_router():
        from fastapi import Response
        from starlette.routing import Route
        
        async def dummy_frontend(request):
            return Response(
                "Frontend not available. Please build the frontend first.",
                media_type="text/plain",
                status_code=503,
            )
        return Route("/{path:path}", endpoint=dummy_frontend)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Gemini Research Agent API",
    description="AI research assistant powered by Google Agent Development Kit",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the frontend
app.mount(
    "/app",
    create_frontend_router(),
    name="frontend",
)

# No need for ADK components - using direct functions

# Pydantic models
class Message(BaseModel):
    type: str
    content: str
    id: Optional[str] = None

class RunRequest(BaseModel):
    messages: List[Message]
    initial_search_query_count: Optional[int] = 3
    max_research_loops: Optional[int] = 3
    reasoning_model: Optional[str] = "gemini-2.0-flash"

def format_stream_event(event_type: str, data: Dict, message_id: str = None) -> str:
    """Format event for SSE streaming."""
    event = {
        "event_type": event_type,
        "data": data,
        "message_id": message_id,
        "timestamp": datetime.now().isoformat()
    }
    return f"data: {json.dumps(event)}\n\n"

async def research_and_answer_with_agent(query: str) -> AsyncGenerator[str, None]:
    """Research query using direct functions and provide streaming response."""
    try:
        # Yield initial query generation event
        yield format_stream_event("generate_query", {
            "query_list": [query]
        })
        
        # Perform web research
        research_result = web_research(query)
        
        # Extract sources from research result
        sources = research_result.get("sources", [])
        
        # Yield web research event
        yield format_stream_event("web_research", {
            "sources_gathered": sources,
            "query": query,
            "status": "success"
        })
        
        # Yield reflection event
        yield format_stream_event("reflection", {
            "is_sufficient": True,
            "confidence": 0.8,
            "follow_up_queries": []
        })
        
        # Generate final answer
        final_answer_result = generate_final_answer(query, [research_result])
        final_response_text = final_answer_result.get("answer", "Xin lỗi, tôi không thể tìm thấy thông tin phù hợp.")
        
        # Yield finalize event
        yield format_stream_event("finalize_answer", {
            "answer": final_response_text,
            "sources": sources,
            "confidence": 0.8
        })
        
        # Send final message
        message_id = f"msg_{datetime.now().timestamp()}"
        final_message = {
            "type": "ai",
            "content": final_response_text,
            "id": message_id,
            "sources": sources
        }
        yield format_stream_event("message", final_message, message_id)
        
    except Exception as e:
        error_message = f"Xin lỗi, đã xảy ra lỗi khi tìm kiếm thông tin: {str(e)}"
        
        yield format_stream_event("error", {"message": error_message})
        
        message_id = f"msg_{datetime.now().timestamp()}"
        error_response = {
            "type": "ai",
            "content": error_message,
            "id": message_id
        }
        yield format_stream_event("message", error_response, message_id)

@app.post("/assistants/{assistant_id}/runs")
async def create_run(assistant_id: str, run_request: RunRequest):
    """Create a new run (compatible with LangGraph SDK)."""
    # Get the latest user message
    user_messages = [msg for msg in run_request.messages if msg.type == "human"]
    if not user_messages:
        raise HTTPException(status_code=400, detail=NO_QUERY_MESSAGE)
    
    latest_message = user_messages[-1]
    query = latest_message.content
    
    async def generate():
        yield "event: message\n"
        async for chunk in research_and_answer_with_agent(query):
            yield chunk
        yield "event: end\n"
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        }
    )

@app.get("/assistants/{assistant_id}/runs/{run_id}")
async def get_run(assistant_id: str, run_id: str):
    """Get run status (compatibility endpoint)."""
    return {
        "run_id": run_id,
        "assistant_id": assistant_id,
        "status": "completed",
        "created_at": datetime.now().isoformat()
    }

@app.post("/assistants/{assistant_id}/runs/{run_id}/cancel")
async def cancel_run(assistant_id: str, run_id: str):
    """Cancel a run (compatibility endpoint)."""
    return {
        "run_id": run_id,
        "status": "cancelled",
        "cancelled_at": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # Use health check response from prompts module
    health_data = get_health_check_response()
    health_data["api_key_configured"] = bool(os.getenv("GEMINI_API_KEY"))
    return health_data

@app.get("/")
async def root():
    """Root endpoint."""
    # Use API description from prompts module
    return get_api_description()

if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=2024,
        reload=True,
        log_level="info"
    ) 