from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from fastapi import FastAPI
from fastapi.routing import APIRoute, APIWebSocketRoute


TIANHAI_PRODUCT_API_PREFIX = "/tianhai"

AGENTOS_HTTP_EXACT_PATHS: tuple[str, ...] = (
    "/",
    "/health",
    "/info",
    "/config",
    "/models",
    "/openapi.json",
    "/trace_session_stats",
    "/memory_topics",
    "/user_memory_stats",
    "/optimize-memories",
)
AGENTOS_HTTP_PREFIXES: tuple[str, ...] = (
    "/docs",
    "/redoc",
    "/agents",
    "/teams",
    "/workflows",
    "/sessions",
    "/memories",
    "/eval-runs",
    "/metrics",
    "/knowledge",
    "/traces",
    "/databases",
    "/components",
    "/schedules",
    "/approvals",
    "/registry",
)
AGENTOS_STREAMING_PATHS: tuple[str, ...] = ("/workflows/ws",)


class ApiSurfaceId(StrEnum):
    PRODUCT_HTTP = "product_http"
    PRODUCT_REALTIME = "product_realtime"
    AGENTOS_HTTP = "agentos_http"
    AGENTOS_REALTIME = "agentos_realtime"


class ApiSurfaceAudience(StrEnum):
    PRODUCT = "product"
    OPS_DEV = "ops_dev"


class ApiSurfaceTransport(StrEnum):
    HTTP = "http"
    REALTIME_STREAMING = "realtime_streaming"


class ApiContractLevel(StrEnum):
    PRODUCT_CONTRACT = "product_contract"
    OPS_DEV_ONLY = "ops_dev_only"


class FutureApiCapability(StrEnum):
    REQUEST_SUBMISSION_HTTP = "request_submission_http"
    INCIDENT_READ_HTTP = "incident_read_http"
    CONTROL_ACTION_HTTP = "control_action_http"
    STATUS_STREAMING = "status_streaming"
    OPERATOR_ATTENTION_STREAMING = "operator_attention_streaming"
    RAW_AGENTOS_OPERATIONS = "raw_agentos_operations"


@dataclass(frozen=True)
class ApiSurfaceRule:
    surface_id: ApiSurfaceId
    audience: ApiSurfaceAudience
    transport: ApiSurfaceTransport
    contract_level: ApiContractLevel
    route_patterns: tuple[str, ...]
    current_state: str
    placement_rule: str


@dataclass(frozen=True)
class FutureApiCapabilityPlacement:
    capability: FutureApiCapability
    surface_id: ApiSurfaceId
    rationale: str


@dataclass(frozen=True)
class RegisteredApiSurface:
    path: str
    transport: ApiSurfaceTransport
    surface_id: ApiSurfaceId | None
    route_name: str | None = None
    methods: tuple[str, ...] = ()


@dataclass(frozen=True)
class ApiSurfaceSnapshot:
    routes: tuple[RegisteredApiSurface, ...]

    @property
    def product_paths(self) -> tuple[str, ...]:
        return tuple(
            route.path
            for route in self.routes
            if route.surface_id
            in {ApiSurfaceId.PRODUCT_HTTP, ApiSurfaceId.PRODUCT_REALTIME}
        )

    @property
    def ops_dev_paths(self) -> tuple[str, ...]:
        return tuple(
            route.path
            for route in self.routes
            if route.surface_id
            in {ApiSurfaceId.AGENTOS_HTTP, ApiSurfaceId.AGENTOS_REALTIME}
        )

    @property
    def unclassified_paths(self) -> tuple[str, ...]:
        return tuple(route.path for route in self.routes if route.surface_id is None)


@dataclass(frozen=True)
class TianHaiApiSurfaceGovernance:
    surfaces: tuple[ApiSurfaceRule, ...]
    future_capabilities: tuple[FutureApiCapabilityPlacement, ...]
    product_prefix: str = TIANHAI_PRODUCT_API_PREFIX

    def get_surface(self, surface_id: ApiSurfaceId) -> ApiSurfaceRule:
        for surface in self.surfaces:
            if surface.surface_id == surface_id:
                return surface
        raise KeyError(surface_id)

    def placement_for(
        self,
        capability: FutureApiCapability,
    ) -> FutureApiCapabilityPlacement:
        for placement in self.future_capabilities:
            if placement.capability == capability:
                return placement
        raise KeyError(capability)

    def classify_path(
        self,
        path: str,
        *,
        transport: ApiSurfaceTransport,
    ) -> ApiSurfaceId | None:
        if _is_product_path(path):
            if transport is ApiSurfaceTransport.HTTP:
                return ApiSurfaceId.PRODUCT_HTTP
            return ApiSurfaceId.PRODUCT_REALTIME

        if transport is ApiSurfaceTransport.REALTIME_STREAMING:
            if path in AGENTOS_STREAMING_PATHS:
                return ApiSurfaceId.AGENTOS_REALTIME
            return None

        if path in AGENTOS_HTTP_EXACT_PATHS:
            return ApiSurfaceId.AGENTOS_HTTP
        if any(path == prefix or path.startswith(f"{prefix}/") for prefix in AGENTOS_HTTP_PREFIXES):
            return ApiSurfaceId.AGENTOS_HTTP
        return None


DEFAULT_API_SURFACE_GOVERNANCE = TianHaiApiSurfaceGovernance(
    surfaces=(
        ApiSurfaceRule(
            surface_id=ApiSurfaceId.PRODUCT_HTTP,
            audience=ApiSurfaceAudience.PRODUCT,
            transport=ApiSurfaceTransport.HTTP,
            contract_level=ApiContractLevel.PRODUCT_CONTRACT,
            route_patterns=(f"{TIANHAI_PRODUCT_API_PREFIX}/*",),
            current_state="reserved_no_product_http_routes_registered",
            placement_rule=(
                "Future TianHai HTTP features must be added under /tianhai/* "
                "as the product contract, separate from raw AgentOS routes."
            ),
        ),
        ApiSurfaceRule(
            surface_id=ApiSurfaceId.PRODUCT_REALTIME,
            audience=ApiSurfaceAudience.PRODUCT,
            transport=ApiSurfaceTransport.REALTIME_STREAMING,
            contract_level=ApiContractLevel.PRODUCT_CONTRACT,
            route_patterns=(f"{TIANHAI_PRODUCT_API_PREFIX}/*",),
            current_state="reserved_no_product_streaming_routes_registered",
            placement_rule=(
                "Future TianHai realtime streaming must stay under the "
                "/tianhai/* product namespace without reusing raw AgentOS "
                "streaming as the client contract."
            ),
        ),
        ApiSurfaceRule(
            surface_id=ApiSurfaceId.AGENTOS_HTTP,
            audience=ApiSurfaceAudience.OPS_DEV,
            transport=ApiSurfaceTransport.HTTP,
            contract_level=ApiContractLevel.OPS_DEV_ONLY,
            route_patterns=AGENTOS_HTTP_EXACT_PATHS + tuple(
                f"{prefix}/*" for prefix in AGENTOS_HTTP_PREFIXES
            ),
            current_state="active_raw_agentos_auto_surface",
            placement_rule=(
                "Raw AgentOS HTTP routes are kept for ops and development "
                "access only and are not TianHai's product API contract."
            ),
        ),
        ApiSurfaceRule(
            surface_id=ApiSurfaceId.AGENTOS_REALTIME,
            audience=ApiSurfaceAudience.OPS_DEV,
            transport=ApiSurfaceTransport.REALTIME_STREAMING,
            contract_level=ApiContractLevel.OPS_DEV_ONLY,
            route_patterns=AGENTOS_STREAMING_PATHS,
            current_state="active_raw_agentos_auto_surface",
            placement_rule=(
                "Raw AgentOS realtime routes stay available only as ops/dev "
                "surfaces and must not be treated as TianHai client streaming."
            ),
        ),
    ),
    future_capabilities=(
        FutureApiCapabilityPlacement(
            capability=FutureApiCapability.REQUEST_SUBMISSION_HTTP,
            surface_id=ApiSurfaceId.PRODUCT_HTTP,
            rationale=(
                "User-facing request submission belongs to the /tianhai/* "
                "product contract instead of direct /agents/* or /workflows/* calls."
            ),
        ),
        FutureApiCapabilityPlacement(
            capability=FutureApiCapability.INCIDENT_READ_HTTP,
            surface_id=ApiSurfaceId.PRODUCT_HTTP,
            rationale=(
                "Incident read models and result retrieval should be exposed as "
                "TianHai product resources rather than raw AgentOS workflow state."
            ),
        ),
        FutureApiCapabilityPlacement(
            capability=FutureApiCapability.CONTROL_ACTION_HTTP,
            surface_id=ApiSurfaceId.PRODUCT_HTTP,
            rationale=(
                "Future approval, pause, continue, and cancellation actions "
                "should be wrapped by the TianHai product contract instead of "
                "leaking AgentOS workflow control endpoints."
            ),
        ),
        FutureApiCapabilityPlacement(
            capability=FutureApiCapability.STATUS_STREAMING,
            surface_id=ApiSurfaceId.PRODUCT_REALTIME,
            rationale=(
                "Incident and run status streaming belongs on TianHai product "
                "streaming surfaces, not on raw AgentOS websocket endpoints."
            ),
        ),
        FutureApiCapabilityPlacement(
            capability=FutureApiCapability.OPERATOR_ATTENTION_STREAMING,
            surface_id=ApiSurfaceId.PRODUCT_REALTIME,
            rationale=(
                "Operator-attention and approval-needed events should flow "
                "through the future TianHai product streaming boundary without "
                "locking a protocol in Phase 8."
            ),
        ),
        FutureApiCapabilityPlacement(
            capability=FutureApiCapability.RAW_AGENTOS_OPERATIONS,
            surface_id=ApiSurfaceId.AGENTOS_HTTP,
            rationale=(
                "Low-level AgentOS agent, workflow, knowledge, trace, "
                "schedule, and registry operations remain ops/dev-only."
            ),
        ),
    ),
)


def inspect_app_api_surfaces(
    app: FastAPI,
    *,
    governance: TianHaiApiSurfaceGovernance = DEFAULT_API_SURFACE_GOVERNANCE,
) -> ApiSurfaceSnapshot:
    routes: list[RegisteredApiSurface] = []

    for route in app.routes:
        if isinstance(route, APIWebSocketRoute):
            transport = ApiSurfaceTransport.REALTIME_STREAMING
            methods: tuple[str, ...] = ()
        elif isinstance(route, APIRoute):
            transport = ApiSurfaceTransport.HTTP
            methods = tuple(sorted(route.methods or ()))
        else:
            continue

        routes.append(
            RegisteredApiSurface(
                path=route.path,
                transport=transport,
                surface_id=governance.classify_path(route.path, transport=transport),
                route_name=route.name,
                methods=methods,
            )
        )

    return ApiSurfaceSnapshot(routes=tuple(routes))


def apply_api_surface_governance(
    app: FastAPI,
    *,
    governance: TianHaiApiSurfaceGovernance = DEFAULT_API_SURFACE_GOVERNANCE,
) -> FastAPI:
    app.state.tianhai_api_surface_governance = governance
    app.state.tianhai_api_surface_snapshot = inspect_app_api_surfaces(
        app,
        governance=governance,
    )
    return app


def _is_product_path(path: str) -> bool:
    return path == TIANHAI_PRODUCT_API_PREFIX or path.startswith(
        f"{TIANHAI_PRODUCT_API_PREFIX}/"
    )


__all__ = (
    "AGENTOS_HTTP_EXACT_PATHS",
    "AGENTOS_HTTP_PREFIXES",
    "AGENTOS_STREAMING_PATHS",
    "ApiContractLevel",
    "ApiSurfaceAudience",
    "ApiSurfaceId",
    "ApiSurfaceRule",
    "ApiSurfaceSnapshot",
    "ApiSurfaceTransport",
    "DEFAULT_API_SURFACE_GOVERNANCE",
    "FutureApiCapability",
    "FutureApiCapabilityPlacement",
    "RegisteredApiSurface",
    "TIANHAI_PRODUCT_API_PREFIX",
    "TianHaiApiSurfaceGovernance",
    "apply_api_surface_governance",
    "inspect_app_api_surfaces",
)
