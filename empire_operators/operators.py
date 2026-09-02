"""General (non-talora) empire_os reasoning operators, fleet-installable.

Each is a pure `execute(state: dict) -> dict` transform — no I/O, no deps.
Bodies are copied verbatim from
`empire_os/operators/all_operators.py`; keep them in sync.

This first slice carries the operators Step 8 Phase B wires: input
safety, output constraint/validation, error-recovery policy, and
metric drift detection. The remaining ~40 general operators land here
incrementally.
"""
import json
import re
from typing import Any, Dict

from .operator_base import BaseOperator


class SafetyBoundaryOperator(BaseOperator):
    name = "SafetyBoundaryOperator"
    operator_type = "reactive"
    engine = "governance"

    UNSAFE_PATTERNS = [
        "ignore previous instructions",
        "ignore all previous",
        "disregard the system prompt",
        "<script",
        "drop table",
    ]

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        text = (state.get("parsed_input", {}).get("text") or state.get("raw_input", "") or "").lower()
        detected = [p for p in self.UNSAFE_PATTERNS if p in text]
        explicit_flag = bool(state.get("unsafe_pattern", False))

        state["unsafe_patterns_detected"] = detected
        state.setdefault("flags", {})
        state["flags"]["safety_ok"] = not (detected or explicit_flag)
        return state


class ConstraintEnforcer(BaseOperator):
    name = "ConstraintEnforcer"
    operator_type = "reactive"
    engine = "governance"

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        constraints = state.get("constraints", {}) or {}
        text = self._output_text(state)
        violations = []

        max_length = constraints.get("max_length")
        if max_length is not None and len(text) > max_length:
            violations.append(f"output exceeds max_length ({len(text)} > {max_length})")

        for word in constraints.get("forbidden_words", []):
            if word and word.lower() in text.lower():
                violations.append(f"forbidden word present: {word}")

        state["constraint_violations"] = violations
        state.setdefault("flags", {})
        state["flags"]["constraints_enforced"] = len(violations) == 0
        return state

    @staticmethod
    def _output_text(state: Dict[str, Any]) -> str:
        output = state.get("output")
        if isinstance(output, str):
            return output
        if output is not None:
            return json.dumps(output, default=str)
        return state.get("parsed_input", {}).get("text", "") or state.get("raw_input", "") or ""


class ValidationOperator(BaseOperator):
    name = "ValidationOperator"
    operator_type = "conditional"
    engine = "execution"

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        schema = state.get("validation_schema")
        output = state.get("output")

        if schema and isinstance(output, dict):
            required_fields = schema.get("required_fields", [])
            missing = [f for f in required_fields if f not in output]
        else:
            missing = []

        state["validation_errors"] = missing
        state.setdefault("flags", {})
        state["flags"]["validated"] = len(missing) == 0
        return state


class ErrorRecoveryOperator(BaseOperator):
    name = "ErrorRecoveryOperator"
    operator_type = "reactive"
    engine = "execution"

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        error = state.get("error")
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 3)

        state.setdefault("flags", {})
        if not error:
            state["flags"]["recovered"] = True
            state["recovery_action"] = "none_needed"
            return state

        error_text = str(error).lower()
        if "timeout" in error_text:
            error_type = "timeout"
        elif "valid" in error_text:
            error_type = "validation"
        else:
            error_type = "unknown"

        if retry_count < max_retries:
            recovery_action = "retry"
            recovered = True
        else:
            recovery_action = "abort"
            recovered = False

        state["error_type"] = error_type
        state["recovery_action"] = recovery_action
        state["flags"]["recovered"] = recovered
        return state


class DriftMonitor(BaseOperator):
    name = "DriftMonitor"
    operator_type = "proactive"
    engine = "governance"

    DRIFT_THRESHOLD_PCT = 20.0

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # Compare current metrics against a baseline to detect real deviation
        baseline = state.get("baseline_metrics", {}) or {}
        current = state.get("current_metrics", {}) or {}

        deviations = {}
        for key, baseline_value in baseline.items():
            if key not in current or not baseline_value:
                continue
            pct_change = abs(current[key] - baseline_value) / abs(baseline_value) * 100
            if pct_change >= self.DRIFT_THRESHOLD_PCT:
                deviations[key] = round(pct_change, 1)

        state["drift_deviations"] = deviations
        state.setdefault("flags", {})
        state["flags"]["drift_detected"] = len(deviations) > 0
        return state


__all__ = [
    "BaseOperator",
    "SafetyBoundaryOperator",
    "ConstraintEnforcer",
    "ValidationOperator",
    "ErrorRecoveryOperator",
    "DriftMonitor",
]
