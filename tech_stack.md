# Technical Stack Documentation

## Core Principles
- Python 3.10+ required
- Pydantic v2 for data validation
- Strict type annotations
- Rich library for CLI formatting
- Modular architecture with clear separation:
  - API interactions
  - File operations
  - User interface

## Security Requirements
- All file operations require path normalization
- 5MB size limit for generated files
- Prohibit home directory references
- Validate JSON responses before processing

## Testing Standards
- 90%+ test coverage required
- Pytest for unit tests
- Golden master testing for CLI output
- Security penetration testing for file operations

## Performance Guidelines
- <2s response time for most operations
- Stream API responses
- Cache frequently accessed files
- Limit conversation history to 10k tokens

## Version Control
- Semantic versioning (SemVer)
- Conventional commits
- Protected main branch
- PR reviews required

## Documentation
- Keep docstrings Google-style
- Generate API docs with pdoc
- Update tech_stack.md for major changes