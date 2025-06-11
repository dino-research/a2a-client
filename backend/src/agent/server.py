"""
FastAPI server using Gemini API directly with grounded search.
Refactored to use Google Agent Development Kit with separated prompts.
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
from google.genai import Client
import uvicorn

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import prompts and configurations
from prompts import (
    get_research_prompt,
    get_error_message, 
    get_model_config,
    get_health_check_response,
    get_api_description,
    NO_QUERY_MESSAGE
)

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

# Initialize Gemini client
client = Client(api_key=os.getenv("GEMINI_API_KEY"))

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

async def research_and_answer(query: str) -> AsyncGenerator[str, None]:
    """Research query and provide streaming response."""
    try:
        # Yield initial query generation event
        yield format_stream_event("generate_query", {
            "query_list": [query]
        })
        
        # Get research prompt from prompts module
        prompt = get_research_prompt(query)
        
        # Get model configuration from prompts module
        config = get_model_config()

        # Call Gemini with grounded search
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=config,
        )
        
        # Extract sources from grounding metadata
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
                                "snippet": getattr(chunk.web, 'snippet', ''),
                                "label": chunk.web.title.split('.')[0] if '.' in chunk.web.title else chunk.web.title
                            })
        
        # Yield web research event
        yield format_stream_event("web_research", {
            "sources_gathered": sources,
            "query": query,
            "status": "success"
        })
        
        # Yield reflection event
        yield format_stream_event("reflection", {
            "is_sufficient": True,
            "confidence": 0.8 if sources else 0.6,
            "follow_up_queries": []
        })
        
        # Yield finalize event
        yield format_stream_event("finalize_answer", {
            "answer": response.text,
            "sources": sources,
            "confidence": 0.8 if sources else 0.6
        })
        
        # Send final message
        message_id = f"msg_{datetime.now().timestamp()}"
        final_message = {
            "type": "ai",
            "content": response.text,
            "id": message_id,
            "sources": sources
        }
        yield format_stream_event("message", final_message, message_id)
        
    except Exception as e:
        # Use error message from prompts module
        error_message = get_error_message(str(e))
        
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
        async for chunk in research_and_answer(query):
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