"""Interrupt signal management for FeinnAgent.

Provides a global threading.Event that any tool can check to determine
if the user has requested an interrupt. The agent's interrupt() method
sets this event, and tools poll it during long-running operations.
"""

import threading
from typing import Optional

_interrupt_event = threading.Event()
_interrupt_reason: Optional[str] = None
_interrupt_timestamp: Optional[float] = None


def set_interrupt(reason: str = "") -> None:
    """Set the interrupt signal.
    
    Called by the agent or CLI to signal an interrupt request.
    
    Args:
        reason: Optional reason for the interrupt
    """
    global _interrupt_reason, _interrupt_timestamp
    _interrupt_reason = reason
    import time
    _interrupt_timestamp = time.time()
    _interrupt_event.set()


def clear_interrupt() -> None:
    """Clear the interrupt signal.
    
    Called when resuming from an interrupt or canceling it.
    """
    global _interrupt_reason, _interrupt_timestamp
    _interrupt_reason = None
    _interrupt_timestamp = None
    _interrupt_event.clear()


def is_interrupted() -> bool:
    """Check if an interrupt has been requested.
    
    Safe to call from any thread. Tools should poll this
    during long-running operations to allow graceful shutdown.
    
    Returns:
        True if interrupt is set, False otherwise
    """
    return _interrupt_event.is_set()


def get_interrupt_reason() -> Optional[str]:
    """Get the reason for the interrupt.
    
    Returns:
        The interrupt reason string, or None if not interrupted
    """
    return _interrupt_reason


def get_interrupt_timestamp() -> Optional[float]:
    """Get the timestamp when interrupt was set.
    
    Returns:
        Unix timestamp when interrupt was set, or None
    """
    return _interrupt_timestamp


def get_interrupt_info() -> dict:
    """Get full interrupt information.
    
    Returns:
        Dict with 'is_interrupted', 'reason', and 'timestamp' keys
    """
    return {
        "is_interrupted": is_interrupted(),
        "reason": _interrupt_reason,
        "timestamp": _interrupt_timestamp,
    }


class InterruptContext:
    """Context manager for temporary interrupt handling.
    
    Usage:
        with InterruptContext():
            # Code that respects interrupt signals
            pass
    """
    
    def __init__(self):
        self._previous_state = False
        self._previous_reason: Optional[str] = None
    
    def __enter__(self):
        self._previous_state = is_interrupted()
        self._previous_reason = get_interrupt_reason()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if not is_interrupted():
            return
        clear_interrupt()
