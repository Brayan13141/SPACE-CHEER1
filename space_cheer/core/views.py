from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.decorators.cache import cache_page
from accounts.decorators import role_required
from teams.models import UserTeamMembership
from core.models import LandingSettings
from events.models import Event
from products.models import Product


def _landing_context():
    return {
        "landing_settings": LandingSettings.get_solo(),
        "featured_events": Event.objects.filter(featured_on_landing=True).order_by("landing_order", "start_date")[:6],
        "featured_products": Product.objects.filter(featured_on_landing=True, is_active=True).order_by("landing_order", "name")[:8],
    }


def home(request):
    if request.user.is_authenticated:
        memberships = UserTeamMembership.objects.select_related("team").filter(
            user=request.user, is_active=True, status="accepted"
        ).order_by("team__name")
        teams = [m.team for m in memberships]

        return render(request, "core/dashboard.html", {
            "user_teams": teams,
            "user_teams_count": len(teams),
        })

    return render(request, "core/home.html", _landing_context())


def landing(request):
    return render(request, "core/home.html", _landing_context())


@role_required("ADMIN")
def manage_landing(request):
    landing_settings = LandingSettings.get_solo()

    if request.method == "POST":
        form_type = request.POST.get("form_type")

        if form_type == "settings":
            for field in [
                "hero_badge", "hero_title", "hero_paragraph",
                "stat1_number", "stat1_label",
                "stat2_number", "stat2_label",
                "stat3_number", "stat3_label",
                "cta_title", "cta_paragraph",
            ]:
                if field in request.POST:
                    setattr(landing_settings, field, request.POST.get(field, ""))
            if request.FILES.get("hero_image"):
                landing_settings.hero_image = request.FILES["hero_image"]
            landing_settings.save()
            messages.success(request, "Configuración general de la landing actualizada.")

        elif form_type == "events":
            featured_ids = set(request.POST.getlist("featured_event_ids"))
            for event in Event.objects.all():
                should_feature = str(event.id) in featured_ids
                order_value = request.POST.get(f"landing_order_event_{event.id}")
                try:
                    order_value = int(order_value) if order_value is not None else event.landing_order
                except ValueError:
                    order_value = event.landing_order
                if event.featured_on_landing != should_feature or event.landing_order != order_value:
                    event.featured_on_landing = should_feature
                    event.landing_order = order_value
                    event.save(update_fields=["featured_on_landing", "landing_order"])
            messages.success(request, "Competencias destacadas actualizadas.")

        elif form_type == "products":
            featured_ids = set(request.POST.getlist("featured_product_ids"))
            for product in Product.objects.filter(is_active=True):
                should_feature = str(product.id) in featured_ids
                order_value = request.POST.get(f"landing_order_product_{product.id}")
                try:
                    order_value = int(order_value) if order_value is not None else product.landing_order
                except ValueError:
                    order_value = product.landing_order
                if product.featured_on_landing != should_feature or product.landing_order != order_value:
                    product.featured_on_landing = should_feature
                    product.landing_order = order_value
                    product.save(update_fields=["featured_on_landing", "landing_order"])
            messages.success(request, "Productos destacados actualizados.")

        return redirect("core:manage_landing")

    events = Event.objects.all().order_by("landing_order", "start_date")
    products = Product.objects.filter(is_active=True).order_by("landing_order", "name")

    return render(request, "core/manage_landing.html", {
        "landing_settings": landing_settings,
        "events": events,
        "products": products,
    })


@cache_page(60 * 60 * 24)
def contact(request):
    return render(request, "core/contact.html")


@cache_page(60 * 60 * 24)
def privacy(request):
    return render(request, "core/privacy.html")


@cache_page(60 * 60 * 24)
def terminos(request):
    return render(request, "core/terminos.html")


def user_teams_context(request):
    if not request.user.is_authenticated:
        return {}

    memberships = UserTeamMembership.objects.select_related("team").filter(
        user=request.user,
        is_active=True,
        status="accepted",
    ).order_by("team__name")

    teams = [m.team for m in memberships]

    is_headcoach = request.user.roles.filter(name="HEADCOACH").exists()
    is_admin = request.user.roles.filter(name="ADMIN").exists()

    return {
        "navbar_teams": teams,
        "user_teams_count": len(teams),
        "is_headcoach": is_headcoach,
        "is_admin": is_admin,
    }
