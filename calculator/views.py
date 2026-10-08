from django.conf import settings
from django.shortcuts import render

from . import services


OPERATIONS = {
    "add": ("Add", services.add),
    "subtract": ("Subtract", services.subtract),
    "multiply": ("Multiply", services.multiply),
    "divide": ("Divide", services.divide),
}


def index(request):
    context = {
        "left": "",
        "right": "",
        "operation": "divide",
        "operations": OPERATIONS,
        "result": None,
        "error": None,
        "demo_epoch": settings.DEMO_EPOCH_FILE.read_text(encoding="utf-8").strip() if settings.DEMO_EPOCH_FILE.exists() else "",
    }

    if request.method == "POST":
        context["left"] = request.POST.get("left", "0")
        context["right"] = request.POST.get("right", "0")
        context["operation"] = request.POST.get("operation", "divide")

        try:
            left = float(context["left"])
            right = float(context["right"])
            _, operation = OPERATIONS[context["operation"]]
            context["result"] = operation(left, right)
        except Exception as exc:
            context["error"] = f"{type(exc).__name__}: {exc}"

    return render(request, "calculator/index.html", context)

