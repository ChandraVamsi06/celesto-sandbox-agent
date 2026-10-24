"""
Celesto Safety Hooks & Callback Interceptors
Inspects and filters agent commands before they reach the guest microVM kernel.
Provides deterministic protection against prompt injection, destructive commands,
and credential exfiltration attacks.
"""

import re
from typing import Tuple, Optional


class CommandBlockedError(Exception):
    """Raised when a command violates security policy and is blocked before execution."""
    def __init__(self, command: str, reason: str):
        self.command = command
        self.reason = reason
        super().__init__(f"Command blocked by safety hook: '{command}'. Reason: {reason}")


class SafetyHook:
    """Pre-execution command inspector for Celesto sandboxes."""

    BLOCKED_PATTERNS = [
        # Exfiltration via curl / wget / netcat / python socket
        (re.compile(r"curl\s+.*(?:evil|attacker|exfil|leak|webhook|httpbin).*", re.IGNORECASE), "Credential or data exfiltration attempt"),
        (re.compile(r"curl\s+.*-(?:d|F|X\s*POST).*[\$]?API_KEY", re.IGNORECASE), "API key exfiltration via HTTP POST"),
        (re.compile(r"wget\s+.*--post-(?:data|file)", re.IGNORECASE), "Data exfiltration via wget POST"),
        (re.compile(r"nc\s+-[e|c]", re.IGNORECASE), "Netcat reverse shell execution"),
        # Host escape / destructive commands
        (re.compile(r"rm\s+-rf\s+(?:/|/\*|~|~/\*|\$HOME|\.\./)", re.IGNORECASE), "Destructive file system wipe command"),
        (re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", re.IGNORECASE), "Fork bomb denial of service attack"),
        (re.compile(r"mkfs(?:\.ext[234]|\.vfat)?\s+/dev/[s|v]da", re.IGNORECASE), "Direct block device formatting"),
        # Sensitive host file exfiltration
        (re.compile(r"(?:cat|head|tail|less|more)\s+(?:/etc/shadow|/proc/kcore)", re.IGNORECASE), "Unauthorized privileged credential access"),
    ]

    @classmethod
    def inspect(cls, command: str) -> Tuple[bool, Optional[str]]:
        """
        Inspect command string before execution.
        Returns: (is_allowed: bool, reason: Optional[str])
        """
        cmd_clean = command.strip()
        for pattern, reason in cls.BLOCKED_PATTERNS:
            if pattern.search(cmd_clean):
                return False, reason
        return True, None
