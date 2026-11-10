"""The records desk is not a core feature flag."""

import uuid

from fastapi.testclient import TestClient

from ar_contracts.tenants import FeatureFlags, TenantSettings
from ar_domain.chat.service import demo_id
from ar_domain.identity.tenant_settings import dev_tenant_settings, permissions_for_features
from ar_testing.demo import demo_application


def test_dev_settings_do_not_carry_a_records_feature_flag() -> None:
    settings = dev_tenant_settings()
    features = settings.get("features")
    assert isinstance(features, dict)
    assert "assurance" not in features
    assert "assurance" not in FeatureFlags.model_fields
    dumped = TenantSettings().model_dump(by_alias=True)
    assert "assurance" not in dumped["features"]


def test_permissions_are_not_stripped_by_a_removed_flag() -> None:
    store = demo_application().state.chat
    keys = frozenset({"chat:use", "audit:read"})
    assert permissions_for_features(store, demo_id("tenant"), keys) == keys
    other = uuid.uuid4()
    assert permissions_for_features(store, other, keys) == keys


def test_records_routes_are_absent_until_a_pack_mounts_them() -> None:
    client = TestClient(demo_application())
    paths = {getattr(route, "path", "") for route in client.app.routes}
    assert "/api/v1/evidence" not in paths
