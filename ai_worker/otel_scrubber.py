"""OpenTelemetry ``SpanProcessor`` that redacts PII in LLM span attributes.

Why a SpanProcessor and not a wrapping exporter:
- Langfuse v4 registers its own ``BatchSpanProcessor`` during ``get_client()``,
  and we don't have a clean handle to wrap the underlying exporter.
- A ``SpanProcessor.on_end`` hook runs synchronously for every ended span
  before the BatchSpanProcessor's background thread actually serializes
  it for export. Mutating the span's attributes in ``on_end`` is therefore
  observed by the export — the same ``_Span`` object is shared across
  processors.

The mutation reaches into ``BoundedAttributes._dict`` directly because the
public ``set_attribute`` API on the SDK ``_Span`` is a no-op after the span
ends. Both are private SDK internals; if the OTel SDK changes its shape
this module is the one place to update.
"""

from __future__ import annotations

import logging
import os
from typing import Final

from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor

from ai_worker.security import PIIScrubber

logger = logging.getLogger(__name__)

# OpenInference semantic-convention attribute names that carry raw prompt /
# completion text. Anything not in this set is left untouched so we don't
# accidentally redact span names, IDs, or numeric counters.
_LLM_TEXT_ATTRS: Final[frozenset[str]] = frozenset(
    {
        "input.value",
        "output.value",
        "llm.prompt",
        "llm.completion",
        "llm.prompt_template.template",
        "llm.prompt_template.variables",
    }
)

# Prefixes for indexed message attributes:
#   llm.input_messages.0.message.content
#   llm.output_messages.0.message.content
#   llm.input_messages.0.message.contents.0.message_content.text
_LLM_TEXT_ATTR_PREFIXES: Final[tuple[str, ...]] = (
    "llm.input_messages.",
    "llm.output_messages.",
    "input.messages.",
    "output.messages.",
)


def _is_pii_attr(key: str) -> bool:
    if key in _LLM_TEXT_ATTRS:
        return True
    return any(key.startswith(p) for p in _LLM_TEXT_ATTR_PREFIXES)


class PIIScrubbingSpanProcessor(SpanProcessor):
    """Redacts PII from LLM span attributes before they are exported.

    Construct one instance and add it to the global ``TracerProvider``
    AFTER ``langfuse.get_client()`` has initialised its OTel pipeline.
    """

    def __init__(self, scrubber: PIIScrubber | None = None) -> None:
        self._scrubber = scrubber or PIIScrubber()
        self._redaction_count = 0

    # SpanProcessor contract -------------------------------------------------

    def on_start(self, span, parent_context=None) -> None:  # noqa: D401
        return None

    def on_end(self, span: ReadableSpan) -> None:
        attrs = getattr(span, "_attributes", None)
        if attrs is None:
            return

        # BoundedAttributes wraps an OrderedDict at ._dict; on older SDK
        # versions attrs is the dict itself. Handle both.
        inner = getattr(attrs, "_dict", attrs)

        try:
            for key, value in list(inner.items()):
                if not _is_pii_attr(key):
                    continue
                if isinstance(value, str):
                    scrubbed = self._scrubber.scrub(value)
                    if scrubbed != value:
                        inner[key] = scrubbed
                        self._redaction_count += 1
                elif isinstance(value, (list, tuple)):
                    new_seq = [
                        self._scrubber.scrub(v) if isinstance(v, str) else v
                        for v in value
                    ]
                    if new_seq != list(value):
                        inner[key] = type(value)(new_seq)
                        self._redaction_count += 1
        except Exception:
            # Never let a redaction failure block telemetry export — log
            # and move on. The alternative (losing the trace) hurts more.
            logger.exception("PII scrubber failed on span %s", span.name)

    def shutdown(self) -> None:
        logger.info(
            "PIIScrubbingSpanProcessor shutdown — redacted %d attribute(s)",
            self._redaction_count,
        )

    def force_flush(self, timeout_millis: int = 30_000) -> bool:  # noqa: ARG002
        return True


def install_pii_scrubber() -> PIIScrubbingSpanProcessor | None:
    """Register the scrubber on the global OTel TracerProvider.

    Idempotent in spirit (cheap to re-install, but normally called once
    from the worker's main()). Returns the registered processor for
    introspection, or ``None`` if ``PII_SCRUB_TELEMETRY`` is disabled or
    the provider does not support span processors (no-op default
    provider before Langfuse init).
    """
    if os.environ.get("PII_SCRUB_TELEMETRY", "true").strip().lower() != "true":
        logger.info("PII telemetry scrubbing disabled via env var")
        return None

    provider = trace.get_tracer_provider()
    add = getattr(provider, "add_span_processor", None)
    if add is None:
        logger.warning(
            "Tracer provider %s has no add_span_processor — PII scrubber NOT installed. "
            "Make sure langfuse.get_client() has been called first.",
            type(provider).__name__,
        )
        return None

    processor = PIIScrubbingSpanProcessor()
    add(processor)
    logger.info("PII scrubber installed on tracer provider %s", type(provider).__name__)
    return processor
