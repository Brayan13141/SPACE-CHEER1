from pathlib import Path
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404


@login_required
def serve_protected_media(request, path):
    media_root = Path(settings.MEDIA_ROOT).resolve()
    requested = (media_root / path).resolve()

    # Previene path traversal: la ruta resuelta debe estar dentro de MEDIA_ROOT
    if not str(requested).startswith(str(media_root) + ("/" if not str(media_root).endswith("/") else "")):
        raise Http404

    if not requested.is_file():
        raise Http404

    # Imágenes de diseño requieren permiso a nivel de orden
    if path.startswith("designs/"):
        from orders.models import OrderDesignImage
        from orders.permissions import OrderPermissions

        design = (
            OrderDesignImage.objects
            .filter(image=path)
            .select_related("order")
            .first()
        )
        if design and not OrderPermissions.can_view_order(request.user, design.order):
            raise Http404

    return FileResponse(requested.open("rb"))
