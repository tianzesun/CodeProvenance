"""Detector calibration is admin-only, and model files load through the restricted unpickler."""

import asyncio
import os
import pickle
import types

import pytest
from fastapi import HTTPException

from src.backend.api import server
from src.backend.engines.learned_scoring_model import LearnedScoringModel
from src.backend.engines.score_calibration import ScoreCalibrator
from src.backend.utils.safe_pickle import load_restricted_pickle

PROFESSOR = {"id": "u-prof", "role": "professor", "tenant_id": "t1"}
ADMIN = {"id": "u-admin", "role": "admin", "tenant_id": "t1"}


def _request(user):
    return types.SimpleNamespace(state=types.SimpleNamespace(user=user, tenant_id="t1"))


@pytest.fixture
def empty_calibration(monkeypatch):
    """A fresh in-memory sample list, so tests never touch the shared one."""
    samples: list = []
    monkeypatch.setattr(server, "_calibration_data", samples)
    return samples


class TestCalibrationEndpointsAreAdminOnly:
    def test_professor_cannot_submit_samples(self, empty_calibration) -> None:
        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                server.calibrate_ai_detector(
                    _request(PROFESSOR),
                    raw_score=0.9,
                    is_ai_generated=True,
                    code_sample="",
                )
            )
        assert exc.value.status_code == 403
        assert empty_calibration == []

    def test_professor_cannot_retrain(self, empty_calibration) -> None:
        with pytest.raises(HTTPException) as exc:
            asyncio.run(server.retrain_ai_detector(_request(PROFESSOR)))
        assert exc.value.status_code == 403

    def test_admin_can_submit_samples(self, empty_calibration) -> None:
        response = asyncio.run(
            server.calibrate_ai_detector(
                _request(ADMIN), raw_score=0.9, is_ai_generated=True, code_sample=""
            )
        )
        assert response.status_code == 200
        assert len(empty_calibration) == 1

    def test_admin_retrain_still_needs_ten_samples(self, empty_calibration) -> None:
        response = asyncio.run(server.retrain_ai_detector(_request(ADMIN)))
        assert response.status_code == 400


class _RunsCode:
    """Pickles to a call of ``os.system`` — what an attacker would write."""

    def __reduce__(self):
        return (os.system, ("true",))


class TestRestrictedUnpickling:
    def test_refuses_a_payload_that_runs_code(self, tmp_path) -> None:
        path = tmp_path / "evil.pkl"
        path.write_bytes(pickle.dumps({"calibrator": _RunsCode(), "is_fitted": True}))
        with pytest.raises(pickle.UnpicklingError):
            load_restricted_pickle(path)

    def test_score_calibrator_refuses_a_payload_that_runs_code(self, tmp_path) -> None:
        path = tmp_path / "evil.pkl"
        path.write_bytes(pickle.dumps({"calibrator": _RunsCode(), "is_fitted": True}))
        with pytest.raises(pickle.UnpicklingError):
            ScoreCalibrator().load(str(path))

    def test_scoring_model_refuses_a_payload_that_runs_code(self, tmp_path) -> None:
        path = tmp_path / "evil.pkl"
        path.write_bytes(pickle.dumps({"model": _RunsCode(), "is_trained": True}))
        with pytest.raises(pickle.UnpicklingError):
            LearnedScoringModel().load(str(path))

    def test_refuses_a_world_writable_file(self, tmp_path) -> None:
        path = tmp_path / "open.pkl"
        path.write_bytes(pickle.dumps({"a": 1}))
        path.chmod(0o666)
        with pytest.raises(PermissionError):
            load_restricted_pickle(path)

    def test_fitted_score_calibrator_round_trips(self, tmp_path) -> None:
        pytest.importorskip("sklearn")
        calibrator = ScoreCalibrator()
        calibrator.fit([0.1, 0.2, 0.3, 0.7, 0.8, 0.9] * 2, [0, 0, 0, 1, 1, 1] * 2)
        path = tmp_path / "calibrator.pkl"
        calibrator.save(str(path))

        loaded = ScoreCalibrator(model_path=str(path))

        assert loaded.is_fitted
        assert loaded.calibrate(0.85) == pytest.approx(calibrator.calibrate(0.85))
