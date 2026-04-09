from tianhai.config import TianHaiSettings
from tianhai.server.factory import build_app
from tianhai.server.governance import (
    ApiContractLevel,
    ApiSurfaceAudience,
    ApiSurfaceId,
    ApiSurfaceTransport,
    DEFAULT_API_SURFACE_GOVERNANCE,
    FutureApiCapability,
    TIANHAI_PRODUCT_API_PREFIX,
    inspect_app_api_surfaces,
)


def test_phase8_governance_separates_product_and_agentos_boundaries() -> None:
    governance = DEFAULT_API_SURFACE_GOVERNANCE

    assert governance.get_surface(ApiSurfaceId.PRODUCT_HTTP).route_patterns == (
        f"{TIANHAI_PRODUCT_API_PREFIX}/*",
    )
    assert (
        governance.get_surface(ApiSurfaceId.PRODUCT_HTTP).contract_level
        == ApiContractLevel.PRODUCT_CONTRACT
    )
    assert (
        governance.get_surface(ApiSurfaceId.AGENTOS_HTTP).audience
        == ApiSurfaceAudience.OPS_DEV
    )
    assert (
        governance.classify_path(
            "/tianhai/incidents",
            transport=ApiSurfaceTransport.HTTP,
        )
        == ApiSurfaceId.PRODUCT_HTTP
    )
    assert (
        governance.classify_path(
            "/tianhai/incidents/stream",
            transport=ApiSurfaceTransport.REALTIME_STREAMING,
        )
        == ApiSurfaceId.PRODUCT_REALTIME
    )
    assert (
        governance.classify_path(
            "/agents/tianhai-primary-agent/runs",
            transport=ApiSurfaceTransport.HTTP,
        )
        == ApiSurfaceId.AGENTOS_HTTP
    )
    assert (
        governance.classify_path(
            "/workflows/ws",
            transport=ApiSurfaceTransport.REALTIME_STREAMING,
        )
        == ApiSurfaceId.AGENTOS_REALTIME
    )
    assert (
        governance.placement_for(FutureApiCapability.REQUEST_SUBMISSION_HTTP).surface_id
        == ApiSurfaceId.PRODUCT_HTTP
    )
    assert (
        governance.placement_for(FutureApiCapability.STATUS_STREAMING).surface_id
        == ApiSurfaceId.PRODUCT_REALTIME
    )
    assert (
        governance.placement_for(FutureApiCapability.RAW_AGENTOS_OPERATIONS).surface_id
        == ApiSurfaceId.AGENTOS_HTTP
    )


def test_build_app_exposes_only_agentos_routes_in_phase8() -> None:
    app = build_app(TianHaiSettings(sqlite_db_file=":memory:"))
    snapshot = app.state.tianhai_api_surface_snapshot

    assert app.state.tianhai_api_surface_governance is DEFAULT_API_SURFACE_GOVERNANCE
    assert snapshot.product_paths == ()
    assert "/agents/{agent_id}/runs" in snapshot.ops_dev_paths
    assert "/workflows/ws" in snapshot.ops_dev_paths
    assert snapshot.unclassified_paths == ()


def test_phase8_snapshot_matches_current_agentos_app_routes() -> None:
    app = build_app(TianHaiSettings(sqlite_db_file=":memory:"))
    snapshot = inspect_app_api_surfaces(app)

    assert "/health" in snapshot.ops_dev_paths
    assert "/knowledge/search" in snapshot.ops_dev_paths
    assert "/approvals/{approval_id}/resolve" in snapshot.ops_dev_paths
    assert "/tianhai" not in snapshot.ops_dev_paths
    assert all(not path.startswith("/tianhai/") for path in snapshot.ops_dev_paths)
