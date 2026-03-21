# orders/management/commands/close_expired_measurements.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.db.models import F
from orders.models import Order, OrderLog
from orders.services.measurements.MeasurementLifecycleService import (
    MeasurementLifecycleService,
)
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Cierra automáticamente las medidas vencidas"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula sin modificar datos",
        )

        parser.add_argument(
            "--order-id",
            type=int,
            help="Procesar solo esta orden",
        )

        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Output detallado",
        )

        parser.add_argument(
            "--days-overdue",
            type=int,
            default=0,
            help="Solo cerrar órdenes vencidas por N días o más (default: 0)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        order_id = options.get("order_id")
        verbose = options["verbose"]
        days_overdue = options["days_overdue"]

        today = timezone.now().date()
        cutoff_date = today - timezone.timedelta(days=days_overdue)

        # Header
        self.stdout.write("=" * 70)
        self.stdout.write(
            self.style.HTTP_INFO("🔄 CIERRE AUTOMÁTICO DE MEDIDAS VENCIDAS")
        )
        self.stdout.write("=" * 70)

        if dry_run:
            self.stdout.write(
                self.style.WARNING("\n🔍 MODO DRY-RUN - No se modificarán datos\n")
            )

        # Build query
        qs = (
            Order.objects.filter(
                measurements_open=True,
                measurements_locked=False,
                measurements_due_date__isnull=False,
                measurements_due_date__lte=cutoff_date,
            )
            .select_related("owner_user", "owner_team")
            .only(
                "id",
                "measurements_open",
                "measurements_locked",
                "measurements_due_date",
                "owner_user__email",
                "owner_team__name",
            )
        )

        if order_id:
            qs = qs.filter(id=order_id)

        orders = list(qs)  # Evaluar query UNA vez
        total = len(orders)

        # Stats
        self.stdout.write(f"\n📊 Fecha de corte: {cutoff_date}")
        self.stdout.write(f"📊 Órdenes encontradas: {total}\n")

        if not total:
            self.stdout.write(self.style.SUCCESS("✅ No hay medidas para cerrar\n"))
            return

        # Process orders
        results = {"closed": 0, "failed": 0, "skipped": 0, "errors": []}

        for idx, order in enumerate(orders, 1):
            prefix = f"[{idx}/{total}]"

            try:
                # Info básica
                owner_info = (
                    order.owner_team.name
                    if order.owner_team
                    else order.owner_user.email if order.owner_user else "Sin dueño"
                )

                if verbose:
                    self.stdout.write(
                        f"{prefix} Procesando orden #{order.id} "
                        f"({owner_info}) - Vencida: {order.measurements_due_date}"
                    )

                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            f"{prefix} [DRY-RUN] Cerraría orden #{order.id}"
                        )
                    )
                    results["closed"] += 1
                else:
                    # ✅ Transacción atómica por orden
                    with transaction.atomic():
                        # Re-fetch con lock dentro de transacción
                        locked_order = Order.objects.select_for_update(nowait=True).get(
                            id=order.id
                        )

                        # Verificar de nuevo (doble check)
                        if not locked_order.measurements_open:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"{prefix} ⚠️  Orden #{order.id} ya cerrada (race condition)"
                                )
                            )
                            results["skipped"] += 1
                            continue

                        # Cerrar medidas
                        MeasurementLifecycleService.auto_close_if_due(locked_order)

                        # Log de auditoría
                        OrderLog.objects.create(
                            order=locked_order,
                            user=None,  # Sistema
                            action="MEASUREMENTS_AUTO_CLOSED",
                            from_status=locked_order.status,
                            to_status=locked_order.status,
                            notes=f"Cerrado automáticamente por vencimiento ({order.measurements_due_date})",
                            metadata={
                                "command": "close_expired_measurements",
                                "due_date": str(order.measurements_due_date),
                                "closed_on": str(today),
                            },
                        )

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"{prefix} ✅ Orden #{order.id} cerrada correctamente"
                        )
                    )
                    results["closed"] += 1

            except Order.DoesNotExist:
                msg = f"{prefix} ⚠️  Orden #{order.id} eliminada durante procesamiento"
                self.stdout.write(self.style.WARNING(msg))
                results["skipped"] += 1

            except Exception as e:
                error_msg = f"{prefix} ❌ Error en orden #{order.id}: {str(e)}"
                self.stdout.write(self.style.ERROR(error_msg))

                results["failed"] += 1
                results["errors"].append(
                    {
                        "order_id": order.id,
                        "error": str(e),
                        "due_date": str(order.measurements_due_date),
                    }
                )

                logger.exception(f"Error procesando orden {order.id}")

        # Summary
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.HTTP_INFO("📈 RESUMEN DE EJECUCIÓN"))
        self.stdout.write("=" * 70)

        self.stdout.write(f"✅ Cerradas exitosamente: {results['closed']}")
        self.stdout.write(f"⚠️  Omitidas: {results['skipped']}")
        self.stdout.write(f"❌ Fallidas: {results['failed']}")

        if results["errors"]:
            self.stdout.write("\n⚠️  ERRORES DETALLADOS:")
            for error in results["errors"]:
                self.stdout.write(f"  - Orden #{error['order_id']}: {error['error']}")

        self.stdout.write("=" * 70 + "\n")

        # Exit code
        if results["failed"] > 0:
            self.stdout.write(
                self.style.ERROR(f"⚠️  Completado con {results['failed']} errores")
            )
        else:
            self.stdout.write(self.style.SUCCESS("✅ Completado exitosamente"))
