"""Unit tests for weight-governance evidence endpoints (no real config writes)."""

import copy
import uuid

import pytest
from fastapi.testclient import TestClient

from src.backend.config.database import SessionLocal
from src.backend.config.settings import settings as app_settings


def _cookie_jar() -> dict[str, str]:
    """Return a valid session cookie accepted by the auth middleware."""
    from datetime import datetime, timedelta, timezone

    from jose import jwt as jose_jwt

    from src.backend.api.server import AUTH_COOKIE_NAME

    now = datetime.now(timezone.utc)
    token = jose_jwt.encode(
        {"sub": "admin-1", "exp": now + timedelta(minutes=30), "iat": now},
        app_settings.auth_jwt_secret or "unit-test-secret",
        algorithm="HS256",
    )
    return {AUTH_COOKIE_NAME: token}


def _fake_admin(*args, **kwargs):
    return {"id": "admin-1", "role": "admin"}


def _fake_professor(*args, **kwargs):
    return {"id": "prof-1", "role": "professor"}


def _stored_config() -> dict:
    """Return a config with a pending, unevidenced weight change."""
    return {
        "weights": {"ast": 0.5, "token": 0.5},
        "advanced": {"weights_need_validation": True},
    }


def _evidence_payload() -> dict:
    """Return a complete validation-evidence payload."""
    return {
        "validation_run_id": "val-2026-01-01",
        "benchmark_dataset_id": "pan-validation",
        "metric_snapshot": "F1 0.91, AUC-PR 0.93",
    }


class TestAttachWeightGovernanceEvidence:
    """POST /api/settings/weight-governance-evidence behavior."""

    def test_records_evidence_and_clears_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that complete evidence clears the pending-validation flag."""
        from src.backend.api import server
        from src.backend.engines.scoring import fusion_engine

        monkeypatch.setattr(server, "_authenticate_request", _fake_admin)
        monkeypatch.setattr(
            fusion_engine, "load_engine_config", lambda: _stored_config()
        )
        saved: dict = {}

        def fake_save(config: dict) -> None:
            saved.update(copy.deepcopy(config))

        monkeypatch.setattr(fusion_engine, "save_engine_config", fake_save)
        client = TestClient(server.app)
        response = client.post(
            "/api/settings/weight-governance-evidence",
            json=_evidence_payload(),
            cookies=_cookie_jar(),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["cleared"] is True
        advanced = saved["advanced"]
        assert "weights_need_validation" not in advanced
        assert (
            advanced["weight_governance_evidence"]["validation_run_id"]
            == "val-2026-01-01"
        )

    def test_missing_fields_are_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that incomplete evidence returns 400 naming the gaps."""
        from src.backend.api import server

        monkeypatch.setattr(server, "_authenticate_request", _fake_admin)
        client = TestClient(server.app)
        response = client.post(
            "/api/settings/weight-governance-evidence",
            json={"validation_run_id": "val-1"},
            cookies=_cookie_jar(),
        )
        assert response.status_code == 400
        assert "benchmark_dataset_id" in response.json()["detail"]
        assert "metric_snapshot" in response.json()["detail"]

    def test_non_admin_is_forbidden(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that professors cannot record validation evidence."""
        from src.backend.api import server

        monkeypatch.setattr(server, "_authenticate_request", _fake_professor)
        client = TestClient(server.app)
        response = client.post(
            "/api/settings/weight-governance-evidence",
            json=_evidence_payload(),
            cookies=_cookie_jar(),
        )
        assert response.status_code == 403


class TestValidationGovernanceBlock:
    """GET /api/settings/validation exposes governance state for the UI."""

    def test_response_includes_governance_block(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that the validation payload carries the governance block."""
        from src.backend.api import server

        monkeypatch.setattr(server, "_authenticate_request", _fake_admin)
        client = TestClient(server.app)
        response = client.get("/api/settings/validation", cookies=_cookie_jar())
        assert response.status_code == 200
        block = response.json()["weight_governance"]
        assert set(block) == {
            "needs_validation",
            "changed_engines",
            "evidence",
            "warnings",
        }


def _labeled_run(run_id: str = "run-7") -> dict:
    """Return a minimal labeled benchmark run payload."""
    return {
        "run_id": run_id,
        "dataset_id": "pan-validation",
        "has_ground_truth": True,
        "pair_results": [{"file_a": "a.py", "file_b": "b.py", "label": 1}],
        "tool_scores": {"integritydesk": {}},
        "evaluation": {"integritydesk": {"precision": 0.9, "recall": 0.85, "f1": 0.87}},
    }


class TestAttachWeightGovernanceEvidenceAuto:
    """POST /api/settings/weight-governance-evidence/auto behavior."""

    def test_attaches_latest_labeled_run(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """Test that a labeled run becomes evidence and clears the flag."""
        import json

        from src.backend.api import server
        from src.backend.engines.scoring import fusion_engine

        (tmp_path / "run-7.json").write_text(json.dumps(_labeled_run()))
        (tmp_path / "unlabeled.json").write_text(json.dumps({"pair_results": []}))
        monkeypatch.setattr(server, "BENCHMARK_RUNS_DIR", tmp_path)
        monkeypatch.setattr(server, "_authenticate_request", _fake_admin)
        monkeypatch.setattr(
            fusion_engine, "load_engine_config", lambda: _stored_config()
        )
        saved: dict = {}

        def fake_save(config: dict) -> None:
            saved.update(copy.deepcopy(config))

        monkeypatch.setattr(fusion_engine, "save_engine_config", fake_save)
        client = TestClient(server.app)
        response = client.post(
            "/api/settings/weight-governance-evidence/auto", cookies=_cookie_jar()
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["cleared"] is True
        assert body["evidence"]["validation_run_id"] == "run-7"
        assert body["evidence"]["benchmark_dataset_id"] == "pan-validation"
        advanced = saved["advanced"]
        assert "weights_need_validation" not in advanced
        assert advanced["weight_governance_evidence"]["validation_run_id"] == "run-7"

    def test_no_labeled_runs_returns_404(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """Test that an empty runs dir explains itself instead of 500ing."""
        from src.backend.api import server

        monkeypatch.setattr(server, "BENCHMARK_RUNS_DIR", tmp_path)
        monkeypatch.setattr(server, "_authenticate_request", _fake_admin)
        client = TestClient(server.app)
        response = client.post(
            "/api/settings/weight-governance-evidence/auto", cookies=_cookie_jar()
        )
        assert response.status_code == 404
        assert "benchmark" in response.json()["detail"].lower()


class TestRevertWeightGovernance:
    """POST /api/settings/weight-governance-revert behavior."""

    def test_revert_restores_defaults_and_clears(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that revert restores shipped weights and drops the flag."""
        from src.backend.api import server
        from src.backend.engines.scoring import fusion_engine
        from src.backend.engines.scoring.fusion_engine import DEFAULT_WEIGHTS

        def fake_load() -> dict:
            return {
                "weights": {"ast": 0.9, "token": 0.1},
                "advanced": {
                    "weights_need_validation": True,
                    "weight_governance_evidence": {"validation_run_id": "old"},
                },
            }

        monkeypatch.setattr(server, "_authenticate_request", _fake_admin)
        monkeypatch.setattr(fusion_engine, "load_engine_config", fake_load)
        saved: dict = {}

        def fake_save(config: dict) -> None:
            saved.update(copy.deepcopy(config))

        monkeypatch.setattr(fusion_engine, "save_engine_config", fake_save)
        client = TestClient(server.app)
        response = client.post(
            "/api/settings/weight-governance-revert", cookies=_cookie_jar()
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["ok"] is True
        assert body["cleared"] is True
        assert saved["weights"] == dict(DEFAULT_WEIGHTS)
        assert "weights_need_validation" not in saved["advanced"]
        assert "weight_governance_evidence" not in saved["advanced"]


class TestValidationChangedEngines:
    """GET /api/settings/validation names real diffs vs shipped defaults."""

    def test_changed_engines_compare_against_defaults(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that only genuinely changed engines are reported."""
        from src.backend.api import server
        from src.backend.engines.scoring import fusion_engine
        from src.backend.engines.scoring.fusion_engine import DEFAULT_WEIGHTS

        weights = dict(DEFAULT_WEIGHTS)
        first_engine = next(iter(weights))
        weights[first_engine] = float(weights[first_engine]) + 0.05

        def fake_load() -> dict:
            return {
                "weights": weights,
                "advanced": {"weights_need_validation": True},
            }

        monkeypatch.setattr(server, "_authenticate_request", _fake_admin)
        monkeypatch.setattr(fusion_engine, "load_engine_config", fake_load)
        client = TestClient(server.app)
        response = client.get("/api/settings/validation", cookies=_cookie_jar())
        assert response.status_code == 200, response.text
        block = response.json()["weight_governance"]
        assert block["needs_validation"] is True
        assert block["changed_engines"] == [first_engine]
        assert any("validation_run_id" in warning for warning in block["warnings"])


class TestGovernanceFullLoop:
    """The user-visible flow through real endpoints: warn → attach → clear."""

    def test_flag_warn_attach_clear(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """Test that auto-attach resolves a flagged config end to end."""
        import json

        from src.backend.api import server
        from src.backend.engines.scoring import fusion_engine

        store = {
            "config": {
                "weights": {"ast": 0.5, "token": 0.5},
                "advanced": {"weights_need_validation": True},
            }
        }
        monkeypatch.setattr(
            fusion_engine,
            "load_engine_config",
            lambda: copy.deepcopy(store["config"]),
        )

        def fake_save(config: dict) -> None:
            store["config"] = copy.deepcopy(config)

        monkeypatch.setattr(fusion_engine, "save_engine_config", fake_save)
        (tmp_path / "run-1.json").write_text(json.dumps(_labeled_run("run-1")))
        monkeypatch.setattr(server, "BENCHMARK_RUNS_DIR", tmp_path)
        monkeypatch.setattr(server, "_authenticate_request", _fake_admin)
        client = TestClient(server.app)
        cookies = _cookie_jar()

        flagged = client.get("/api/settings/validation", cookies=cookies)
        assert flagged.status_code == 200, flagged.text
        assert flagged.json()["weight_governance"]["needs_validation"] is True
        assert any(
            "validation_run_id" in warning
            for warning in flagged.json()["weight_governance"]["warnings"]
        )

        attached = client.post(
            "/api/settings/weight-governance-evidence/auto", cookies=cookies
        )
        assert attached.status_code == 200, attached.text
        assert attached.json()["cleared"] is True

        cleared = client.get("/api/settings/validation", cookies=cookies)
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["weight_governance"]["needs_validation"] is False
        assert cleared.json()["valid"] is True


class TestEngineConfigAdminGate:
    """GET/PUT /api/settings/engine-config are admin-only."""

    def test_get_requires_admin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that professors cannot read engine configuration."""
        from src.backend.api import server

        monkeypatch.setattr(server, "_authenticate_request", _fake_professor)
        client = TestClient(server.app)
        response = client.get("/api/settings/engine-config", cookies=_cookie_jar())
        assert response.status_code == 403

    def test_put_requires_admin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that professors cannot rewrite engine weights."""
        from src.backend.api import server

        monkeypatch.setattr(server, "_authenticate_request", _fake_professor)
        client = TestClient(server.app)
        response = client.put(
            "/api/settings/engine-config",
            json={"weights": {"ast": 0.9, "token": 0.1}},
            cookies=_cookie_jar(),
        )
        assert response.status_code == 403

    def test_admin_put_with_evidence_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that admins with evidence can still update weights."""
        from src.backend.api import server
        from src.backend.engines.scoring import fusion_engine

        monkeypatch.setattr(server, "_authenticate_request", _fake_admin)
        monkeypatch.setattr(
            fusion_engine,
            "load_engine_config",
            lambda: {"weights": {"ast": 0.5, "token": 0.5}, "advanced": {}},
        )
        saved: dict = {}

        def fake_save(config: dict) -> None:
            saved.update(copy.deepcopy(config))

        monkeypatch.setattr(fusion_engine, "save_engine_config", fake_save)
        client = TestClient(server.app)
        response = client.put(
            "/api/settings/engine-config",
            json={
                "weights": {"ast": 0.6, "token": 0.4},
                "weight_governance_evidence": {
                    "validation_run_id": "val-1",
                    "benchmark_dataset_id": "pan",
                    "metric_snapshot": "F1 0.9",
                    "split": "validation",
                },
            },
            cookies=_cookie_jar(),
        )
        assert response.status_code == 200, response.text
        assert saved["weights"] == {"ast": 0.6, "token": 0.4}


def _delete_audit_test_rows() -> None:
    """Remove audit-test rows so reruns never pollute the workspace listing."""
    from src.backend.models.database import Tenant, User, WeightAudit

    with SessionLocal() as db:
        user_ids = [
            u.id for u in db.query(User).filter(User.email.like("audit-%@%")).all()
        ]
        if user_ids:
            db.query(WeightAudit).filter(
                WeightAudit.actor_user_id.in_(user_ids)
            ).delete(synchronize_session=False)
        db.query(User).filter(User.email.like("audit-%@%")).delete(
            synchronize_session=False
        )
        db.query(Tenant).filter(Tenant.name.like("Audit Workspace %")).delete(
            synchronize_session=False
        )
        db.commit()


@pytest.fixture(autouse=True)
def _isolated_audit_rows():
    """Each test starts with no audit-test rows from earlier tests."""
    _delete_audit_test_rows()
    yield
    _delete_audit_test_rows()


def _admin_user_with_row(monkeypatch: pytest.MonkeyPatch, tag: str):
    """Create a tenant + admin user row; fake auth as that user id."""
    from src.backend.api import server
    from src.backend.models.database import Tenant, User

    email = f"audit-{tag}-{uuid.uuid4().hex[:8]}@example.com"
    with SessionLocal() as db:
        tenant = Tenant(
            name=f"Audit Workspace {tag}",
            api_key_hash=f"test-hash-{uuid.uuid4().hex}",
        )
        db.add(tenant)
        db.flush()
        user = User(
            tenant_id=tenant.id,
            email=email,
            full_name="Audit Admin",
            password_hash="already-hashed",
            role="admin",
            is_active=True,
        )
        db.add(user)
        db.commit()
        tenant_id = str(tenant.id)
        user_id = str(user.id)

    def fake_auth(request):
        return {"id": user_id, "role": "admin", "tenant_id": tenant_id}

    monkeypatch.setattr(server, "_authenticate_request", fake_auth)
    return user_id


class TestWeightAuditTrail:
    """Audit rows for every governance mutation plus the history endpoint."""

    def test_manual_attach_records_audit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that manual evidence attach writes who/what/proof."""
        from src.backend.api import server
        from src.backend.engines.scoring import fusion_engine
        from src.backend.models.database import WeightAudit

        user_id = _admin_user_with_row(monkeypatch, "manual")
        monkeypatch.setattr(
            fusion_engine, "load_engine_config", lambda: _stored_config()
        )
        saved: dict = {}

        def fake_save(config: dict) -> None:
            saved.update(copy.deepcopy(config))

        monkeypatch.setattr(fusion_engine, "save_engine_config", fake_save)
        client = TestClient(server.app)
        response = client.post(
            "/api/settings/weight-governance-evidence",
            json=_evidence_payload(),
            cookies=_cookie_jar(),
        )
        assert response.status_code == 200, response.text
        with SessionLocal() as db:
            rows = (
                db.query(WeightAudit)
                .filter(WeightAudit.actor_user_id == user_id)
                .order_by(WeightAudit.created_at.desc())
                .all()
            )
            assert len(rows) == 1
            assert rows[0].action == "evidence_attached"
            assert rows[0].allowed is True
            assert (rows[0].evidence or {}).get("validation_run_id") == "val-2026-01-01"

    def test_auto_attach_and_revert_record_audit(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """Test that auto-attach and revert write distinguishable rows."""
        import json

        from src.backend.api import server
        from src.backend.engines.scoring import fusion_engine
        from src.backend.models.database import WeightAudit

        user_id = _admin_user_with_row(monkeypatch, "auto")
        (tmp_path / "run-9.json").write_text(
            json.dumps(
                {
                    "run_id": "run-9",
                    "dataset_id": "pan-validation",
                    "has_ground_truth": True,
                    "pair_results": [{"a": 1}],
                    "tool_scores": {"integritydesk": {}},
                    "evaluation": {"integritydesk": {"f1": 0.9}},
                }
            )
        )
        monkeypatch.setattr(server, "BENCHMARK_RUNS_DIR", tmp_path)
        monkeypatch.setattr(
            fusion_engine, "load_engine_config", lambda: _stored_config()
        )
        saved: dict = {}

        def fake_save(config: dict) -> None:
            saved.update(copy.deepcopy(config))

        monkeypatch.setattr(fusion_engine, "save_engine_config", fake_save)
        client = TestClient(server.app)
        auto = client.post(
            "/api/settings/weight-governance-evidence/auto", cookies=_cookie_jar()
        )
        assert auto.status_code == 200, auto.text
        revert = client.post(
            "/api/settings/weight-governance-revert", cookies=_cookie_jar()
        )
        assert revert.status_code == 200, revert.text
        with SessionLocal() as db:
            actions = [
                row.action
                for row in db.query(WeightAudit)
                .filter(WeightAudit.actor_user_id == user_id)
                .order_by(WeightAudit.created_at.asc())
                .all()
            ]
            assert actions == ["evidence_attached", "reverted_to_defaults"]

    def test_put_weights_records_audit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that a PUT weight change records before/after."""
        from src.backend.api import server
        from src.backend.engines.scoring import fusion_engine
        from src.backend.models.database import WeightAudit

        user_id = _admin_user_with_row(monkeypatch, "put")
        monkeypatch.setattr(
            fusion_engine, "load_engine_config", lambda: _stored_config()
        )
        saved: dict = {}

        def fake_save(config: dict) -> None:
            saved.update(copy.deepcopy(config))

        monkeypatch.setattr(fusion_engine, "save_engine_config", fake_save)
        client = TestClient(server.app)
        response = client.put(
            "/api/settings/engine-config",
            json={
                "weights": {"ast": 0.6, "token": 0.4},
                "weight_governance_evidence": {
                    "validation_run_id": "val-1",
                    "benchmark_dataset_id": "pan",
                    "metric_snapshot": "F1 0.9",
                    "split": "validation",
                },
            },
            cookies=_cookie_jar(),
        )
        assert response.status_code == 200, response.text
        with SessionLocal() as db:
            row = (
                db.query(WeightAudit)
                .filter(WeightAudit.actor_user_id == user_id)
                .order_by(WeightAudit.created_at.desc())
                .first()
            )
            assert row is not None
            assert row.action == "weights_updated"
            assert row.weights_after == {"ast": 0.6, "token": 0.4}

    def test_history_endpoint_lists_entries(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that the history endpoint serves newest-first entries."""
        from src.backend.api import server
        from src.backend.models.database import WeightAudit

        user_id = _admin_user_with_row(monkeypatch, "history")
        with SessionLocal() as db:
            db.add(
                WeightAudit(
                    action="weights_updated",
                    actor_user_id=user_id,
                    weights_before={"ast": 0.5},
                    weights_after={"ast": 0.6},
                    allowed=True,
                )
            )
            db.commit()
        client = TestClient(server.app)
        response = client.get("/api/settings/weight-audit", cookies=_cookie_jar())
        assert response.status_code == 200, response.text
        entries = response.json()["entries"]
        assert isinstance(entries, list)
        assert any(entry["action"] == "weights_updated" for entry in entries)

    def test_history_requires_admin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that professors cannot read the audit trail."""
        from src.backend.api import server

        monkeypatch.setattr(server, "_authenticate_request", _fake_professor)
        client = TestClient(server.app)
        response = client.get("/api/settings/weight-audit", cookies=_cookie_jar())
        assert response.status_code == 403

    def test_model_matches_migration(self) -> None:
        """Test that the ORM columns match the migration DDL."""
        from src.backend.models.database import WeightAudit

        assert set(WeightAudit.__table__.columns.keys()) == {
            "id",
            "action",
            "actor_user_id",
            "weights_before",
            "weights_after",
            "evidence",
            "allowed",
            "note",
            "created_at",
        }
