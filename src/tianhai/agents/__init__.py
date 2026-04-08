from tianhai.runtime.boundaries import BoundaryName, get_boundary

BOUNDARY = get_boundary(BoundaryName.AGENTS)

__all__ = ("BOUNDARY",)
