#!/usr/bin/env python3

import os
import sys
import json
from pathlib import Path
from textwrap import dedent
from typing import List, Dict, Any, Optional, Tuple
from openai import OpenAI
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.style import Style
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style as PromptStyle

# Initialize Rich console and prompt session
console = Console()
prompt_session = PromptSession(
    style=PromptStyle.from_dict({
        'prompt': '#00aa00 bold',  # Green prompt
    })
)

# --------------------------------------------------------------------------------
# 1. Configure OpenAI client and load environment variables
# --------------------------------------------------------------------------------
load_dotenv()  # Load environment variables from .env file
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)  # Configure for DeepSeek API

# --------------------------------------------------------------------------------
# 2. Define our schema using Pydantic for type safety
# --------------------------------------------------------------------------------
class FileToCreate(BaseModel):
    path: str
    content: str

class FileToEdit(BaseModel):
    path: str
    original_snippet: str
    new_snippet: str

class AssistantResponse(BaseModel):
    assistant_reply: Optional[str] = None
    files_to_create: Optional[List[FileToCreate]] = None
    files_to_edit: Optional[List[FileToEdit]] = None
    analysis: Optional[str] = None
    explanation: Optional[str] = None
    output: Optional[str] = Field(None, pattern=r'^(CORRECT|INCORRECT|UNECESSARY|NEED_CHANGES)$')

# --------------------------------------------------------------------------------
# 3. system prompts
# --------------------------------------------------------------------------------
planning_system_PROMPT = dedent("""\
    You are an elite software engineer tasked with creating detailed implementation plans.
    Your job is to analyze user requirements and create a step-by-step plan that will guide the implementation.

    Output Format:
    Respond STRICTLY in this JSON format:
    {
      "assistant_reply": "text string with plan using markdown formatting"
    }

    Planning Requirements:
    1. Break down the problem into clear implementation steps
    2. Identify all affected files and components
    3. Highlight potential edge cases and error conditions
    4. Consider security implications and performance impacts
    5. Outline validation and testing approaches
    6. Suggest appropriate architectural patterns
    7. Evaluate alternative solutions if applicable
    8. Define success criteria for implementation

    Critical Instructions:
    - assistant_reply MUST be a plain text string
    - Use '\n' for new lines, NOT actual newlines in JSON
    - NEVER include other fields like files_to_create/edit
    - Escape all double quotes in text content
    - Example valid response: {"assistant_reply": "1. First step\n2. Second step"}
""")

review_system_PROMPT = dedent("""\
    You are an elite software engineer tasked with reviewing code changes.
    Your job is to analyze proposed code changes and determine if they correctly and completely solve the problem while adhering to all guidelines.

    Input format:
    {
        "total_new_files": 0,
        "total_edits": N,  // Number of distinct edits
        "changes": [
            {
            "change_type": "file_edit",
            "path": "path/to/file",
            "original": "exact code snippet that will be replaced",
            "new": "new code snippet that will replace the original"
            },
            // ... additional changes
        ]
    }
                              
    This format allows the review function to make accurate determinations about whether the changes should be marked as CORRECT, INCORRECT, UNNECESSARY, or NEED_CHANGES based on a clear view of exactly what is being modified.

    Review Requirements:
    1. State which change you are reviewing from previous system input.
    2. Analyze each of the diffs provided in 'changes'
    3. Evaluate them based on the review criteria
    4. Provide a detailed analysis of the changes
    5. Explain why the changes are either CORRECT, INCORRECT, UNECESSARY, or NEED_CHANGES
                              

    Output Format:
    Respond STRICTLY in this JSON format:
    {
      "analysis": "Detailed analysis of the overall code changes",
      "explanation": "Brief justification for the output status",
      "output": "One of [CORRECT, INCORRECT, UNECESSARY, NEED_CHANGES]"
    }
    

    Review Criteria:
    1. COMPLETENESS: Do the changes fully address the problem requirements?
    2. CORRECTNESS: Does the code follow technical specifications and avoid errors?
    3. FOCUS: Are changes limited to the problem scope without unnecessary expansions?
    4. QUALITY: Does the code follow best practices and maintain existing standards?
    5. SAFETY: Are all security checks and validations in place?

    Analysis Guidelines:
    - Check for type errors, syntax errors, and security vulnerabilities
    - The goal is to evaluate the changes provided
    - You must first acknowledge what the changes are before providing a review
    - Ensure no existing functionality is broken
    - Confirm changes don't include unrelated modifications
    - Validate proper error handling and edge case coverage

    Output Status Definitions:
    - CORRECT: Changes perfectly solve the problem with no issues
    - INCORRECT: Changes contain too many errors to be fixed or does not address the problem
    - UNECESSARY: Changes include scope creep or unrelated modifications
    - NEED_CHANGES: Partially correct but requires specific adjustments

    Critical Instructions:
    - output MUST be exactly one of the allowed statuses
    - analysis MUST be a single paragraph
    - explanation MUST be 1-2 sentences
    - Escape all double quotes in text content
""")

system_PROMPT = dedent("""\
    You are an elite software engineer called DeepSeek Engineer with decades of experience across all programming domains.
    Your expertise spans system design, algorithms, testing, and best practices.
    You provide thoughtful, well-structured solutions while explaining your reasoning.

    Core capabilities:
    1. Code Analysis & Discussion
       - Analyze code with expert-level insight
       - Explain complex concepts clearly
       - Suggest optimizations and best practices
       - Debug issues with precision

    2. File Operations:
       a) Read existing files
          - Access user-provided file contents for context
          - Analyze multiple files to understand project structure
       
       b) Create new files
          - Generate complete new files with proper structure
          - Create complementary files (tests, configs, etc.)
       
       c) Edit existing files
          - Make precise changes using diff-based editing
          - Modify specific sections while preserving context
          - Suggest refactoring improvements

    3. Implementation Planning
       - Create detailed execution plans before writing code
       - Break down complex problems into sequential steps
       - Identify affected components and dependencies
       - Evaluate multiple implementation strategies
       - Highlight security, performance, and error handling considerations
       - Outline testing and validation approaches

    Output Format:
    You must provide responses in this JSON structure:
    {
      "assistant_reply": "Your main explanation or response",
      "files_to_create": [
        {
          "path": "path/to/new/file",
          "content": "complete file content"
        }
      ],
      "files_to_edit": [
        {
          "path": "path/to/existing/file",
          "original_snippet": "exact code to be replaced",
          "new_snippet": "new code to insert"
        }
      ]
    }

    Guidelines:
    1. YOU ONLY RETURN JSON, NO OTHER TEXT OR EXPLANATION OUTSIDE THE JSON!!!
    2. For normal responses, use 'assistant_reply'
    3. When creating files, include full content in 'files_to_create'
    4. For editing files:
       - Use 'files_to_edit' for precise changes
       - Include enough context in original_snippet to locate the change
       - Ensure new_snippet maintains proper indentation
       - Prefer targeted edits over full file replacements
    5. Always begin with a detailed implementation plan in 'assistant_reply' that:
       - Outlines step-by-step approach to solve the problem
       - Identifies relevant files and components involved
       - Addresses potential edge cases and error conditions
       - Considers security and performance implications
       - Proposes testing and validation strategy
    6. Always explain your changes and reasoning
    6. Consider edge cases and potential impacts
    7. Follow language-specific best practices
    8. Suggest tests or validation steps when appropriate

    Remember: You're a senior engineer - be thorough, precise, and thoughtful in your solutions.

    Technical Reference:
    - Always consult and strictly adhere to the technical stack documentation in tech_stack.md
    - Validate all implementations against version requirements in tech_stack.md
""")

# --------------------------------------------------------------------------------
# 4. Helper functions 
# --------------------------------------------------------------------------------

def read_local_file(file_path: str) -> str:
    """Return the text content of a local file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def create_file(path: str, content: str):
    """Create (or overwrite) a file at 'path' with the given 'content'."""
    file_path = Path(path)
    
    # Security checks
    if any(part.startswith('~') for part in file_path.parts):
        raise ValueError("Home directory references not allowed")
    normalized_path = normalize_path(str(file_path))
    
    # Validate reasonable file size for operations
    if len(content) > 5_000_000:  # 5MB limit
        raise ValueError("File content exceeds 5MB size limit")
    
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    console.print(f"[green]✓[/green] Created/updated file at '[cyan]{file_path}[/cyan]'")
    
    # Record the action as a system message
    conversation_history.append({
        "role": "system",
        "content": f"File operation: Created/updated file at '{file_path}'"
    })
    
    normalized_path = normalize_path(str(file_path))
    conversation_history.append({
        "role": "system",
        "content": f"Content of file '{normalized_path}':\n\n{content}"
    })

def show_diff_table(files_to_edit: List[FileToEdit]) -> None:
    if not files_to_edit:
        return
    
    table = Table(title="Proposed Edits", show_header=True, header_style="bold magenta", show_lines=True)
    table.add_column("File Path", style="cyan")
    table.add_column("Original", style="red")
    table.add_column("New", style="green")

    for edit in files_to_edit:
        table.add_row(edit.path, edit.original_snippet, edit.new_snippet)
    
    console.print(table)

def apply_diff_edit(path: str, original_snippet: str, new_snippet: str):
    """Reads the file at 'path', replaces the first occurrence of 'original_snippet' with 'new_snippet', then overwrites."""
    try:
        content = read_local_file(path)
        
        # Verify we're replacing the exact intended occurrence
        occurrences = content.count(original_snippet)
        if occurrences == 0:
            raise ValueError("Original snippet not found")
        if occurrences > 1:
            console.print(f"[yellow]Multiple matches ({occurrences}) found - requiring line numbers for safety", style="yellow")
            console.print("Use format:\n--- original.py (lines X-Y)\n+++ modified.py\n")
            raise ValueError(f"Ambiguous edit: {occurrences} matches")
        
        updated_content = content.replace(original_snippet, new_snippet, 1)
        create_file(path, updated_content)
        console.print(f"[green]✓[/green] Applied diff edit to '[cyan]{path}[/cyan]'")
        # Record the edit as a system message
        conversation_history.append({
            "role": "system",
            "content": f"File operation: Applied diff edit to '{path}'"
        })
    except FileNotFoundError:
        console.print(f"[red]✗[/red] File not found for diff editing: '[cyan]{path}[/cyan]'", style="red")
    except ValueError as e:
        console.print(f"[yellow]⚠[/yellow] {str(e)} in '[cyan]{path}[/cyan]'. No changes made.", style="yellow")
        console.print("\nExpected snippet:", style="yellow")
        console.print(Panel(original_snippet, title="Expected", border_style="yellow"))
        # console.print("\nActual file content:", style="yellow")
        console.print(Panel(content, title="Actual", border_style="yellow"))

def try_handle_add_command(user_input: str) -> bool:
    prefix = "/add "
    if user_input.strip().lower().startswith(prefix):
        path_to_add = user_input[len(prefix):].strip()
        try:
            normalized_path = normalize_path(path_to_add)
            if os.path.isdir(normalized_path):
                # Handle entire directory
                add_directory_to_conversation(normalized_path)
            else:
                # Handle a single file as before
                content = read_local_file(normalized_path)
                conversation_history.append({
                    "role": "system",
                    "content": f"Content of file '{normalized_path}':\n\n{content}"
                })
                console.print(f"[green]✓[/green] Added file '[cyan]{normalized_path}[/cyan]' to conversation.\n")
        except OSError as e:
            console.print(f"[red]✗[/red] Could not add path '[cyan]{path_to_add}[/cyan]': {e}\n", style="red")
        return True
    return False

def get_file_content_from_history(file_path: str, conversation_history: List[Dict[str, str]]) -> Optional[str]:
    """
    Retrieve file content from conversation history by path.
    
    Args:
        file_path: The normalized path of the file to find
        conversation_history: The list of conversation messages
        
    Returns:
        The file content if found, None otherwise
    """
    normalized_path = normalize_path(file_path)
    file_marker = f"Content of file '{normalized_path}'"
    
    for msg in conversation_history:
        if msg["role"] == "system" and file_marker in msg["content"]:
            # Extract content after the marker
            content = msg["content"].split(file_marker + ":\n\n", 1)
            if len(content) > 1:
                return content[1]
    return None

def add_directory_to_conversation(directory_path: str) -> Tuple[List[str], List[str]]:
    """
    Add all suitable files from a directory to conversation history.
    
    Args:
        directory_path: Path to the directory to process
        
    Returns:
        Tuple of (added_files, skipped_files) lists
    """
    added_files = []
    skipped_files = []
    
    with console.status("[bold green]Scanning directory...") as status:
        excluded_files = {
            ".git", "__pycache__", "node_modules",
            ".env", ".venv", "venv",
            ".DS_Store", "Thumbs.db"
        }
        excluded_extensions = {
            ".pyc", ".pyo", ".pyd",
            ".exe", ".dll", ".so",
            ".zip", ".tar", ".gz",
            ".jpg", ".png", ".pdf"
        }
        
        for root, dirs, files in os.walk(directory_path):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in excluded_files]
            
            for file in files:
                if any((
                    file.startswith('.'),
                    file in excluded_files,
                    Path(file).suffix.lower() in excluded_extensions
                )):
                    skipped_files.append(os.path.join(root, file))
                    continue
                    
                try:
                    full_path = os.path.join(root, file)
                    if os.path.getsize(full_path) > 5_000_000:  # 5MB limit
                        skipped_files.append(f"{full_path} (size limit exceeded)")
                        continue
                        
                    if is_binary_file(full_path):
                        skipped_files.append(f"{full_path} (binary file)")
                        continue
                        
                    if ensure_file_in_context(full_path):
                        added_files.append(full_path)
                        
                except OSError as e:
                    skipped_files.append(f"{full_path} ({str(e)})")
                    
        return added_files, skipped_files

def is_binary_file(file_path: str, peek_size: int = 1024) -> bool:
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(peek_size)
        # If there is a null byte in the sample, treat it as binary
        if b'\0' in chunk:
            return True
        return False
    except Exception:
        # If we fail to read, just treat it as binary to be safe
        return True

def ensure_file_in_context(file_path: str) -> bool:
    """
    Ensures a file's content is available in conversation history.
    
    Args:
        file_path: Path to the file to check/add
        
    Returns:
        True if file is in context (either already there or successfully added),
        False if file couldn't be read
    """
    try:
        normalized_path = normalize_path(file_path)
        
        # First check if already in history
        existing_content = get_file_content_from_history(normalized_path, conversation_history)
        if existing_content is not None:
            return True
            
        # If not found, try to read and add
        content = read_local_file(normalized_path)
        conversation_history.append({
            "role": "system",
            "content": f"Content of file '{normalized_path}':\n\n{content}"
        })
        return True
        
    except OSError as e:
        console.print(f"[red]✗[/red] Could not read file '[cyan]{file_path}[/cyan]': {str(e)}", style="red")
        return False

def normalize_path(path_str: str) -> str:
    """Return a canonical, absolute version of the path with security checks."""
    path = Path(path_str).resolve()
    
    # Prevent directory traversal attacks
    if ".." in path.parts:
        raise ValueError(f"Invalid path: {path_str} contains parent directory references")
    
    return str(path)

# --------------------------------------------------------------------------------
# 5. Conversation state
# --------------------------------------------------------------------------------
conversation_history = [
    {"role": "system", "content": system_PROMPT}
]

# --------------------------------------------------------------------------------
# 6. OpenAI API interaction with streaming
# --------------------------------------------------------------------------------

def guess_files_in_message(user_message: str) -> List[str]:
    recognized_extensions = [".css", ".html", ".js", ".py", ".json", ".md", ".txt", ".yml", ".yaml", ".ts", ".tsx"]
    potential_paths = []
    for word in user_message.split():
        if any(ext in word for ext in recognized_extensions) or "/" in word:
            path = word.strip("',\"")
            try:
                normalized_path = normalize_path(path)
                potential_paths.append(normalized_path)
            except (OSError, ValueError):
                continue
    return potential_paths

def validate_edits(response_data: AssistantResponse, conversation_history: List[Dict]) -> Optional[AssistantResponse]:
    """Check if all edits can be applied safely (original_snippet exists exactly once)."""
    issues = []
    if response_data.files_to_edit:
        for edit in response_data.files_to_edit:
            content = get_file_content_from_history(edit.path, conversation_history)
            if content is None:
                issues.append(f"File '{edit.path}' not found in context.")
                continue
            count = content.count(edit.original_snippet)
            if count == 0:
                issues.append(f"Original snippet not found in '{edit.path}'.")
            elif count > 1:
                issues.append(f"Multiple occurrences ({count}) of snippet in '{edit.path}'.")
    
    if issues:
        analysis = "Invalid edits detected:\n- " + "\n- ".join(issues)
        explanation = "Edits cannot be applied due to missing or ambiguous snippets."
        return AssistantResponse(
            analysis=analysis,
            explanation=explanation,
            output="NEED_CHANGES"
        )
    return None

def generate_review(response_data: AssistantResponse) -> AssistantResponse:
    """Generate code review by analyzing the proposed changes without modifying conversation history.
    
    Args:
        response_data: AssistantResponse object containing proposed changes
        
    Returns:
        AssistantResponse object containing review results
    """
    console.print("\n[bold yellow]Starting Review Phase[/bold yellow]")
    
    # Perform automated validation of edits
    validation_result = validate_edits(response_data, conversation_history)
    if validation_result:
        console.print("[yellow]Automated validation failed, returning NEED_CHANGES[/yellow]")
        return validation_result
    
    try:
        # Build review context
        review_context = []
        file_contexts = []
        
        # Process file contents from conversation history
        for msg in conversation_history:
            if msg["role"] == "system" and "Content of file '" in msg["content"]:
                file_contexts.append(msg["content"])
                
        # Process implementation plan if it exists
        plan_context = []
        for msg in conversation_history:
            if msg["role"] == "system" and '"Plan Summary"' in msg["content"]:
                try:
                    plan_data = json.loads(msg["content"])
                    plan_context.append(f"Implementation Plan:\n{plan_data.get('Plan Summary', 'No plan found')}")
                except json.JSONDecodeError:
                    continue
        
        # Handle new files
        if response_data.files_to_create:
            for file in response_data.files_to_create:
                review_context.append({
                    "change_type": "new_file",
                    "path": file.path,
                    "content": file.content
                })
        
        # Handle file edits
        if response_data.files_to_edit:
            for edit in response_data.files_to_edit:
                review_context.append({
                    "change_type": "file_edit",
                    "path": edit.path,
                    "original": edit.original_snippet,
                    "new": edit.new_snippet
                })
        
        # Build complete review request with all context embedded
        review_request = {
            "role": "user",
            "content": dedent(f"""
                You are an elite software engineer performing a code review. Here is the complete context and changes to review:

                {review_system_PROMPT}

                EXISTING FILE CONTEXT:
                {''.join(file_contexts)}

                {('IMPLEMENTATION PLAN:\n' + '\n'.join(plan_context)) if plan_context else ''}

                COMPLETE CHANGES SUMMARY:
                {json.dumps({
                    "total_new_files": len(response_data.files_to_create) if response_data.files_to_create else 0,
                    "total_edits": len(response_data.files_to_edit) if response_data.files_to_edit else 0,
                    "changes": review_context
                }, indent=2)}

                Please perform a thorough code review of the proposed changes:
                1. Verify the changes solve the intended problem completely
                2. Check for potential bugs, edge cases, and security issues
                3. Evaluate code quality, readability, and maintainability
                4. Confirm all changes are necessary and focused
                5. Validate error handling and input validation
                
                Provide a detailed analysis and clear recommendation following the specified JSON format.
            """).strip()
        }
        
        # Generate review using streaming
        console.print("[cyan]Analyzing code changes...[/cyan]")
        review_messages = [
            {"role": "system", "content": review_system_PROMPT},
            review_request
        ]
        
        # Create a new chat completion for review
        stream = client.chat.completions.create(
            model="deepseek-reasoner",
            messages=review_messages,
            stream=True
        )
        
        console.print("\nGenerating review...", style="bold yellow")
        review_content = ""
        
        for chunk in stream:
            if chunk.choices[0].delta.content:
                content_part = chunk.choices[0].delta.content
                review_content += content_part
                console.print(content_part, end="")
        
        console.print()
        
        # Parse and validate review response
        try:
            parsed = json.loads(review_content)
            review_result = AssistantResponse(
                analysis=parsed.get('analysis'),
                explanation=parsed.get('explanation'),
                output=parsed.get('output')
            )
            
            # Validate review output
            if not review_result.output or review_result.output not in ["CORRECT", "INCORRECT", "UNECESSARY", "NEED_CHANGES"]:
                raise ValueError(f"Invalid review status: {review_result.output}")
            
            console.print(f"[green]✓[/green] Review completed: {review_result.output}")
            return review_result
            
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse review response: {str(e)}"
            console.print(f"[red]✗[/red] {error_msg}")
            console.print(f"Problematic content: {review_content}")
            return AssistantResponse(
                analysis="Failed to parse review response",
                explanation=str(e),
                output="INCORRECT"
            )
            
    except Exception as e:
        error_msg = f"Review generation failed: {str(e)}"
        console.print(f"[red]✗[/red] {error_msg}")
        return AssistantResponse(
            analysis="Review process failed",
            explanation=error_msg,
            output="INCORRECT"
        )

def generate_plan(user_message: str) -> AssistantResponse:
    """Generate implementation plan through streaming API call"""
    console.print("\n[bold yellow]Starting Planning Phase[/bold yellow]")
    
    # Save original conversation state
    original_history = conversation_history.copy()
    original_system = original_history[0] if original_history else None
    
    try:
        # Create temporary planning context
        planning_history = [
            {"role": "system", "content": planning_system_PROMPT},
            *[msg for msg in original_history if msg["role"] == "system" and "Content of file '" in msg["content"]],
        ]
        
        # Replace global conversation history with planning version
        conversation_history.clear()
        conversation_history.extend(planning_history)
        
        # Generate response using streaming
        console.print("[cyan]Streaming planning thoughts...[/cyan]")
        response = stream_openai_response(user_message)
        
        # Log plan generation
        console.print(f"\n[green]✓[/green] Planning phase completed")
        if response.assistant_reply:
            console.print(Panel.fit(
                response.assistant_reply,
                title="Implementation Plan",
                border_style="blue"
            ))
        
        return response
    except Exception as e:
        console.print(f"[red]✗[/red] Planning Error: {str(e)}", style="red")
        return AssistantResponse(assistant_reply=f"⚠ Planning Error: {str(e)}")
    finally:
        # Restore original conversation history
        conversation_history.clear()
        conversation_history.extend(original_history)
        if original_system:
            conversation_history[0] = original_system


def stream_openai_response(user_message: str) -> AssistantResponse:
    """
    Generate streaming response from OpenAI with improved file handling.
    
    Args:
        user_message: The user's input message
        
    Returns:
        AssistantResponse object containing the response data
    """
    # Clean up conversation history while preserving important context
    system_msgs = [conversation_history[0]]  # Keep initial system prompt
    file_context = []
    user_assistant_pairs = []
    
    for msg in conversation_history[1:]:
        if msg["role"] == "system" and "Content of file '" in msg["content"]:
            file_context.append(msg)
        elif msg["role"] in ["user", "assistant"]:
            user_assistant_pairs.append(msg)
    
    # Keep complete user-assistant pairs
    if len(user_assistant_pairs) % 2 != 0:
        user_assistant_pairs = user_assistant_pairs[:-1]

    # Rebuild clean history with preserved files
    cleaned_history = system_msgs + file_context
    cleaned_history.extend(user_assistant_pairs)
    cleaned_history.append({"role": "user", "content": user_message})
    
    # Replace conversation_history with cleaned version
    conversation_history.clear()
    conversation_history.extend(cleaned_history)

    # Handle file references in message
    potential_paths = guess_files_in_message(user_message)
    for path in potential_paths:
        ensure_file_in_context(path)

    try:
        stream = client.chat.completions.create(
            model="deepseek-reasoner",
            messages=conversation_history,
            stream=True
        )

        console.print("\nThinking...", style="bold yellow")
        reasoning_started = False
        reasoning_content = ""
        final_content = ""

        for chunk in stream:
            if chunk.choices[0].delta.reasoning_content:
                if not reasoning_started:
                    console.print("\nReasoning:", style="bold yellow")
                    reasoning_started = True
                reasoning_part = chunk.choices[0].delta.reasoning_content
                console.print(reasoning_part, end="")
                reasoning_content += reasoning_part
            elif chunk.choices[0].delta.content:
                if reasoning_started:
                    console.print("\n")
                    console.print("\nAssistant> ", style="bold blue", end="")
                    reasoning_started = False
                content_part = chunk.choices[0].delta.content
                final_content += content_part
                console.print(content_part, end="")

        console.print()

        # Ensure we have actual content before parsing
        if not final_content.strip():
            return AssistantResponse(
                assistant_reply="No response generated",
                files_to_create=[],
                files_to_edit=[]
            )

        try:
            # Clean up the final content to ensure it's valid JSON
            final_content = final_content.strip()
            if not final_content.startswith('{'):
                final_content = '{' + final_content
            if not final_content.endswith('}'):
                final_content = final_content + '}'
                
            parsed_response = json.loads(final_content)
            
            # Handle review response
            if "analysis" in parsed_response and "output" in parsed_response:
                return AssistantResponse(
                    analysis=parsed_response.get("analysis"),
                    explanation=parsed_response.get("explanation"),
                    output=parsed_response.get("output")
                )
            
            # Handle normal response
            return AssistantResponse(
                assistant_reply=parsed_response.get("assistant_reply", ""),
                files_to_create=[FileToCreate(**file) for file in parsed_response.get("files_to_create", [])],
                files_to_edit=[FileToEdit(**file) for file in parsed_response.get("files_to_edit", [])]
            )
            
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse JSON response from assistant: {str(e)}"
            console.print(f"[red]✗[/red] {error_msg}", style="red")
            console.print(f"Problematic content: {final_content}")
            return AssistantResponse(
                assistant_reply=error_msg,
                files_to_create=[],
                files_to_edit=[]
            )

    except Exception as e:
        error_msg = f"DeepSeek API error: {str(e)}"
        console.print(f"\n[red]✗[/red] {error_msg}", style="red")
        return AssistantResponse(
            assistant_reply=error_msg,
            files_to_create=[]
        )
    

def trim_conversation_history():
    """Trim conversation history to prevent token limit issues"""
    max_pairs = 10  # Adjust based on your needs
    system_msgs = [msg for msg in conversation_history if msg["role"] == "system"]
    other_msgs = [msg for msg in conversation_history if msg["role"] != "system"]
    
    # Keep only the last max_pairs of user-assistant interactions
    if len(other_msgs) > max_pairs * 2:
        other_msgs = other_msgs[-max_pairs * 2:]
    
    conversation_history.clear()
    conversation_history.extend(system_msgs + other_msgs)

# --------------------------------------------------------------------------------
# 7. Main interactive loop
# --------------------------------------------------------------------------------

def main():
    console.print(Panel.fit(
        "[bold red] Initializing Infrared",
        border_style="red",
    ))
    console.print(
        "Use '[bold magenta]/add[/bold magenta]' to include files in the conversation:\n"
        "  • '[bold magenta]/add path/to/file[/bold magenta]' for a single file\n"
        "  • '[bold magenta]/add path/to/folder[/bold magenta]' for all files in a folder\n"
        "  • You can add multiple files one by one using /add for each file\n"
        "Type '[bold red]exit[/bold red]' or '[bold red]quit[/bold red]' to end.\n"
    )

    # Load technical stack documentation
    tech_stack_path = "tech_stack.md"
    try:
        content = read_local_file(tech_stack_path)
        conversation_history.append({
            "role": "system",
            "content": f"Content of file 'tech_stack.md':\n\n{content}"
        })
        console.print(f"[green]✓[/green] Loaded technical stack documentation from '[cyan]{tech_stack_path}[/cyan]'")
    except FileNotFoundError:
        console.print(f"[red]✗[/red] Critical error: [cyan]{tech_stack_path}[/cyan] not found. Technical guidelines unavailable.")
    except Exception as e:
        console.print(f"[red]✗[/red] Error loading technical stack: {str(e)}")

    while True:
        try:
            user_input = prompt_session.prompt("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Exiting.[/yellow]")
            break

        if not user_input:
            continue

        if user_input.lower() in ["exit", "quit"]:
            console.print("[yellow]Goodbye![/yellow]")
            break

        if try_handle_add_command(user_input):
            continue

        plan_turned_on = False
        if plan_turned_on:
            # Generate implementation plan
            console.print("\n[bold yellow]Phase 1: Generating Implementation Plan[/bold yellow]")
            plan_response = generate_plan(user_input)
            
            # Store plan in conversation history
            if plan_response.assistant_reply:
                conversation_history.append({
                    "role": "system",
                    "content": json.dumps({
                        "Message": 'The following is a plan for the implementation of the solution. You are free to use it as a guide if it is helpful.',
                        "Plan Summary": plan_response.assistant_reply,
                        "files_to_create": [],
                        "files_to_edit": []
                    })
                })
        else:
            console.print("\n[bold yellow]Phase 1: Planning Skipped [/bold yellow]")

        # Generate code implementation
        console.print("\n[bold yellow]Phase 2: Generating Code Implementation[/bold yellow]")
        response_data = stream_openai_response(user_input)

        if response_data:
            # Display files to create
            if response_data.files_to_create:
                console.print("\n[bold cyan]Proposed New Files:[/bold cyan]")
                for file in response_data.files_to_create:
                    console.print(Panel.fit(
                        file.content,
                        title=f"[bold green]New File: {file.path}[/bold green]",
                        border_style="green"
                    ))

            # Display files to edit
            if response_data.files_to_edit:
                console.print("\n[bold cyan]Proposed File Changes:[/bold cyan]")
                for edit in response_data.files_to_edit:
                    console.print(Panel.fit(
                        f"[red]Original:[/red]\n{edit.original_snippet}\n\n[green]New:[/green]\n{edit.new_snippet}",
                        title=f"[bold yellow]Edit in: {edit.path}[/bold yellow]",
                        border_style="yellow"
                    ))

            # If no changes proposed
            if not response_data.files_to_create and not response_data.files_to_edit:
                console.print("\n[yellow]No file changes proposed in this implementation.[/yellow]")

        # Phase 3: Automated Code Review
        console.print("\n[bold yellow]Phase 3: Code Review Analysis[/bold yellow]")
        review_response = generate_review(response_data)

        # Iterative review handling
        max_attempts = 3
        attempt = 1
        while attempt < max_attempts and review_response.output == "NEED_CHANGES":
            # Add review feedback to context
            feedback_content = f"Code Review Feedback (Attempt {attempt}):\nAnalysis: {review_response.analysis}\nExplanation: {review_response.explanation}"
            conversation_history.append({
                "role": "system",
                "content": feedback_content
            })

            # Regenerate code
            console.print(f"\n[bold yellow]Attempt {attempt + 1}: Regenerating Code[/bold yellow]")
            response_data = stream_openai_response(user_input)

            # Review new changes
            review_response = generate_review(response_data)
            attempt += 1

        # Final outcome handling
        if review_response.output == "CORRECT":
            if response_data.files_to_create:
                for file_info in response_data.files_to_create:
                    create_file(file_info.path, file_info.content)
            if response_data.files_to_edit:
                for edit_info in response_data.files_to_edit:
                    apply_diff_edit(edit_info.path, edit_info.original_snippet, edit_info.new_snippet)
            console.print(f"[green]✓[/green] Changes applied after {attempt} attempts")
        else:
            console.print(f"[red]✗[/red] Final rejection after {attempt} attempts (Status: {review_response.output or 'NO_STATUS'})")
            if review_response.analysis or review_response.explanation:
                console.print(Panel.fit(
                    f"FINAL ANALYSIS: {review_response.analysis or 'No analysis provided'}\n\nEXPLANATION: {review_response.explanation or 'No explanation provided'}",
                    title="Review Details",
                    border_style="red"
                ))

    console.print("[blue]Session finished.[/blue]")

if __name__ == "__main__":
    main()