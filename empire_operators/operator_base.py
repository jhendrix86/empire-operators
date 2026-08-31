from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseOperator(ABC):
    """A reasoning primitive: receives and returns a mutable state dict.

    Copied verbatim from empire_os/operators/operator_base.py — the two are
    kept in sync by convention (this package is the fleet-installable
    extract of empire_os's ~48 general, non-talora operators).
    """

    name: str = "BaseOperator"
    operator_type: str = "generic"
    engine: str = "none"

    def __init__(self) -> None:
        pass

    @abstractmethod
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError
