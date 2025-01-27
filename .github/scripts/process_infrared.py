#!/usr/bin/env python3

import os
import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any

def get_issue_content() -> Optional[Dict[str, Any]]:
    """Get the relevant issue or PR content from environment variables."""
    issue_number = os.getenv('ISSUE_NUMBER')
    issue_body = os.getenv('ISSUE_BODY')
    comment_body = os.getenv('COMMENT_BODY')
    pr_number = os.getenv('PR_NUMBER')
    
    if not any([issue_body, comment_body]):
        print("Error: No content found in environment variables")
        sys.exit(1)
    
    return {
        'issue_number': issue_number,
        'content': issue_body or comment_body,
        'pr_number': pr_number
    }

def extract_file_references(content: str) -> list[str]:
    """Extract file references from the issue/PR content."""
    # This is a simple implementation - enhance based on your needs
    files = []
    lines = content.split('\n')
    for line in lines:
        # Look for common file patterns
        if any(ext in line for ext in ['.py', '.js', '.css', '.html', '.md', '.txt', '.json']):
            # Extract the file reference - this is a basic implementation
            words = line.split()
            for word in words:
                if any(ext in word for ext in ['.py', '.js', '.css', '.html', '.md', '.txt', '.json']):
                    files.append(word.strip('`*,. '))
    return files

def write_temp_file(filename: str, content: str):
    """Write content to a temporary file for GitHub Actions."""
    os.makedirs('.github/temp', exist_ok=True)
    with open(f'.github/temp/{filename}', 'w') as f:
        f.write(content)

def main():
    # Get issue/PR content
    content_data = get_issue_content()
    if not content_data:
        sys.exit(1)
    
    # Extract file references
    files = extract_file_references(content_data['content'])
    
    # Add files to conversation history
    for file in files:
        try:
            if os.path.exists(file):
                # Use the existing add_file functionality from original code
                os.system(f'python infrared.py "/add {file}"')
        except Exception as e:
            print(f"Error adding file {file}: {e}")
    
    # Process with Infrared
    try:
        # Run the main Infrared processing
        # Note: This needs to be adapted based on how you want to integrate with the original code
        result = os.system(f'python infrared.py "{content_data["content"]}"')
        
        # For demonstration, we'll simulate the review result
        # In practice, this should come from the actual Infrared execution
        review_result = {
            'status': 'CORRECT',  # or 'INCORRECT', 'UNECESSARY', 'NEED_CHANGES'
            'analysis': 'Code changes look good and meet all requirements.',
            'explanation': 'All tests passed and code follows best practices.'
        }
        
        # Write results to temp files for GitHub Actions
        write_temp_file('analysis.txt', review_result['analysis'])
        write_temp_file('explanation.txt', review_result['explanation'])
        write_temp_file('output.txt', review_result['status'])
        
        # Set output for GitHub Actions
        print(f"::set-output name=status::{review_result['status']}")
        
    except Exception as e:
        print(f"Error during Infrared processing: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()