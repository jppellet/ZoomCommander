from datetime import datetime
from dataclasses import dataclass

def is_assistant(name: str) -> bool:
    name_lower = name.lower()
    return "[assistant" in name_lower or "[enseignant" in name_lower


@dataclass
class Assignment:
    time: datetime
    assistant: str
