#!/usr/bin/env python3
"""
Test LLM reasoning capability for intelligent question classification.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from src.agent.adk_agent_workflow import create_coordinator_workflow_agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

async def test_llm_reasoning():
    """Test LLM's reasoning ability for question classification."""
    
    test_cases = [
        {"question": "Tôi tên Nam", "expected": "direct", "category": "Personal"},
        {"question": "7 x 8 = ?", "expected": "direct", "category": "Math"},
        {"question": "Thủ đô Pháp là gì?", "expected": "direct", "category": "Static fact"},
        {"question": "Giá vàng hôm nay", "expected": "web_research", "category": "Real-time data"},
        {"question": "Thời tiết TPHCM", "expected": "web_research", "category": "Current weather"},
        {"question": "Cách nấu phở", "expected": "direct", "category": "General knowledge"},
        {"question": "Tin tức mới nhất", "expected": "web_research", "category": "Current news"},
    ]
    
    print("🧠 Testing LLM Reasoning for Question Classification")
    print("=" * 60)
    
    coordinator = create_coordinator_workflow_agent("gemini-2.0-flash")
    session_service = InMemorySessionService()
    runner = Runner(agent=coordinator, app_name="test_reasoning", session_service=session_service)
    
    user_id = "test_user"
    session_id = "test_session"
    
    try:
        await session_service.create_session(app_name="test_reasoning", user_id=user_id, session_id=session_id)
    except:
        pass
    
    correct = 0
    total = len(test_cases)
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n📋 Test {i}: {case['category']}")
        print(f"❓ Question: {case['question']}")
        print(f"🎯 Expected: {case['expected']}")
        
        user_content = Content(role='user', parts=[Part(text=case['question'])])
        actual = None
        
        async for event in runner.run_async(user_id=user_id, session_id=f"{session_id}_{i}", new_message=user_content):
            if hasattr(event, 'content') and event.content:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        text = part.text.strip()
                        
                        if text.startswith('{') and 'web_research_needed' in text:
                            actual = "web_research"
                            print("🔍 LLM: Web Research")
                        elif len(text) > 10 and not text.startswith('{'):
                            actual = "direct"
                            print("💬 LLM: Direct Answer")
                        break
            break
        
        if actual == case['expected']:
            print("✅ CORRECT")
            correct += 1
        else:
            print(f"❌ INCORRECT (got {actual})")
    
    accuracy = (correct / total) * 100
    print(f"\n🏆 Results: {correct}/{total} correct ({accuracy:.1f}%)")
    
    if accuracy >= 80:
        print("🎉 Excellent LLM reasoning!")
    else:
        print("⚠️  LLM reasoning needs improvement")

if __name__ == "__main__":
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ GEMINI_API_KEY not set")
        sys.exit(1)
    
    asyncio.run(test_llm_reasoning()) 