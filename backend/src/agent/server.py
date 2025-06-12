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
from adk_agent_workflow import create_research_agent

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
        # Create agent with specified model and effort settings
        research_agent = create_research_agent(model, initial_search_query_count, max_research_loops)
        
        # Create runner with the dynamic agent
        runner = Runner(
            agent=research_agent,
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
        
        # Add effort level instructions to the user message
        effort_instruction = ""
        if initial_search_query_count == 1:
            effort_instruction = "\n\nMức độ nghiên cứu: Thấp (1 truy vấn tìm kiếm, 1 vòng nghiên cứu)"
        elif initial_search_query_count == 5:
            effort_instruction = "\n\nMức độ nghiên cứu: Cao (5 truy vấn tìm kiếm, 10 vòng nghiên cứu tối đa)"
        else:
            effort_instruction = "\n\nMức độ nghiên cứu: Trung bình (3 truy vấy tìm kiếm, 3 vòng nghiên cứu)"
        
        user_message += effort_instruction
        
        user_content = Content(role='user', parts=[Part(text=user_message)])
        
        # Variables to track the agent's response
        final_response_content = ""
        sources = []
        research_step = "initial"
        research_loops = 0  # Track research loops to enforce max_research_loops
        event_count = 0
        
        # Initial event to show timeline starts
        yield format_stream_event("generate_query", {
            "query": query,
            "status": "initializing"
        })
        
        # Run the agent and process events
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_content
        ):
            event_count += 1
            
            # Handle workflow events (text responses from SequentialAgent)
            if hasattr(event, 'content') and event.content and hasattr(event.content, 'parts'):
                for part in event.content.parts:
                    # Handle text responses from workflow agents
                    if hasattr(part, 'text') and part.text:
                        text_content = part.text.strip()
                        
                        # Detect different workflow stages based on content patterns
                        try:
                            # Try to parse as JSON (agent outputs)
                            if text_content.startswith('```json'):
                                json_content = text_content.replace('```json', '').replace('```', '').strip()
                                parsed_data = json.loads(json_content)
                                
                                # Handle query generation stage
                                if isinstance(parsed_data, list) and event_count <= 3:
                                    yield format_stream_event("generate_query", {
                                        "query_list": parsed_data
                                    })
                                
                                # Handle research results
                                elif isinstance(parsed_data, dict) and parsed_data.get("status") == "success":
                                    if "sources" in str(parsed_data) or "content" in parsed_data:
                                        yield format_stream_event("web_research", {
                                            "sources_gathered": parsed_data.get("sources", []),
                                            "query": query,
                                            "status": "success"
                                        })
                                        if parsed_data.get("sources"):
                                            sources.extend(parsed_data["sources"])
                                
                                # Handle quality analysis
                                elif isinstance(parsed_data, dict) and "confidence" in parsed_data:
                                    yield format_stream_event("reflection", {
                                        "is_sufficient": parsed_data.get("is_sufficient", True),
                                        "confidence": parsed_data.get("confidence", 0.7),
                                        "follow_up_queries": []
                                    })
                                
                                # Handle refinement queries
                                elif isinstance(parsed_data, list) and event_count > 3:
                                    if parsed_data:  # Non-empty list means more research needed
                                        yield format_stream_event("web_research", {
                                            "query": "follow-up research",
                                            "status": "refining"
                                        })
                                        research_loops += 1
                                    else:  # Empty list means research is sufficient
                                        yield format_stream_event("reflection", {
                                            "is_sufficient": True,
                                            "confidence": 0.8,
                                            "reason": "No additional queries needed"
                                        })
                            
                            # Handle final answer (non-JSON text)
                            elif not text_content.startswith('```') and len(text_content) > 100:
                                final_response_content = text_content
                                yield format_stream_event("finalize_answer", {
                                    "status": "synthesizing"
                                })
                                
                        except json.JSONDecodeError:
                            # Handle final answer (non-JSON text)
                            if len(text_content) > 100:
                                final_response_content = text_content
                                yield format_stream_event("finalize_answer", {
                                    "status": "synthesizing"
                                })
                    
                    # Legacy support: Handle function calls if present
                    elif hasattr(part, 'function_call') and part.function_call:
                        tool_name = part.function_call.name

                        
                        if tool_name == "generate_initial_queries":

                            yield format_stream_event("generate_query", {
                                "query": query,
                                "status": "generating"
                            })
                            
                        elif tool_name == "web_research":
                            yield format_stream_event("web_research", {
                                "query": query,
                                "status": "searching"
                            })
                            
                        elif tool_name == "analyze_research_quality":
                            yield format_stream_event("reflection", {
                                "status": "analyzing"
                            })
                            
                        elif tool_name == "iterative_refinement":
                            # Check if we should continue research loops
                            if research_loops < max_research_loops:
                                yield format_stream_event("web_research", {
                                    "query": "follow-up research",
                                    "status": "refining"
                                })
                                research_loops += 1
                            else:
                                yield format_stream_event("reflection", {
                                    "is_sufficient": True,
                                    "confidence": 0.8,
                                    "reason": f"Reached maximum research loops ({max_research_loops})"
                                })
                            
                        elif tool_name == "finalize_answer":
                            yield format_stream_event("finalize_answer", {
                                "status": "synthesizing"
                            })
                    
                    # Handle function responses (tool responses)
                    elif hasattr(part, 'function_response') and part.function_response:
                        tool_name = part.function_response.name
                        tool_result = part.function_response.response

                        
                        if tool_name == "generate_initial_queries":

                            if tool_result and 'result' in tool_result:
                                queries = tool_result['result']
                                if isinstance(queries, list):
                                    yield format_stream_event("generate_query", {
                                        "query_list": queries
                                    })
                                else:
                                    yield format_stream_event("generate_query", {
                                        "query_list": [str(queries)]
                                    })
                            else:
                                yield format_stream_event("generate_query", {
                                    "query_list": [query]
                                })
                                
                        elif tool_name == "web_research":
                            if tool_result and isinstance(tool_result, dict):
                                if tool_result.get("sources"):
                                    sources.extend(tool_result["sources"])
                                    yield format_stream_event("web_research", {
                                        "sources_gathered": tool_result["sources"],
                                        "query": tool_result.get("query", query),
                                        "status": "success"
                                    })
                                else:
                                    yield format_stream_event("web_research", {
                                        "sources_gathered": [],
                                        "query": query,
                                        "status": "completed"
                                    })
                            else:
                                yield format_stream_event("web_research", {
                                    "sources_gathered": [],
                                    "query": query,
                                    "status": "completed"
                                })
                                
                        elif tool_name == "analyze_research_quality":
                            confidence = 0.7  # Default confidence
                            is_sufficient = True
                            follow_up_queries = []
                            
                            if tool_result and isinstance(tool_result, dict):
                                confidence = tool_result.get("confidence", 0.7)
                                status = tool_result.get("status", "sufficient")
                                recommendation = tool_result.get("recommendation", "finalize_answer")
                                is_sufficient = recommendation == "finalize_answer"
                            
                            yield format_stream_event("reflection", {
                                "is_sufficient": is_sufficient,
                                "confidence": confidence,
                                "follow_up_queries": follow_up_queries
                            })
                            
                        elif tool_name == "iterative_refinement":
                            if tool_result and 'result' in tool_result:
                                follow_up_queries = tool_result['result']
                                if isinstance(follow_up_queries, list) and follow_up_queries:
                                    yield format_stream_event("reflection", {
                                        "is_sufficient": False,
                                        "confidence": 0.5,
                                        "follow_up_queries": follow_up_queries
                                    })
                                    
                        elif tool_name == "finalize_answer":
                            if tool_result:
                                final_response_content = str(tool_result)
                                yield format_stream_event("finalize_answer", {
                                    "answer": final_response_content,
                                    "sources": sources,
                                    "confidence": 0.8,
                                    "status": "completed"
                                })
                    
                    # Handle final text response
                    elif hasattr(part, 'text') and part.text and not final_response_content:
                        final_response_content = part.text
                        
                        # Send final message
                        message_id = f"msg_{datetime.now().timestamp()}"
                        final_message = {
                            "type": "ai",
                            "content": final_response_content,
                            "id": message_id,
                            "sources": sources
                        }
                        yield format_stream_event("message", final_message, message_id)
                        return
        
        # If we reach here, send final response if we have one
        if final_response_content:
            message_id = f"msg_{datetime.now().timestamp()}"
            final_message = {
                "type": "ai",
                "content": final_response_content,
                "id": message_id,
                "sources": sources
            }
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