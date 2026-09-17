"""Tool Request Validator for JARVIS.

Ensures parameter types match, required arguments exist, and prevents path traversal.
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from jarvis.tools.base import BaseTool


FORBIDDEN_WINDOWS_PATHS = [
    r"c:\windows\system32\config",
    r"c:\windows\system32\drivers",
    r"c:\windows\system",
    r"c:\pagefile.sys",
    r"c:\hiberfil.sys",
]


@dataclass
class ValidationResult:
    """Result of tool request validation."""
    valid: bool
    error: Optional[str] = None
    sanitized_arguments: Dict[str, Any] = None


class ToolValidator:
    """Validates raw tool invocation requests against tool schemas and security constraints."""

    @staticmethod
    def validate(tool: BaseTool, arguments: Dict[str, Any]) -> ValidationResult:
        """Validate input arguments against tool parameter specifications."""
        sanitized = dict(arguments) if arguments else {}

        # 1. Check for missing required parameters
        for param_name, param in tool.parameters.items():
            if param.required and param_name not in sanitized:
                return ValidationResult(
                    valid=False,
                    error=f"Missing required parameter '{param_name}' for tool '{tool.name}'",
                )
            if param_name not in sanitized and param.default is not None:
                sanitized[param_name] = param.default

        # 2. Type checking
        for param_name, val in sanitized.items():
            if param_name not in tool.parameters:
                continue
            expected_type = tool.parameters[param_name].type

            if expected_type == "string" and not isinstance(val, str):
                sanitized[param_name] = str(val)
            elif expected_type == "integer" and not isinstance(val, int):
                try:
                    sanitized[param_name] = int(val)
                except (ValueError, TypeError):
                    return ValidationResult(
                        valid=False,
                        error=f"Parameter '{param_name}' must be an integer, got {type(val).__name__}",
                    )
            elif expected_type == "boolean" and not isinstance(val, bool):
                if str(val).lower() in ("true", "1", "yes"):
                    sanitized[param_name] = True
                elif str(val).lower() in ("false", "0", "no"):
                    sanitized[param_name] = False
                else:
                    return ValidationResult(
                        valid=False,
                        error=f"Parameter '{param_name}' must be a boolean",
                    )

        # 3. Path safety check for file/path parameters
        for param_name in ("path", "source_path", "destination_path", "target_path", "filepath"):
            if param_name in sanitized and isinstance(sanitized[param_name], str):
                path_val = sanitized[param_name]
                norm_path = os.path.normpath(os.path.abspath(path_val)).lower()
                for forbidden in FORBIDDEN_WINDOWS_PATHS:
                    if norm_path.startswith(forbidden):
                        return ValidationResult(
                            valid=False,
                            error=f"Security violation: Access to critical system path '{path_val}' is blocked.",
                        )

        return ValidationResult(valid=True, sanitized_arguments=sanitized)
