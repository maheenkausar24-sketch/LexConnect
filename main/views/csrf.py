from django.contrib import messages
from django.shortcuts import render


def csrf_failure(request, reason=""):
    messages.error(
        request,
        "Your session or security token changed. This often happens when signing in as a different role "
        "in another browser tab. Refresh this page and try again, or use a separate browser window for each role.",
    )
    return render(request, "csrf_failure.html", {"reason": reason}, status=403)
