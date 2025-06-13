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
import asyncio
from pprint import pformat

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
# from adk_agent_workflow import create_research_agent, create_coordinator_agent
from routing_agent import root_agent as routing_agent, get_root_agent

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

# Note: Runner is now created dynamically in research_and_answer_with_agent function
# to support different models and effort settings per request

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

def _extract_response_text(response_content) -> str:
    """Extract text from function response content."""
    if isinstance(response_content, dict) and "result" in response_content:
        task_result = response_content["result"]
        if hasattr(task_result, 'artifacts') and task_result.artifacts:
            text_parts = []
            for artifact in task_result.artifacts:
                if hasattr(artifact, 'parts') and artifact.parts:
                    for part_item in artifact.parts:
                        if hasattr(part_item, 'root') and hasattr(part_item.root, 'text'):
                            text_parts.append(part_item.root.text)
            return "\n".join(text_parts)
        return str(task_result)
    elif isinstance(response_content, dict) and "response" in response_content:
        return response_content["response"]
    return str(response_content)

def _find_function_name(event) -> str:
    """Find function name from event parts."""
    if event.content and event.content.parts:
        for part in event.content.parts:
            if part.function_call:
                return part.function_call.name
    return None

def _find_agent_name_from_event(event) -> str:
    """Find agent name from function call args in event parts."""
    if event.content and event.content.parts:
        for part in event.content.parts:
            if part.function_call and part.function_call.args:
                return part.function_call.args.get('agent_name')
    return None

async def research_and_answer_with_agent(
    query: str, 
    user_id: str = "default_user", 
    conversation_context: str = "",
    model: str = "gemini-2.0-flash",
    initial_search_query_count: int = 3,
    max_research_loops: int = 3
) -> AsyncGenerator[str, None]:
    """Research query using ADK agent and provide streaming response."""
    try:
        # Create coordinator agent instead of research agent
        # research_agent = create_coordinator_agent(model)
        
        # Get the routing agent (with lazy initialization if needed)
        if routing_agent is None:
            agent = await get_root_agent()
        else:
            agent = routing_agent
        
        # Create runner with the dynamic agent
        runner = Runner(
            agent=agent,
            app_name=APP_NAME,
            session_service=session_service
        )
        
        # Use a persistent session for each user to maintain context
        session_id = f"session_{user_id}"
        
        # Always ensure session exists - create if needed, reuse if exists
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
        except Exception:
            # Session may already exist, which is fine - we'll reuse it
            pass
        
        # Yield initial query generation event
        yield format_stream_event("generate_query", {
            "query_list": [query]
        })
        
        # Create user content for ADK - include conversation context if available
        user_message = query
        if conversation_context:
            user_message = f"Bối cảnh cuộc hội thoại trước:\n{conversation_context}\n\nCâu hỏi hiện tại: {query}"
        
        user_content = Content(role='user', parts=[Part(text=user_message)])
        
        # Variables to track the agent's response
        final_response_content = ""
        sources = []
        
        # Initial event to show timeline starts
        # yield format_stream_event("generate_query", {
        #     "query": query,
        #     "status": "analyzing_question"
        # })
        
        # Track current agent name for function responses
        current_agent_name = None
        
        # Run the agent and process events
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=user_content):
            if event.content and event.content.parts:
                # Collect text content from all responses
                text_parts = [p.text for p in event.content.parts if p.text]
                if text_parts:
                    current_text = "".join(text_parts)
                    if current_text.strip():
                        final_response_content += current_text
                
                # Process function calls and responses
                for part in event.content.parts:
                    if part.function_call:
                        # Extract actual agent name from function args
                        current_agent_name = part.function_call.args.get('agent_name', part.function_call.name)
                        yield format_stream_event("remote_agent_call", {
                            "agent_name": current_agent_name,
                        })
                    elif part.function_response:
                        formatted_response_data = _extract_response_text(part.function_response.response)
                        # Use the agent name from the most recent function call
                        agent_name = current_agent_name or "Remote Agent"
                        
                        yield format_stream_event("remote_agent_call", {
                            "agent_name": agent_name,
                            "answer": formatted_response_data
                        })
            
            # Handle escalation
            if event.is_final_response() and event.actions and event.actions.escalate:
                final_response_content += f"Agent escalated: {event.error_message or 'No specific message.'}"
            
            
        # Send finalize event before final message
        yield format_stream_event("finalize_answer", {
            "status": "synthesizing"
        })
        
        # If we reach here, send final response if we have one
        if final_response_content:
            message_id = f"msg_{datetime.now().timestamp()}"
            final_message = {
                "type": "ai",
                "content": final_response_content,
                "id": message_id,
                "sources": sources
            }
            
            # Send finalize completion event
            yield format_stream_event("finalize_answer", {
                "status": "completed"
            })
            
            yield format_stream_event("message", final_message, message_id)
        else:
            # Fallback message if no response was captured
            error_message = "Xin lỗi, tôi không thể tìm được thông tin để trả lời câu hỏi của bạn."
            message_id = f"msg_{datetime.now().timestamp()}"
            error_response = {
                "type": "ai",
                "content": error_message,
                "id": message_id
            }
            
            # Send finalize completion event even for errors
            yield format_stream_event("finalize_answer", {
                "status": "completed"
            })
            
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
    # Get all messages to maintain conversation context
    if not run_request.messages:
        raise HTTPException(status_code=400, detail="Xin lỗi, tôi không nhận được câu hỏi nào từ bạn. Vui lòng đặt câu hỏi để tôi có thể giúp đỡ.")
    
    # Get the latest user message
    user_messages = [msg for msg in run_request.messages if msg.type in ["human", "user"]]
    if not user_messages:
        raise HTTPException(status_code=400, detail="Xin lỗi, tôi không nhận được câu hỏi nào từ bạn. Vui lòng đặt câu hỏi để tôi có thể giúp đỡ.")
    
    latest_message = user_messages[-1]
    query = latest_message.content
    
    # Use assistant_id as user_id for session management, but ensure it's valid
    user_id = assistant_id if assistant_id and assistant_id != "agent" else f"user_{assistant_id}"
    
    # Build conversation context from previous messages (limit to last 10 messages for performance)
    conversation_context = ""
    if len(run_request.messages) > 1:
        recent_messages = run_request.messages[-11:-1]  # Get last 10 messages excluding current
        context_parts = []
        for msg in recent_messages:
            role = "Người dùng" if msg.type in ["human", "user"] else "Trợ lý"
            context_parts.append(f"{role}: {msg.content}")
        conversation_context = "\n".join(context_parts)
    
    async def generate():
        yield "event: message\n"
        async for chunk in research_and_answer_with_agent(
            query, 
            user_id, 
            conversation_context, 
            run_request.reasoning_model or "gemini-2.0-flash",
            run_request.initial_search_query_count or 3,
            run_request.max_research_loops or 3
        ):
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