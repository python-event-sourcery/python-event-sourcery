# OpenTelemetry context propagation

Install the optional integration:

```bash
pip install "python-event-sourcery[otel]"
```

Configure its enricher before accessing the event store. It persists the active
OpenTelemetry propagation context; it does not create or end spans.

```python
--8<--
docs/code/test_otel.py:otel_01
--8<--
```

When consuming a recorded event, explicitly activate its propagated parent
context before starting application work or a consumer span:

```python
--8<--
docs/code/test_otel.py:otel_02
--8<--
```
