from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import FastAPI, Response


# Define metrics
vm_created_counter = Counter(
    "minicloud_vm_created_total",
    "Total number of VMs created",
)

vm_deleted_counter = Counter(
    "minicloud_vm_deleted_total",
    "Total number of VMs deleted",
)

vm_operation_failures = Counter(
    "minicloud_vm_operation_failures_total",
    "Total failed VM operations",
    ["operation"],
)

task_completed_counter = Counter(
    "minicloud_task_completed_total",
    "Total completed tasks",
    ["task_type", "status"],
)

task_duration_seconds = Histogram(
    "minicloud_task_duration_seconds",
    "Task execution duration",
    ["task_type"],
)


def setup_metrics(app: FastAPI):
    @app.get("/metrics")
    async def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)