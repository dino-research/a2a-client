#!/usr/bin/env python3
"""
Simple debug script for coordinator agent.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

# Import the research agent
from src.agent.adk_agent_workflow import create_coordinator_workflow_agent

# Import ADK components
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

async def debug_coordinator():
    """Debug coordinator agent with simple questions."""
    
    # Test question
    question = "Chào bạn, Tôi là Thái"
    
    print(f"🧪 Debug Coordinator Agent")
    print(f"❓ Question: {question}")
    print("=" * 50)
    
    # Create coordinator agent
    coordinator = create_coordinator_workflow_agent("gemini-2.0-flash")
    
    # Initialize ADK components
    session_service = InMemorySessionService()
    
    runner = Runner(
        agent=coordinator,
        app_name="debug_coordinator",
        session_service=session_service
    )
    
    # Create session
    user_id = "debug_user"
    session_id = "debug_session"
    
    try:
        await session_service.create_session(
            app_name="debug_coordinator",
            user_id=user_id,
            session_id=session_id
        )
    except:
        pass  # Session may already exist
    
    # Create user content
    user_content = Content(role='user', parts=[Part(text=question)])
    
    print("📤 Sending to coordinator agent...")
    
    # Run the agent
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_content
    ):
        if hasattr(event, 'content') and event.content and hasattr(event.content, 'parts'):
            for part in event.content.parts:
                if hasattr(part, 'text') and part.text:
                    text = part.text.strip()
                    print(f"📥 Response from coordinator:")
                    print(f"Type: {type(text)}")
                    print(f"Length: {len(text)}")
                    print(f"Starts with JSON: {text.startswith('{')}")
                    print(f"Content: {text}")
                    print("-" * 40)
                    
                    # Analyze response type
                    if text.startswith('{') and 'web_research_needed' in text:
                        print("✅ DETECTED: Web research trigger")
                    elif len(text) > 20 and not text.startswith('{'):
                        print("✅ DETECTED: Direct answer")
                    else:
                        print("❓ DETECTED: Unknown response type")
                    
                    return

if __name__ == "__main__":
    # Check if required environment variables are set
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ Error: GEMINI_API_KEY environment variable not set")
        print("Please add your Gemini API key to the .env file")
        sys.exit(1)
    
    # Run the debug
    asyncio.run(debug_coordinator()) 