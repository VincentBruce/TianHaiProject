from tianhai.runtime.boundaries import BoundaryName, get_boundary

BOUNDARY = get_boundary(BoundaryName.WORKFLOWS)

__all__ = ("BOUNDARY",)
