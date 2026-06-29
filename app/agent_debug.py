import json

from agent_core import AgentAction
from typing import Any

def debug_action(action: AgentAction) -> None:
    """
    Print useful debug info in the terminal.
    """
    print(
        "[Decision]",
        json.dumps(
            {
                "tool": action.tool,
                "arguments": action.arguments,
                "reason": action.reason,
            },
            indent=2,
        ),
    )

def debug_result(result: Any) -> None:
    """
    Print tool result debug info in the terminal.
    """
    print(
        "[Tool result]",
        json.dumps(result, indent=2, default=str),
    )
