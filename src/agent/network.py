"""
Celesto MicroVM Network Policy Enforcement
Controls egress and ingress networking for isolated agent sandboxes.
Default mode disables external internet to prevent prompt-injection exfiltration.
"""

from typing import Dict, Any, List, Optional


class NetworkPolicy:
    def __init__(self, mode: str = "off", allowed_ips: Optional[List[str]] = None):
        """
        :param mode: 'off' (no external internet), 'allowlist' (specific hosts only), 'open'
        :param allowed_ips: List of CIDRs or hostnames permitted when mode='allowlist'
        """
        if mode not in {"off", "allowlist", "open"}:
            raise ValueError(f"Invalid network policy mode: {mode}")
        self.mode = mode
        self.allowed_ips = allowed_ips or []

    def to_celesto_settings(self) -> Dict[str, Any]:
        """Convert policy to Celesto microVM internet settings dict."""
        if self.mode == "off":
            return {"mode": "off"}
        elif self.mode == "allowlist":
            return {
                "mode": "allowlist",
                "allowed_ips": self.allowed_ips,
            }
        return {"mode": "open"}

    def is_egress_allowed(self, target_host: str) -> bool:
        if self.mode == "off":
            return False
        if self.mode == "open":
            return True
        return target_host in self.allowed_ips
