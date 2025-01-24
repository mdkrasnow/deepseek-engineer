from dataclasses import dataclass
from typing import Literal

@dataclass
class EditValidationError:
    error_type: Literal['NOT_FOUND', 'AMBIGUOUS']
    file_path: str
    snippet_hash: str
    occurrences: int
    original_snippet: str
    new_snippet: str

@dataclass
class FileOperationResult:
    success: bool
    errors: list[EditValidationError]
    warnings: list[str]