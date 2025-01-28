#!/usr/bin/env python3

import os
from openai import OpenAI
from dotenv import load_dotenv

def test_deepseek_api():
    # Load environment variables from .env file
    load_dotenv()
    
    # Initialize the client with DeepSeek configuration
    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com"
    )
    
    # Test message
    messages = [
        {"role": "system", "content": "You are a helpful AI assistant."},
        {"role": "user", "content": "What's 2 + 2?"}
    ]
    
    try:
        # Create a streaming chat completion
        stream = client.chat.completions.create(
            model="deepseek-reasoner",
            messages=messages,
            stream=True
        )
        
        print("\nAPI Response:")
        print("-" * 50)
        
        # Track content separately
        reasoning_content = ""
        final_content = ""
        
        for chunk in stream:
            # Handle reasoning content
            if chunk.choices[0].delta.reasoning_content:
                reasoning_part = chunk.choices[0].delta.reasoning_content
                reasoning_content += reasoning_part
            
            # Handle final content
            elif chunk.choices[0].delta.content:
                content_part = chunk.choices[0].delta.content
                final_content += content_part
        
        # Print both reasoning and final content
        if reasoning_content:
            print("Reasoning:")
            print(reasoning_content)
            print("-" * 50)
        
        print("Final Answer:")
        print(final_content)
        print("-" * 50)
        
    except Exception as e:
        print(f"\nError: {str(e)}")

if __name__ == "__main__":
    print("Testing DeepSeek API...")
    test_deepseek_api()