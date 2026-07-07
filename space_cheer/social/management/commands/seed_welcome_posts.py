"""
Publicaciones de bienvenida para que el Feed nunca se vea vacío la primera
vez que alguien entra al Portal Social. Se publican con un usuario ADMIN
(visibilidad PLATFORM por defecto), así que las ve cualquier usuario nuevo
sin equipo ni conexiones todavía.

Uso:
    python manage.py seed_welcome_posts
    python manage.py seed_welcome_posts --dry-run

Idempotente: no duplica publicaciones si ya existen (compara por texto).
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

User = get_user_model()

WELCOME_POSTS = [
    "¡Bienvenidos al Portal Social de Space Cheer! 🎉 Aquí pueden compartir "
    "fotos y videos de sus rutinas, entrenamientos y logros con toda la "
    "comunidad. ¡Anímense a publicar el primero!",
    "¿Sabían que pueden reaccionar a las publicaciones con 👏 🔥 ⭐ ❤️ 💪? "
    "Prueben la reacción que más represente cómo se sienten con cada rutina.",
    "El Ranking de Equipos se actualiza con competencias aceptadas, atletas "
    "activos y publicaciones del equipo 🏆 Échenle un vistazo y compitan "
    "por el primer lugar.",
]


class Command(BaseCommand):
    help = "Crea publicaciones de bienvenida (PLATFORM) para que el feed nunca esté vacío"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", help="Mostrar cambios sin ejecutarlos"
        )

    def handle(self, *args, **options):
        from social.models import Post

        dry_run = options["dry_run"]

        author = (
            User.objects.filter(roles__name="ADMIN", is_active=True)
            .order_by("id")
            .first()
        )
        if author is None:
            author = User.objects.filter(
                is_superuser=True, is_active=True
            ).order_by("id").first()
        if author is None:
            raise CommandError(
                "No hay ningún usuario ADMIN o superuser activo para autor de "
                "las publicaciones de bienvenida. Corre seed_roles y crea un "
                "ADMIN primero."
            )

        created_count = 0
        for text in WELCOME_POSTS:
            if Post.objects.filter(author=author, text=text).exists():
                self.stdout.write(f"  Ya existe: {text[:40]}...")
                continue
            created_count += 1
            self.stdout.write(f"  Creando: {text[:40]}...")
            if not dry_run:
                Post.objects.create(author=author, text=text)

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no se guardó nada"))
        self.stdout.write(
            self.style.SUCCESS(
                f"seed_welcome_posts completado ({created_count} nuevas, autor: {author.username})."
            )
        )
