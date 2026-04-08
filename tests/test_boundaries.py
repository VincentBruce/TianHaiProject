import importlib

from tianhai.runtime import AGNO_FIRST_BOUNDARIES, BoundaryName


def test_phase1_defines_expected_agno_boundaries() -> None:
    names = {boundary.name for boundary in AGNO_FIRST_BOUNDARIES}

    assert names == {
        BoundaryName.AGENTS,
        BoundaryName.TEAMS,
        BoundaryName.WORKFLOWS,
        BoundaryName.MEMORY,
        BoundaryName.KNOWLEDGE,
        BoundaryName.TOOLS,
    }


def test_boundary_packages_export_their_boundary_contracts() -> None:
    for boundary in AGNO_FIRST_BOUNDARIES:
        module = importlib.import_module(boundary.module)

        assert module.BOUNDARY == boundary
        assert "no " in boundary.phase1_scope.lower()
