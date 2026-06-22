from __future__ import annotations

import sys
from types import SimpleNamespace

from app import yolo_fall_adapter as yolo_module
from app.config import Settings
from app.yolo_fall_adapter import FallInferenceResult, UltralyticsFallAdapter


def test_validate_setup_disabled_is_honest_unavailable() -> None:
    adapter = UltralyticsFallAdapter(
        Settings(
            environment="test",
            database_enabled=False,
            action_yolo_fall_enabled=False,
        )
    )

    result = adapter.validate_setup()

    assert result.ready is False
    assert result.status.available is False
    assert result.status.state == "disabled"
    assert result.status.unavailable_reason == "disabled"
    assert result.status.model_path_configured is True
    assert result.status.model_file_exists is False
    assert result.checks["feature_enabled"].state == "failed"
    assert result.checks["ultralytics_import"].state == "skipped"
    assert result.checks["label_compatibility"].state == "skipped"


def test_default_model_path_resolves_to_bundled_artifact() -> None:
    adapter = UltralyticsFallAdapter(
        Settings(
            environment="test",
            database_enabled=False,
        )
    )

    model_path = adapter._model_path()

    assert model_path is not None
    assert model_path.name == "project-memoria-fall-best.pt"
    assert model_path.is_file()


def test_validate_setup_reports_missing_model_path_before_runtime_claims() -> None:
    adapter = UltralyticsFallAdapter(
        Settings(
            environment="test",
            database_enabled=False,
            action_yolo_fall_enabled=True,
            action_yolo_fall_model_path=None,
        )
    )

    result = adapter.validate_setup()

    assert result.ready is False
    assert result.status.available is False
    assert result.status.unavailable_reason == "missing_model_path"
    assert result.checks["model_path_configured"].state == "failed"
    assert result.checks["model_file_exists"].state == "skipped"
    assert result.checks["model_load"].state == "skipped"
    assert result.checks["label_compatibility"].state == "skipped"


def test_validate_setup_reports_missing_dependency_after_file_checks(tmp_path, monkeypatch) -> None:
    model_path = tmp_path / "fall-model.pt"
    model_path.write_bytes(b"fake-model-placeholder")

    def missing_ultralytics(_module_name: str):
        raise ModuleNotFoundError(name="ultralytics")

    monkeypatch.setattr(yolo_module, "import_module", missing_ultralytics)
    adapter = UltralyticsFallAdapter(
        Settings(
            environment="test",
            database_enabled=False,
            action_yolo_fall_enabled=True,
            action_yolo_fall_model_path=str(model_path),
        )
    )

    result = adapter.validate_setup()

    assert result.ready is False
    assert result.status.available is False
    assert result.status.state == "unavailable"
    assert result.status.unavailable_reason == "missing_dependency"
    assert result.checks["model_file_exists"].state == "passed"
    assert result.checks["ultralytics_import"].state == "failed"
    assert result.checks["ultralytics_import"].reason == "missing_dependency"
    assert result.checks["model_load"].state == "skipped"


def test_validate_setup_reports_model_load_failure(tmp_path, monkeypatch) -> None:
    model_path = tmp_path / "fall-model.pt"
    model_path.write_bytes(b"fake-model-placeholder")

    class FakeYOLO:
        def __init__(self, _model_path: str) -> None:
            raise RuntimeError("bad weights")

    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=FakeYOLO))
    adapter = UltralyticsFallAdapter(
        Settings(
            environment="test",
            database_enabled=False,
            action_yolo_fall_enabled=True,
            action_yolo_fall_model_path=str(model_path),
        )
    )

    result = adapter.validate_setup()

    assert result.ready is False
    assert result.status.available is False
    assert result.status.state == "error"
    assert result.status.unavailable_reason == "load_failure"
    assert result.checks["model_load"].state == "failed"
    assert result.checks["label_compatibility"].state == "failed"


def test_status_requires_fallen_and_non_fallen_label_compatibility(tmp_path, monkeypatch) -> None:
    model_path = tmp_path / "fall-model.pt"
    model_path.write_bytes(b"fake-model-placeholder")

    class FakeYOLO:
        names = {0: "fallen"}

        def __init__(self, _model_path: str) -> None:
            pass

    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=FakeYOLO))
    adapter = UltralyticsFallAdapter(
        Settings(
            environment="test",
            database_enabled=False,
            action_yolo_fall_enabled=True,
            action_yolo_fall_model_path=str(model_path),
        )
    )

    result = adapter.validate_setup()

    assert result.ready is False
    assert result.status.available is False
    assert result.status.state == "unavailable"
    assert result.status.unavailable_reason == "unsuitable_labels"
    assert result.status.model_file_exists is True
    assert result.status.model_loaded is True
    assert result.checks["ultralytics_import"].state == "passed"
    assert result.checks["model_load"].state == "passed"
    assert result.checks["label_compatibility"].state == "failed"
    assert result.checks["label_compatibility"].metadata["fallen_label_matches"] == ["fallen"]
    assert result.checks["label_compatibility"].metadata["non_fallen_label_matches"] == []


def test_status_ready_when_model_labels_include_memoria_style_fallen_and_not_fallen(
    tmp_path,
    monkeypatch,
) -> None:
    model_path = tmp_path / "fall-model.pt"
    model_path.write_bytes(b"fake-model-placeholder")

    class FakeYOLO:
        names = {0: "fallen", 1: "not fallen"}

        def __init__(self, _model_path: str) -> None:
            pass

    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=FakeYOLO))
    adapter = UltralyticsFallAdapter(
        Settings(
            environment="test",
            database_enabled=False,
            action_yolo_fall_enabled=True,
            action_yolo_fall_model_path=str(model_path),
        )
    )

    result = adapter.validate_setup()

    assert result.ready is True
    assert result.status.available is True
    assert result.status.state == "ready"
    assert result.status.model_file_exists is True
    assert result.status.model_loaded is True
    assert result.status.labels == ["fallen", "not fallen"]
    assert result.checks["label_compatibility"].state == "passed"
    assert result.checks["label_compatibility"].metadata["non_fallen_label_matches"] == [
        "not_fallen"
    ]


def test_validate_setup_sample_inference_failure_blocks_require_ready_result(
    tmp_path,
    monkeypatch,
) -> None:
    model_path = tmp_path / "fall-model.pt"
    model_path.write_bytes(b"fake-model-placeholder")

    class FakeYOLO:
        names = {0: "fallen", 1: "not fallen"}

        def __init__(self, _model_path: str) -> None:
            pass

    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=FakeYOLO))
    adapter = UltralyticsFallAdapter(
        Settings(
            environment="test",
            database_enabled=False,
            action_yolo_fall_enabled=True,
            action_yolo_fall_model_path=str(model_path),
        )
    )
    monkeypatch.setattr(
        adapter,
        "infer_frame",
        lambda _frame_bytes: FallInferenceResult(
            available=False,
            fallen=None,
            confidence=None,
            label=None,
            message="Sample inference failed.",
            unavailable_reason="inference_failure",
            metadata={"raw_frame_persisted": False},
        ),
    )

    result = adapter.validate_setup(sample_frame_bytes=b"not inspected by fake")

    assert result.ready is False
    assert result.status.available is True
    assert result.checks["sample_inference"].state == "failed"
    assert result.checks["sample_inference"].reason == "inference_failure"
