from tianhai.runtime.boundaries import BoundaryName, get_boundary

BOUNDARY = get_boundary(BoundaryName.TEAMS)

__all__ = ("BOUNDARY",)
