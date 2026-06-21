from __future__ import annotations

from app.ids import new_id
from app.repositories import DataRepository
from app.schemas import Alert, AlertSeverity, Observation, Task, TaskState, TaskType


class TaskCreationService:
    def __init__(self, repository: DataRepository) -> None:
        self._repository = repository

    def create_from_observation(self, observation: Observation) -> tuple[list[Task], list[Alert]]:
        tasks: list[Task] = []
        alerts: list[Alert] = []

        if "medicine_visible_human_verification_required" in observation.risk_signals:
            task = self._repository.create_task(
                Task(
                    id=new_id("task"),
                    type=TaskType.SAFETY_ALERT,
                    state=TaskState.OPEN,
                    title="Check possible medicine left out",
                    body="Medicine appears visible in the home zone. Human verification is required.",
                    recommended_action="Please verify in person and move medicine to a safe place if needed.",
                    evidence_observation_ids=[observation.id],
                )
            )
            alert = self._repository.create_alert(
                Alert(
                    id=new_id("alert"),
                    task_id=task.id,
                    hazard_type="medicine_left_out",
                    severity=AlertSeverity.MEDIUM,
                    title="Possible medicine left out",
                    body="Medicine appears visible in the home zone. Please verify in person.",
                    recommended_action="Move medicine to the safe zone or acknowledge if intentional.",
                    evidence_observation_ids=[observation.id],
                )
            )
            tasks.append(task)
            alerts.append(alert)

        return tasks, alerts
