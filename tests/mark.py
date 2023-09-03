import pytest


def xfail_if_not_implemented_yet(request: pytest.FixtureRequest, storage: str) -> None:
    found_marker = request.node.get_closest_marker("not_implemented")
    if found_marker is None:
        return

    not_implemented = found_marker.kwargs.get("storage", [])
    if isinstance(not_implemented, str):
        not_implemented = [not_implemented]

    if storage in not_implemented:
        marker = pytest.mark.xfail(
            reason=f"{storage} not implemented yet",
            strict=True,
        )
        request.node.add_marker(marker)
