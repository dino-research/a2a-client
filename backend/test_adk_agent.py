#!/usr/bin/env python3
"""
Test script for the ADK research agent.
Run this to verify the agent is working correctly.
"""
import os
import sys
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'agent'))

# Import ADK components
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

# Import the research agent
from adk_agent import research_agent, conduct_comprehensive_research

async def test_research_agent():
    """Test the research agent with a simple query."""
    print("🚀 Starting ADK Research Agent Tests\n")
    
    # Test direct tool first
    print("🔧 Testing tools directly...")
    try:
        print("🔍 Testing direct tool call: Thời tiết Paris hôm nay")
        result = conduct_comprehensive_research("Thời tiết Paris hôm nay")
        print(f"💬 Tool result: {result[:200]}...")
        print("✅ Direct tool test completed successfully!")
    except Exception as e:
        print(f"❌ Error testing direct tool: {e}")
        return

    print("\n🧪 Testing ADK Research Agent...")
    
    # Check API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not found in environment variables")
        return
    
    print(f"✅ API Key configured: {api_key[:20]}...")
    
    try:
        # Initialize session service
        session_service = InMemorySessionService()
        
        # Create session
        APP_NAME = "test_research_agent"
        USER_ID = "test_user"
        SESSION_ID = "test_session"
        
        try:
            # Try async version first (newer ADK versions)
            await session_service.create_session(
                app_name=APP_NAME,
                user_id=USER_ID,
                session_id=SESSION_ID
            )
        except TypeError:
            # Fallback to sync version (older ADK versions)
            session_service.create_session(
                app_name=APP_NAME,
                user_id=USER_ID,
                session_id=SESSION_ID
            )
        
        # Create runner
        runner = Runner(
            agent=research_agent,
            app_name=APP_NAME,
            session_service=session_service
        )
        
        print("✅ ADK components initialized successfully")
        
        # Test query
        test_query = "Thời tiết Hà Nội hôm nay như thế nào?"
        print(f"🔍 Testing query: {test_query}")
        
        user_content = Content(role='user', parts=[Part(text=test_query)])
        
        print("🤖 Running agent...")
        
        # Run the agent and process events
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=SESSION_ID,
            new_message=user_content
        ):
            # Handle different event types based on ADK documentation
            print(f"📨 Event from: {event.author}")
            
            # Check for content
            if hasattr(event, 'content') and event.content:
                if hasattr(event.content, 'parts') and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            if hasattr(event, 'partial') and event.partial:
                                print(f"📄 Streaming: {part.text[:100]}...")
                            else:
                                print(f"📄 Content: {part.text[:200]}...")
                        
                        # Check for function calls
                        if hasattr(part, 'function_call') and part.function_call:
                            print(f"🔧 Tool called: {part.function_call.name}")
                        
                        # Check for function responses
                        if hasattr(part, 'function_response') and part.function_response:
                            print(f"🔧 Tool response received: {part.function_response.name}")
            
            # Check if it's a final response
            if hasattr(event, 'is_final_response') and callable(event.is_final_response):
                if event.is_final_response():
                    print("✅ Final response received!")
                    break
            elif hasattr(event, 'turn_complete') and event.turn_complete:
                print("✅ Turn completed!")
                break
                
        print("✅ ADK Agent test completed successfully!")
        
    except Exception as e:
        print(f"❌ Error testing agent: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

async def main():
    """Main test function."""
    print("\n📊 Test Results:")
    
    # Test direct tools
    try:
        result = conduct_comprehensive_research("Test query")
        print("Direct Tools: ✅ PASSED")
        tool_test_passed = True
    except Exception as e:
        print("Direct Tools: ❌ FAILED")
        print(f"Error: {e}")
        tool_test_passed = False
    
    # Test ADK agent
    agent_test_passed = await test_research_agent()
    
    if tool_test_passed and agent_test_passed:
        print("\n🎉 All tests passed! Your ADK research agent is ready to use.")
        print("\n🚀 Next steps:")
        print("1. Run the server: make dev-backend")
        print("2. Run the frontend: make dev-frontend") 
        print("3. Open http://localhost:3000 to start chatting!")
    else:
        print("\n💥 Some tests failed. Please check the configuration.")

if __name__ == "__main__":
    asyncio.run(main()) 