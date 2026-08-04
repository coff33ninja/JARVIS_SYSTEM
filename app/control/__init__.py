"""Desktop control layer: virtual mouse/keyboard primitives (app/control/)."""

from .modes import Mode, ModeMachine
from .virtual_mouse import VirtualMouse

__all__ = ["Mode", "ModeMachine", "VirtualMouse"]
