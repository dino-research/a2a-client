#!/usr/bin/env python3
"""
ADK Agent Runner - Follows Google ADK v1.0.0 best practices
Run this script to interact with the research agent via command line.
"""

import os
import sys
from pathlib import Path

# Add the current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from adk_agent import research_agent

def main():
    """
    Simple command-line interface for the research agent.
    Following ADK documentation patterns.
    """
    print("🤖 Research Agent - Powered by Google ADK")
    print("Type 'quit' to exit")
    print("-" * 50)
    
    try:
        while True:
            # Get user input
            user_input = input("\nYou > ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("Goodbye! 👋")
                break
                
            if not user_input:
                continue
                
            print("\nAgent > ", end="", flush=True)
            
            # For simple CLI usage, we can call tools directly
            # In a full ADK setup, you'd use Runner with SessionService
            try:
                # Perform research
                research_result = research_agent.tools[0](user_input)  # web_research
                
                if research_result.get("status") == "error":
                    print(f"❌ Research failed: {research_result.get('error')}")
                    continue
                
                # Generate answer
                final_result = research_agent.tools[2](user_input, [research_result])  # generate_final_answer
                
                if final_result.get("status") == "success":
                    print(final_result.get("answer"))
                    
                    # Show sources if available
                    sources = final_result.get("sources", [])
                    if sources:
                        print(f"\n📚 Sources ({len(sources)}):")
                        for i, source in enumerate(sources[:3], 1):  # Show first 3 sources
                            print(f"  {i}. {source.get('title', 'Unknown')} - {source.get('url', '')}")
                else:
                    print(f"❌ {final_result.get('answer')}")
                    
            except Exception as e:
                print(f"❌ Error: {str(e)}")
                
    except KeyboardInterrupt:
        print("\n\nGoodbye! 👋")
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")

if __name__ == "__main__":
    # Check for required environment variables
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ Error: GEMINI_API_KEY environment variable is required")
        print("Please set your Gemini API key in the .env file")
        sys.exit(1)
        
    main() 