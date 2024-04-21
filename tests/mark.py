import pytest


def xfail_if_not_implemented_yet(request: pytest.FixtureRequest, backend: str) -> None:
    found_marker = request.node.get_closest_marker("not_implemented")
    if found_marker is None:
        return

    not_implemented = found_marker.kwargs.get("backend", [])
    if isinstance(not_implemented, str):
        not_implemented = [not_implemented]

    if backend in not_implemented:
        marker = pytest.mark.xfail(
            raises=NotImplementedError,
            reason=f"{backend} not implemented yet",
            strict=True,
        )
        request.node.add_marker(marker)


def skip_backend(request: pytest.FixtureRequest, backend: str) -> None:
    found_marker = request.node.get_closest_marker("skip_backend")
    if found_marker is None:
        return

    reason = found_marker.kwargs.get("reason", "")
    backends = found_marker.kwargs.get("backend", [])
    if isinstance(backends, str):
        backends = [backends]

    if backend in backends:
        pytest.skip(f"Skipping {backend} tests: {reason}")
