from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from io import BytesIO
import os
from pathlib import Path
from tempfile import gettempdir
from typing import Any

from app.config import Settings
from app.schemas import ActionRuntimeFallStatus


@dataclass(frozen=True)
class FallInferenceResult:
    available: bool
    fallen: bool | None
    confidence: float | None
    label: str | None
    message: str
    unavailable_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FallModelValidationCheck:
    ok: bool | None
    state: str
    message: str
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FallModelValidationResult:
    ready: bool
    status: ActionRuntimeFallStatus
    checks: dict[str, FallModelValidationCheck]
    sample_inference: FallInferenceResult | None = None

    @property
    def available(self) -> bool:
        return self.status.available


class UltralyticsFallAdapter:
    provider = "ultralytics"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model: Any | None = None
        self._labels: list[str] = []
        self._load_error: str | None = None

    def status(self) -> ActionRuntimeFallStatus:
        if not self._settings.action_yolo_fall_enabled:
            return self._unavailable(
                reason="disabled",
                message="Ultralytics fall adapter is disabled by configuration.",
                model_loaded=False,
                model_file_exists=False,
            )

        model_path = self._model_path()
        if model_path is None:
            return self._unavailable(
                reason="missing_model_path",
                message="ACTION_YOLO_FALL_MODEL_PATH is not configured.",
                model_loaded=False,
                model_file_exists=False,
            )
        model_file_exists = model_path.is_file()
        if not model_file_exists:
            return self._unavailable(
                reason="missing_model_file",
                message="Configured YOLO fall model file was not found.",
                model_loaded=False,
                model_file_exists=False,
                model_metadata=self._model_metadata(model_path),
            )

        yolo_cls, import_reason, import_message = self._import_yolo()
        if yolo_cls is None:
            return self._unavailable(
                reason=import_reason or "import_failure",
                message=import_message or "Ultralytics could not be imported.",
                model_loaded=False,
                model_file_exists=True,
                model_metadata=self._model_metadata(model_path),
            )

        model = self._load_model(yolo_cls, model_path)
        if model is None:
            return self._unavailable(
                reason="load_failure",
                message=self._load_error or "Configured YOLO fall model could not be loaded.",
                model_loaded=False,
                model_file_exists=True,
                model_metadata=self._model_metadata(model_path),
            )

        labels = self._labels_from_model(model)
        if not self._labels_are_suitable(labels):
            return self._unavailable(
                reason="unsuitable_labels",
                message=(
                    "Configured YOLO model labels must include both a configured "
                    "fallen-like class and a configured non-fallen/upright class."
                ),
                model_loaded=True,
                model_file_exists=True,
                labels=labels,
                model_metadata=self._model_metadata(model_path),
            )

        return ActionRuntimeFallStatus(
            enabled=True,
            available=True,
            state="ready",
            provider=self.provider,
            model_path_configured=True,
            model_file_exists=True,
            model_loaded=True,
            labels=labels,
            message="Ultralytics fall adapter is ready.",
            model_metadata=self._model_metadata(model_path),
        )

    def validate_setup(self, sample_frame_bytes: bytes | None = None) -> FallModelValidationResult:
        checks: dict[str, FallModelValidationCheck] = {}
        model_path = self._model_path()
        model_file_exists = bool(model_path and model_path.is_file())
        checks["feature_enabled"] = _validation_check(
            self._settings.action_yolo_fall_enabled,
            pass_message="ACTION_YOLO_FALL_ENABLED is true.",
            fail_message="ACTION_YOLO_FALL_ENABLED is false; fall-frame inference is unavailable.",
            reason=None if self._settings.action_yolo_fall_enabled else "disabled",
        )
        checks["model_path_configured"] = _validation_check(
            model_path is not None,
            pass_message="ACTION_YOLO_FALL_MODEL_PATH is configured.",
            fail_message="ACTION_YOLO_FALL_MODEL_PATH is not configured.",
            reason=None if model_path is not None else "missing_model_path",
            metadata=self._model_metadata(model_path) if model_path is not None else {},
        )
        if model_path is None:
            checks["model_file_exists"] = _skipped_check(
                "Model file existence check skipped until ACTION_YOLO_FALL_MODEL_PATH is configured.",
                reason="missing_model_path",
            )
        else:
            checks["model_file_exists"] = _validation_check(
                model_file_exists,
                pass_message="Configured YOLO fall model file exists.",
                fail_message="Configured YOLO fall model file was not found.",
                reason=None if model_file_exists else "missing_model_file",
                metadata=self._model_metadata(model_path),
            )

        if not self._settings.action_yolo_fall_enabled:
            status = self.status()
            checks["ultralytics_import"] = _skipped_check(
                "Ultralytics import check skipped because YOLO fall inference is disabled.",
                reason="disabled",
            )
            checks["model_load"] = _skipped_check(
                "Model load check skipped because YOLO fall inference is disabled.",
                reason="disabled",
            )
            checks["label_compatibility"] = _skipped_check(
                "Label compatibility check skipped because YOLO fall inference is disabled.",
                reason="disabled",
            )
            if sample_frame_bytes is not None:
                checks["sample_inference"] = _skipped_check(
                    "Sample inference skipped because YOLO fall inference is disabled.",
                    reason="disabled",
                )
            return FallModelValidationResult(ready=False, status=status, checks=checks)

        yolo_cls, import_reason, import_message = self._import_yolo()
        checks["ultralytics_import"] = _validation_check(
            yolo_cls is not None,
            pass_message="Ultralytics can be imported.",
            fail_message=import_message or "Ultralytics could not be imported.",
            reason=import_reason,
        )

        if model_path is None or not model_file_exists or yolo_cls is None:
            status = self.status()
            checks["model_load"] = _skipped_check(
                "Model load check skipped until dependency and model file checks pass.",
                reason=status.unavailable_reason,
            )
            checks["label_compatibility"] = _skipped_check(
                "Label compatibility check skipped until the model can load.",
                reason=status.unavailable_reason,
            )
            if sample_frame_bytes is not None:
                checks["sample_inference"] = _skipped_check(
                    "Sample inference skipped until the model runtime is ready.",
                    reason=status.unavailable_reason,
                )
            return FallModelValidationResult(ready=False, status=status, checks=checks)

        model = self._load_model(yolo_cls, model_path)
        checks["model_load"] = _validation_check(
            model is not None,
            pass_message="Configured YOLO fall model can load.",
            fail_message=self._load_error or "Configured YOLO fall model could not be loaded.",
            reason=None if model is not None else "load_failure",
            metadata=self._model_metadata(model_path),
        )

        labels = self._labels_from_model(model) if model is not None else []
        labels_compatible, label_metadata = self._label_compatibility(labels)
        checks["label_compatibility"] = _validation_check(
            labels_compatible,
            pass_message="Model labels include configured fallen and non-fallen classes.",
            fail_message=(
                "Model labels must include at least one configured fallen label and "
                "one configured non-fallen label."
            ),
            reason=None if labels_compatible else "unsuitable_labels",
            metadata=label_metadata,
        )

        status = self.status()
        sample_inference = None
        if sample_frame_bytes is not None:
            if not status.available:
                checks["sample_inference"] = _skipped_check(
                    "Sample inference skipped until the model runtime is ready.",
                    reason=status.unavailable_reason,
                )
            else:
                sample_inference = self.infer_frame(sample_frame_bytes)
                checks["sample_inference"] = _validation_check(
                    sample_inference.available,
                    pass_message="Sample frame inference ran without fabricating a fall claim.",
                    fail_message=sample_inference.message,
                    reason=sample_inference.unavailable_reason,
                    metadata={
                        "fallen": sample_inference.fallen,
                        "confidence": sample_inference.confidence,
                        "label": sample_inference.label,
                        "message": sample_inference.message,
                    },
                )

        sample_ready = sample_frame_bytes is None or (
            sample_inference is not None and sample_inference.available
        )
        return FallModelValidationResult(
            ready=status.available and sample_ready,
            status=status,
            checks=checks,
            sample_inference=sample_inference,
        )

    def infer_frame(self, frame_bytes: bytes) -> FallInferenceResult:
        status = self.status()
        if not status.available or self._model is None:
            return FallInferenceResult(
                available=False,
                fallen=None,
                confidence=None,
                label=None,
                message=status.message,
                unavailable_reason=status.unavailable_reason,
                metadata={
                    "runtime_status": status.model_dump(mode="json"),
                    "raw_frame_persisted": False,
                },
            )

        try:
            from PIL import Image

            image = Image.open(BytesIO(frame_bytes))
            image.load()
            results = self._model(image, verbose=False)
        except Exception as exc:  # pragma: no cover - depends on optional runtime
            return FallInferenceResult(
                available=False,
                fallen=None,
                confidence=None,
                label=None,
                message="YOLO fall inference failed for the uploaded frame.",
                unavailable_reason="inference_failure",
                metadata={
                    "error_type": type(exc).__name__,
                    "raw_frame_persisted": False,
                },
            )

        prediction = self._best_prediction(results)
        if prediction is None:
            return FallInferenceResult(
                available=True,
                fallen=None,
                confidence=None,
                label=None,
                message="YOLO fall model returned no recognized fall posture label.",
                metadata={
                    "labels": self._labels,
                    "confidence_threshold": self._settings.action_yolo_fall_confidence_threshold,
                    "raw_frame_persisted": False,
                },
            )

        label, confidence, model_fallen = prediction
        threshold = self._settings.action_yolo_fall_confidence_threshold
        threshold_met = confidence >= threshold
        return FallInferenceResult(
            available=True,
            fallen=model_fallen if threshold_met else False,
            confidence=confidence,
            label=label,
            message="YOLO fall inference completed.",
            metadata={
                "label": label,
                "model_fallen": model_fallen,
                "confidence": confidence,
                "confidence_threshold": threshold,
                "confidence_threshold_met": threshold_met,
                "labels": self._labels,
                "raw_frame_persisted": False,
            },
        )

    def _import_yolo(self) -> tuple[Any | None, str | None, str | None]:
        try:
            _ensure_cv_runtime_cache_dirs()
            module = import_module("ultralytics")
            return getattr(module, "YOLO"), None, None
        except ModuleNotFoundError as exc:
            if exc.name == "ultralytics":
                return (
                    None,
                    "missing_dependency",
                    "Ultralytics is not installed in the backend environment.",
                )
            return (
                None,
                "import_failure",
                "Ultralytics import failed because a dependency is unavailable.",
            )
        except Exception:
            return None, "import_failure", "Ultralytics could not be imported."

    def _load_model(self, yolo_cls: Any, model_path: Path) -> Any | None:
        if self._model is not None:
            return self._model
        try:
            self._model = yolo_cls(str(model_path))
            self._labels = self._labels_from_model(self._model)
        except Exception as exc:  # pragma: no cover - depends on optional runtime
            self._load_error = f"YOLO model load failed: {type(exc).__name__}."
            self._model = None
        return self._model

    def _best_prediction(self, results: Any) -> tuple[str, float, bool] | None:
        candidates: list[tuple[str, float, bool]] = []
        for result in results if isinstance(results, list) else list(results):
            names = self._names_from_result(result)
            probs = getattr(result, "probs", None)
            if probs is not None:
                top_index = getattr(probs, "top1", None)
                top_conf = getattr(probs, "top1conf", None)
                if top_index is not None and top_conf is not None:
                    label = self._label_for_index(names, int(top_index))
                    self._append_candidate(candidates, label, float(top_conf))

            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            classes = getattr(boxes, "cls", None)
            confidences = getattr(boxes, "conf", None)
            if classes is None or confidences is None:
                continue
            for class_index, confidence in zip(_as_list(classes), _as_list(confidences)):
                label = self._label_for_index(names, int(class_index))
                self._append_candidate(candidates, label, float(confidence))

        if not candidates:
            return None
        candidates.sort(key=lambda item: item[1], reverse=True)
        return candidates[0]

    def _append_candidate(
        self,
        candidates: list[tuple[str, float, bool]],
        label: str | None,
        confidence: float,
    ) -> None:
        normalized = _normalize_label(label)
        if normalized in self._settings.action_yolo_fall_fallen_label_set:
            candidates.append((label or normalized, confidence, True))
        elif normalized in self._settings.action_yolo_fall_non_fallen_label_set:
            candidates.append((label or normalized, confidence, False))

    def _labels_are_suitable(self, labels: list[str]) -> bool:
        compatible, _metadata = self._label_compatibility(labels)
        return compatible

    def _label_compatibility(self, labels: list[str]) -> tuple[bool, dict[str, Any]]:
        normalized_labels = {_normalize_label(label) for label in labels}
        fallen_matches = sorted(normalized_labels & self._settings.action_yolo_fall_fallen_label_set)
        non_fallen_matches = sorted(
            normalized_labels & self._settings.action_yolo_fall_non_fallen_label_set
        )
        return bool(fallen_matches and non_fallen_matches), {
            "labels": labels,
            "fallen_label_matches": fallen_matches,
            "non_fallen_label_matches": non_fallen_matches,
            "configured_fallen_labels": sorted(self._settings.action_yolo_fall_fallen_label_set),
            "configured_non_fallen_labels": sorted(
                self._settings.action_yolo_fall_non_fallen_label_set
            ),
        }

    def _labels_from_model(self, model: Any) -> list[str]:
        names = getattr(model, "names", None)
        if isinstance(names, dict):
            labels = [str(names[key]) for key in sorted(names)]
        elif isinstance(names, list):
            labels = [str(item) for item in names]
        else:
            labels = []
        self._labels = labels
        return labels

    @staticmethod
    def _names_from_result(result: Any) -> dict[int, str] | list[str]:
        names = getattr(result, "names", None)
        if isinstance(names, (dict, list)):
            return names
        return {}

    @staticmethod
    def _label_for_index(names: dict[int, str] | list[str], index: int) -> str | None:
        if isinstance(names, dict):
            value = names.get(index)
            return str(value) if value is not None else None
        if 0 <= index < len(names):
            return str(names[index])
        return None

    def _model_path(self) -> Path | None:
        value = (self._settings.action_yolo_fall_model_path or "").strip()
        return Path(value).expanduser() if value else None

    def _unavailable(
        self,
        *,
        reason: str,
        message: str,
        model_loaded: bool,
        model_file_exists: bool,
        labels: list[str] | None = None,
        model_metadata: dict[str, Any] | None = None,
    ) -> ActionRuntimeFallStatus:
        state = (
            "disabled"
            if reason == "disabled"
            else "error"
            if reason in {"load_failure", "import_failure"}
            else "unavailable"
        )
        return ActionRuntimeFallStatus(
            enabled=self._settings.action_yolo_fall_enabled,
            available=False,
            state=state,
            provider=self.provider,
            model_path_configured=bool(self._settings.action_yolo_fall_model_path),
            model_file_exists=model_file_exists,
            model_loaded=model_loaded,
            labels=labels or [],
            message=message,
            unavailable_reason=reason,
            model_metadata=model_metadata or {},
        )

    @staticmethod
    def _model_metadata(model_path: Path) -> dict[str, Any]:
        return {
            "model_filename": model_path.name,
            "model_suffix": model_path.suffix,
        }


def _validation_check(
    ok: bool,
    *,
    pass_message: str,
    fail_message: str,
    reason: str | None,
    metadata: dict[str, Any] | None = None,
) -> FallModelValidationCheck:
    return FallModelValidationCheck(
        ok=ok,
        state="passed" if ok else "failed",
        message=pass_message if ok else fail_message,
        reason=None if ok else reason,
        metadata=metadata or {},
    )


def _skipped_check(
    message: str,
    *,
    reason: str | None,
    metadata: dict[str, Any] | None = None,
) -> FallModelValidationCheck:
    return FallModelValidationCheck(
        ok=None,
        state="skipped",
        message=message,
        reason=reason,
        metadata=metadata or {},
    )


def _normalize_label(value: str | None) -> str:
    return (value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _as_list(value: Any) -> list[Any]:
    if hasattr(value, "tolist"):
        return list(value.tolist())
    return list(value)


def _ensure_cv_runtime_cache_dirs() -> None:
    cache_root = Path(gettempdir()) / "afferens-memory-guardian-cv"
    defaults = {
        "YOLO_CONFIG_DIR": cache_root / "ultralytics",
        "MPLCONFIGDIR": cache_root / "matplotlib",
    }
    for env_name, path in defaults.items():
        if os.environ.get(env_name):
            continue
        path.mkdir(parents=True, exist_ok=True)
        os.environ[env_name] = str(path)
