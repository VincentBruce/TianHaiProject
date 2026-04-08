from tianhai.runtime.boundaries import BoundaryName, get_boundary

BOUNDARY = get_boundary(BoundaryName.MEMORY)

__all__ = ("BOUNDARY",)
