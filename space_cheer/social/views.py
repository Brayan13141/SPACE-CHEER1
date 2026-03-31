from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from invitations.utils import get_invitation_model

Invitation = get_invitation_model()


@login_required
def send_invite(request):
    if request.method == "POST":
        email = request.POST.get("email")

        if not email:
            messages.error(request, "Por favor ingresa un email válido.")
            return redirect("social:send_invite")

        existing = Invitation.objects.filter(email=email, accepted=False).first()

        if existing:
            if existing.sent is None or existing.key_expired():
                existing.delete()
            else:
                messages.warning(
                    request, f"Ya hay una invitación pendiente para {email}."
                )
                return redirect("social:send_invite")

        invite = Invitation.create(email=email, inviter=request.user)
        invite.sent = timezone.now()
        invite.save()
        invite.send_invitation(request)

        messages.success(request, f"Invitación enviada a {email}")
        return redirect("social:send_invite")

    return render(request, "social/send_invite.html")
