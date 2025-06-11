"""
FastAPI server using Google Agent Development Kit with research_agent.
Updated to properly use ADK agent instead of direct function calls.
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

# Import ADK components
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

# Import prompts and configurations
from prompts import (
    get_health_check_response,
    get_api_description,
    NO_QUERY_MESSAGE
)

# Import the research agent
from adk_agent import research_agent

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

# Initialize ADK components
APP_NAME = "gemini_research_agent"
session_service = InMemorySessionService()

# Create runner with the research agent
runner = Runner(
    agent=research_agent,
    app_name=APP_NAME,
    session_service=session_service
)

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

async def research_and_answer_with_agent(query: str, user_id: str = "default_user") -> AsyncGenerator[str, None]:
    """Research query using ADK agent and provide streaming response."""
    try:
        # Create a session for this request
        session_id = f"session_{datetime.now().timestamp()}"
        try:
            # Try async version first (newer ADK versions)
            await session_service.create_session(
                app_name=APP_NAME,
                user_id=user_id,
                session_id=session_id
            )
        except TypeError:
            # Fallback to sync version (older ADK versions)
            session_service.create_session(
                app_name=APP_NAME,
                user_id=user_id,
                session_id=session_id
            )
        
        # Yield initial query generation event
        yield format_stream_event("generate_query", {
            "query_list": [query]
        })
        
        # Create user content for ADK
        user_content = Content(role='user', parts=[Part(text=query)])
        
        # Variables to track the agent's response
        final_response_content = ""
        sources = []
        
        # Run the agent and process events
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_content
        ):
            # Handle different event types
            if hasattr(event, 'tool_name') and event.tool_name == "conduct_comprehensive_research":
                if event.type == "tool_request":
                    # Agent is calling the research tool
                    yield format_stream_event("web_research", {
                        "query": query,
                        "status": "searching"
                    })
                
                elif event.type == "tool_response":
                    # Research tool has completed - parse sources from result
                    try:
                        # The tool returns a formatted text response with sources
                        tool_result = event.content if hasattr(event, 'content') else ""
                        
                        # Extract sources if available (they are in the formatted response)
                        if "**Nguồn thông tin:**" in tool_result:
                            # Simple parsing - could be improved
                            sources = []
                        else:
                            sources = []
                        
                        yield format_stream_event("web_research", {
                            "sources_gathered": sources,
                            "query": query,
                            "status": "success"
                        })
                    except Exception as e:
                        print(f"Error parsing tool response: {e}")
            
            elif event.is_final_response():
                # Agent has generated the final response
                if event.content and event.content.parts:
                    final_response_content = event.content.parts[0].text
                    
                    # Yield reflection event
                    yield format_stream_event("reflection", {
                        "is_sufficient": True,
                        "confidence": 0.8,
                        "follow_up_queries": []
                    })
                    
                    # Yield finalize event
                    yield format_stream_event("finalize_answer", {
                        "answer": final_response_content,
                        "sources": sources,
                        "confidence": 0.8
                    })
                    
                    # Send final message
                    message_id = f"msg_{datetime.now().timestamp()}"
                    final_message = {
                        "type": "ai",
                        "content": final_response_content,
                        "id": message_id,
                        "sources": sources
                    }
                    yield format_stream_event("message", final_message, message_id)
                    break
        
        # If no final response was received, provide fallback
        if not final_response_content:
            error_message = "Xin lỗi, tôi không thể tìm được thông tin để trả lời câu hỏi của bạn."
            message_id = f"msg_{datetime.now().timestamp()}"
            error_response = {
                "type": "ai",
                "content": error_message,
                "id": message_id
            }
            yield format_stream_event("message", error_response, message_id)
        
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
    user_messages = [msg for msg in run_request.messages if msg.type in ["human", "user"]]
    if not user_messages:
        raise HTTPException(status_code=400, detail="Xin lỗi, tôi không nhận được câu hỏi nào từ bạn. Vui lòng đặt câu hỏi để tôi có thể giúp đỡ.")
    
    latest_message = user_messages[-1]
    query = latest_message.content
    
    # Use assistant_id as user_id for session management
    user_id = assistant_id or "default_user"
    
    async def generate():
        yield "event: message\n"
        async for chunk in research_and_answer_with_agent(query, user_id):
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