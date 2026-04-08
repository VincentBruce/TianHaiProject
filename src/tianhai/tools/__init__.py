from tianhai.runtime.boundaries import BoundaryName, get_boundary

BOUNDARY = get_boundary(BoundaryName.TOOLS)

__all__ = ("BOUNDARY",)
