import mimetypes
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404

from ..models import LegalDocument, Lawyer, Message
from ..services.auth import is_admin_user, is_lawyer_user
from ..services.chat import get_authorized_chat


def protected_file_response(field_file, *, as_attachment=False):
    if not field_file:
        raise Http404("File not found.")
    try:
        field_file.open("rb")
    except FileNotFoundError as exc:
        raise Http404("File not found.") from exc
    filename = Path(field_file.name).name
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return FileResponse(field_file, as_attachment=as_attachment, filename=filename, content_type=content_type)


@login_required
def protected_chat_file(request, message_id):
    message = get_object_or_404(Message.objects.select_related("chat", "chat__lawyer", "chat__booking"), id=message_id)
    get_authorized_chat(request.user, message.chat_id)
    return protected_file_response(message.file)


@login_required
def protected_certificate_file(request, lawyer_id):
    lawyer = get_object_or_404(Lawyer.objects.select_related("user"), id=lawyer_id)
    if not (is_admin_user(request.user) or request.user == lawyer.user):
        raise PermissionDenied("You cannot access this verification document.")
    return protected_file_response(lawyer.certificate_file, as_attachment=True)


@login_required
def protected_case_document(request, document_id):
    document = get_object_or_404(
        LegalDocument.objects.select_related("case", "case__client", "case__lawyer", "case__lawyer__user"),
        id=document_id,
    )
    is_case_lawyer = is_lawyer_user(request.user) and document.case.lawyer_id and document.case.lawyer.user_id == request.user.id
    if not (is_admin_user(request.user) or document.case.client_id == request.user.id or is_case_lawyer):
        raise PermissionDenied("You cannot access this legal document.")
    return protected_file_response(document.file, as_attachment=True)
