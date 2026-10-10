import json
from json import JSONDecodeError

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from software_factory.demo_reset import reset_demo_state

from .runner import start_factory
from .status_store import IDLE_STATUS, UNKNOWN_JOB_STATUS, read_status


@require_POST
def fix(request):
    if request.content_type == "application/json":
        try:
            payload = json.loads(request.body or "{}")
        except JSONDecodeError:
            return JsonResponse({"error": "Request body must be valid JSON."}, status=400)
        task = payload.get("task", "")
    else:
        task = request.POST.get("task", "")

    task = task.strip()
    if not task:
        return JsonResponse({"error": "Task text is required."}, status=400)

    return JsonResponse(start_factory(task), status=202)


@require_GET
def status(request):
    job_id = request.GET.get("job_id")
    if not job_id:
        return JsonResponse(IDLE_STATUS)

    status_payload = read_status(job_id=job_id)
    if status_payload is None:
        status_payload = {**UNKNOWN_JOB_STATUS, "job_id": job_id}
    return JsonResponse(status_payload)


@require_GET
def demo_epoch(request):
    epoch = settings.DEMO_EPOCH_FILE.read_text(encoding="utf-8").strip() if settings.DEMO_EPOCH_FILE.exists() else ""
    return JsonResponse({"epoch": epoch})


@require_POST
def reset_demo(request):
    reset_demo_state()
    epoch = settings.DEMO_EPOCH_FILE.read_text(encoding="utf-8").strip() if settings.DEMO_EPOCH_FILE.exists() else ""
    return JsonResponse({"state": "idle", "epoch": epoch})
