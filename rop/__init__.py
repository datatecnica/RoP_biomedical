"""RoP — Biomedical Reference of Parameters.

A portable interoperability contract for biomedical research data,
with governance operationalized through The Forge.
"""

__version__ = "0.1.0"

from rop.schema import RoPElement, SourceAuthority, CurationStatus
from rop.anchors import load_anchors, AnchorRegistry
from rop.validate import (
    validate_element,
    validate_collection,
    parse_priority_rule,
    ValidationResult,
    ValidationError,
)

__all__ = [
    "__version__",
    "RoPElement",
    "SourceAuthority",
    "CurationStatus",
    "load_anchors",
    "AnchorRegistry",
    "validate_element",
    "validate_collection",
    "parse_priority_rule",
    "ValidationResult",
    "ValidationError",
]
