# accounts/views_profile.py
"""
Views para gestión de perfil propio y funciones de coach.

Incluye:
- profile_edit: editar datos básicos del propio perfil
- profile_photo_upload: subir/eliminar foto de perfil
- profile_settings: notificaciones + privacidad
- user_search_api: búsqueda de usuarios (JSON para HTMX/JS)
- bulk_import_athletes: importar CSV de atletas
- guardian_dashboard: dashboard del tutor/padre
- account_deactivate: desactivar cuenta propia
"""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.http import HttpResponse, JsonResponse

logger = logging.getLogger(__name__)
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST, require_GET

from accounts.decorators import role_required
from accounts.forms_profile import (
    ProfileEditForm,
    ProfilePhotoForm,
    NotificationPreferencesForm,
    PrivacySettingsForm,
)
from accounts.services.profile_service import ProfileService
from accounts.services.user_search_service import UserSearchService
from accounts.services.bulk_import_service import BulkImportService
from accounts.services.pii_audit_service import PiiAuditService

# =============================================================================
# PERFIL PROPIO — Editar datos básicos
# =============================================================================


def _style_password_form(form):
    """Aplica clases de bootstrap al formulario de contraseña."""
    for field in form.fields.values():
        # Preservar estilos existentes si los hay y agregar form-control
        existing = field.widget.attrs.get('class', '')
        field.widget.attrs.update({'class': f'{existing} form-control'.strip()})

@login_required
def profile_edit(request):
    """
    Permite al usuario editar sus propios datos básicos y actualizar su contraseña.
    Cualquier usuario autenticado puede acceder.
    """
    user = request.user

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "change_password":
            password_form = PasswordChangeForm(user, request.POST)
            _style_password_form(password_form)
            form = ProfileEditForm(instance=user)
            
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)  # Evita que el usuario pierda la sesión
                messages.success(request, "Tu contraseña ha sido actualizada correctamente.")
                return redirect("accounts:profile_edit")
            else:
                for field, errors in password_form.errors.items():
                    for error in errors:
                        messages.error(request, f"{error}")
        else:
            form = ProfileEditForm(request.POST, instance=user)
            password_form = PasswordChangeForm(user)
            _style_password_form(password_form)

            if form.is_valid():
                try:
                    ProfileService.update_profile(
                        user=user,
                        first_name=form.cleaned_data.get("first_name"),
                        last_name=form.cleaned_data.get("last_name"),
                        phone=form.cleaned_data.get("phone"),
                        birth_date=form.cleaned_data.get("birth_date"),
                        gender=form.cleaned_data.get("gender"),
                    )
                    messages.success(request, "Perfil actualizado correctamente.")
                    return redirect("accounts:profile_edit")

                except ValidationError as e:
                    for msg in e.messages:
                        messages.error(request, msg)
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{form.fields[field].label}: {error}")

    else:
        form = ProfileEditForm(instance=user)
        password_form = PasswordChangeForm(user)
        _style_password_form(password_form)

    return render(
        request,
        "account/profile/edit.html",
        {
            "form": form,
            "password_form": password_form,
            "user": user,
        },
    )


# =============================================================================
# FOTO DE PERFIL
# =============================================================================


@login_required
def profile_photo_upload(request):
    """
    Sube una nueva foto de perfil.
    Valida magic bytes vía ProfileService.
    """
    if request.method == "POST":
        form = ProfilePhotoForm(request.POST, request.FILES)

        if form.is_valid():
            try:
                ProfileService.upload_profile_photo(
                    user=request.user,
                    photo_file=form.cleaned_data["photo"],
                )
                messages.success(request, "Foto de perfil actualizada.")
            except ValidationError as e:
                for msg in e.messages:
                    messages.error(request, msg)
        else:
            messages.error(
                request, "Error con el archivo. Verifica el formato y tamaño."
            )

        return redirect("accounts:profile_edit")

    # GET: no tiene página propia, el form está en profile_edit
    return redirect("accounts:profile_edit")


@login_required
@require_POST
def profile_photo_delete(request):
    """Elimina la foto de perfil del usuario."""
    ProfileService.delete_profile_photo(user=request.user)
    messages.success(request, "Foto de perfil eliminada.")
    return redirect("accounts:profile_edit")


# =============================================================================
# CONFIGURACIÓN: Notificaciones + Privacidad
# =============================================================================


@login_required
def profile_settings(request):
    """
    Página unificada de configuración:
    - Preferencias de notificación
    - Configuración de privacidad
    """
    user = request.user

    # Asegurar que existen los objetos de preferencias
    ProfileService.ensure_preferences_exist(user)

    notif_prefs = user.notification_preferences
    privacy = user.privacy_settings

    if request.method == "POST":
        section = request.POST.get("section")

        if section == "notifications":
            form = NotificationPreferencesForm(request.POST, instance=notif_prefs)
            if form.is_valid():
                form.save()
                messages.success(request, "Preferencias de notificación guardadas.")
            else:
                messages.error(request, "Error al guardar preferencias.")

        elif section == "privacy":
            form = PrivacySettingsForm(request.POST, instance=privacy)
            if form.is_valid():
                form.save()
                messages.success(request, "Configuración de privacidad guardada.")
            else:
                messages.error(request, "Error al guardar configuración.")

        return redirect("accounts:profile_settings")

    notif_form = NotificationPreferencesForm(instance=notif_prefs)
    privacy_form = PrivacySettingsForm(instance=privacy)

    return render(
        request,
        "account/profile/settings.html",
        {
            "notif_form": notif_form,
            "privacy_form": privacy_form,
        },
    )


# =============================================================================
# BÚSQUEDA DE USUARIOS (JSON — para HTMX o fetch JS)
# =============================================================================


@role_required("HEADCOACH", "ADMIN")
@require_GET
def user_search_api(request):
    """
    Endpoint de búsqueda de usuarios.
    Retorna JSON para uso con HTMX o fetch() en templates.

    Query params:
        q: texto de búsqueda (mínimo 2 caracteres)
        role: filtro de rol (opcional, ej: "ATHLETE")
        exclude: IDs a excluir separados por coma (opcional)

    Ejemplo:
        GET /accounts/search/?q=ana&role=ATLETA&exclude=1,2,3
    """
    query = request.GET.get("q", "").strip()
    role_filter = request.GET.get("role", "")
    exclude_str = request.GET.get("exclude", "")

    exclude_ids = []
    if exclude_str:
        try:
            exclude_ids = [int(x) for x in exclude_str.split(",") if x.strip()]
        except ValueError:
            pass

    if len(query) < 2:
        return JsonResponse({"users": [], "count": 0})

    users = UserSearchService.search(
        query=query,
        searching_user=request.user,
        role_filter=role_filter or None,
        exclude_ids=exclude_ids,
    )

    data = [
        {
            "id": u.id,
            "full_name": u.get_full_name() or u.username,
            "email": u.email,
            "username": u.username,
            "roles": list(u.roles.values_list("name", flat=True)),
            "photo_url": u.foto_perfil.url if u.foto_perfil else None,
        }
        for u in users
    ]

    return JsonResponse({"users": data, "count": len(data)})


# =============================================================================
# IMPORTACIÓN MASIVA CSV
# =============================================================================


@role_required("HEADCOACH", "ADMIN")
def bulk_import_athletes(request):
    """
    Importa atletas desde un archivo CSV.
    GET: Muestra formulario + instrucciones
    POST: Procesa el CSV
    """
    if request.method == "POST":
        csv_file = request.FILES.get("csv_file")

        if not csv_file:
            messages.error(request, "Debes subir un archivo CSV.")
            return redirect("accounts:bulk_import_athletes")

        # Validar extensión
        if not csv_file.name.endswith(".csv"):
            messages.error(request, "El archivo debe tener extensión .csv")
            return redirect("accounts:bulk_import_athletes")

        try:
            result = BulkImportService.import_from_csv(
                csv_file=csv_file,
                imported_by=request.user,
            )

            # Log de auditoría para importación masiva
            PiiAuditService.log_bulk_import(
                request=request,
                count=result.success_count,
                notes=f"Archivo: {csv_file.name}",
            )

            # Mensaje de resultado
            if result.success_count:
                messages.success(
                    request,
                    f"{result.success_count} atleta(s) importado(s) correctamente.",
                )
            if result.skipped_count:
                messages.info(
                    request,
                    f"{result.skipped_count} atleta(s) omitido(s) (ya existían en tu grupo).",
                )

            # Mostrar errores por fila
            if result.error_rows:
                messages.warning(
                    request,
                    f"{len(result.error_rows)} fila(s) con error (ver detalle abajo).",
                )

            return render(
                request,
                "account/bulk_import/result.html",
                {"result": result},
            )

        except ValidationError as e:
            for msg in e.messages:
                messages.error(request, msg)

        return redirect("accounts:bulk_import_athletes")

    return render(request, "account/bulk_import/form.html")


@role_required("HEADCOACH", "ADMIN")
def bulk_import_template_download(request):
    """Descarga el CSV plantilla para importación masiva."""
    response = HttpResponse(
        BulkImportService.get_csv_template(),
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = 'attachment; filename="plantilla_atletas.csv"'
    return response


# =============================================================================
# DESACTIVAR CUENTA
# =============================================================================


@login_required
def account_deactivate(request):
    """
    El usuario puede desactivar su propia cuenta.
    Requiere confirmación explícita (POST con campo de confirmación).
    """
    if request.method == "POST":
        confirm = request.POST.get("confirm_deactivate")

        if confirm != "CONFIRMAR":
            messages.error(
                request,
                'Escribe "CONFIRMAR" para desactivar tu cuenta.',
            )
            return redirect("accounts:account_deactivate")

        try:
            ProfileService.deactivate_account(
                user=request.user,
                deactivated_by=request.user,
                reason="Auto-desactivación por el usuario",
            )
            # Django hace logout automático al invalidar el usuario
            from django.contrib.auth import logout

            logout(request)
            messages.success(
                request,
                "Tu cuenta ha sido desactivada. Contacta al administrador si deseas reactivarla.",
            )
            return redirect("account_login")

        except Exception as e:
            logger.exception("Error al desactivar cuenta para user=%s: %s", request.user.id, e)
            messages.error(request, "Ocurrió un error al desactivar tu cuenta. Contacta al administrador.")

    return render(request, "account/profile/deactivate_confirm.html")
