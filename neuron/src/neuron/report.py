"""Build Cortex-shaped ``report`` payloads for Cerebro callbacks."""
from __future__ import annotations

from typing import Any, Self


class Report:
    """
    Mutable builder for analyzer/responder ``report`` dicts (``success``, ``summary``, ``full``,
    ``operations``, ``artifacts``).

    ``success`` defaults to ``True``; call :meth:`fail` with an error message to record a failed run
    (sets ``success`` to ``False`` and replaces ``full`` with that message).
    """

    def __init__(self) -> None:
        self._data: dict[str, Any] = {'success': True}

    def fail(self, message: str) -> Self:
        """Mark the run as failed and set ``full.message`` (Cortex-style failure text)."""
        self._data['success'] = False
        self._data['full'] = {'message': message}
        return self

    def set_details(self, details: dict[str, Any]) -> Self:
        """Replace the Cortex ``full`` object (query, details, short message, …)."""
        self._data['full'] = details
        return self

    def add_taxonomy(
        self,
        namespace: str,
        predicate: str,
        value: str,
        *,
        level: str = 'info',
    ) -> Self:
        """Append one entry to ``summary.taxonomies``."""
        summary = self._data.setdefault('summary', {})
        taxonomies = summary.setdefault('taxonomies', [])
        taxonomies.append(
            {
                'namespace': namespace,
                'predicate': predicate,
                'value': value,
                'level': level,
            }
        )
        return self

    def add_operation(self, operation: dict[str, Any]) -> Self:
        """Append one Cortex operation (e.g. ``AddTagToArtifact``)."""
        operations = self._data.setdefault('operations', [])
        operations.append(operation)
        return self

    def add_artifact(self, artifact: dict[str, Any]) -> Self:
        """Append one analyzer artifact / observable payload."""
        artifacts = self._data.setdefault('artifacts', [])
        artifacts.append(artifact)
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return the report dict for :meth:`neuron.runtime.CerebroNeuron.send_report`."""
        out = dict(self._data)
        out.setdefault('operations', [])
        return out
