#!/usr/bin/env python3
"""
Test script for coordinator agent functionality.
Tests both direct answer and web research paths.
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
from src.agent.adk_agent_workflow import create_research_agent

# Import ADK components
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

async def test_coordinator_agent():
    """Test the coordinator agent with different types of questions."""
    
    # Test questions
    test_cases = [
        {
            "question": "Tôi là Thái",
            "expected_type": "direct_answer",
            "description": "Personal introduction"
        },
        {
            "question": "2 + 2 = ?",
            "expected_type": "direct_answer", 
            "description": "Basic math"
        },
        {
            "question": "Xin chào",
            "expected_type": "direct_answer",
            "description": "Greeting"
        },
        {
            "question": "Thời tiết Hà Nội hôm nay thế nào",
            "expected_type": "web_research",
            "description": "Weather requiring web search"
        },
        {
            "question": "Tình hình kinh tế Việt Nam mới nhất",
            "expected_type": "web_research",
            "description": "Current news requiring web search"
        },
        {
            "question": "Giá bitcoin hôm nay",
            "expected_type": "web_research", 
            "description": "Live data requiring web search"
        }
    ]
    
    # Initialize ADK components
    session_service = InMemorySessionService()
    research_agent = create_research_agent("gemini-2.0-flash", 2, 2)  # Lower settings for testing
    
    runner = Runner(
        agent=research_agent,
        app_name="test_coordinator_agent",
        session_service=session_service
    )
    
    # Create session
    user_id = "test_user"
    session_id = "test_session"
    
    try:
        await session_service.create_session(
            app_name="test_coordinator_agent",
            user_id=user_id,
            session_id=session_id
        )
    except:
        pass  # Session may already exist
    
    print("🧪 Testing Coordinator Agent Functionality")
    print("=" * 60)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 Test {i}: {test_case['description']}")
        print(f"❓ Question: {test_case['question']}")
        print(f"🎯 Expected: {test_case['expected_type']}")
        print("-" * 40)
        
        try:
            # Create user content
            user_content = Content(role='user', parts=[Part(text=test_case['question'])])
            
            # Run the agent
            response_collected = False
            coordinator_decision = None
            
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_content
            ):
                if hasattr(event, 'content') and event.content and hasattr(event.content, 'parts'):
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            text = part.text.strip()
                            
                            # Try to detect web research trigger
                            if text.startswith('{') and 'web_research_needed' in text:
                                import json
                                try:
                                    coordinator_decision = json.loads(text)
                                    print(f"✅ Coordinator Decision: web_research")
                                    print(f"💭 Reasoning: {coordinator_decision.get('reasoning', 'N/A')}")
                                except:
                                    pass
                            # Try to detect coordinator decision (legacy)
                            elif '```json' in text and 'response_type' in text:
                                import json
                                try:
                                    json_content = text.replace('```json', '').replace('```', '').strip()
                                    coordinator_decision = json.loads(json_content)
                                    print(f"✅ Coordinator Decision: {coordinator_decision.get('response_type', 'unknown')}")
                                    print(f"💭 Reasoning: {coordinator_decision.get('reasoning', 'N/A')}")
                                except:
                                    pass
                            
                            # Detect direct response (most common case)
                            elif len(text) > 20 and not text.startswith('```') and not text.startswith('{'):
                                print(f"✅ Coordinator Decision: direct_answer")
                                print(f"💬 Response: {text[:100]}...")
                                coordinator_decision = {"response_type": "direct_answer"}
                                response_collected = True
                                break
                
                if response_collected:
                    break
            
            if coordinator_decision:
                actual_type = coordinator_decision.get('response_type', 'unknown')
                # Map web_research_needed to web_research for comparison
                if coordinator_decision.get('action') == 'web_research_needed':
                    actual_type = 'web_research'
                    
                if actual_type == test_case['expected_type']:
                    print(f"✅ SUCCESS: Correct classification")
                else:
                    print(f"❌ FAILED: Expected {test_case['expected_type']}, got {actual_type}")
            else:
                print(f"⚠️  WARNING: Could not detect coordinator decision")
                
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
        
        print()
    
    print("🏁 Testing completed!")

if __name__ == "__main__":
    # Check if required environment variables are set
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ Error: GEMINI_API_KEY environment variable not set")
        print("Please add your Gemini API key to the .env file")
        sys.exit(1)
    
    # Run the test
    asyncio.run(test_coordinator_agent()) 