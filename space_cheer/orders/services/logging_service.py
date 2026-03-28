"""
Servicio centralizado de logging para el módulo de órdenes.
Proporciona logging consistente y estructurado.
"""

import logging
from typing import Optional, Dict, Any
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger("orders")


class OrderLogger:
    """Logger especializado para operaciones de órdenes"""

    @staticmethod
    def log_order_created(order, user: User):
        """Log cuando se crea una orden"""
        logger.info(
            f"Order created: #{order.id} | "
            f"Type: {order.order_type} | "
            f"By: {user.email}",
            extra={
                "order_id": order.id,
                "order_type": order.order_type,
                "user_id": user.id,
                "user_email": user.email,
                "action": "order_created",
            },
        )

    @staticmethod
    def log_transition_attempt(order, from_status: str, to_status: str, user: User):
        """Log intento de transición de estado"""
        logger.info(
            f"Transition attempt: Order #{order.id} | "
            f"{from_status} → {to_status} | "
            f"By: {user.email}",
            extra={
                "order_id": order.id,
                "from_status": from_status,
                "to_status": to_status,
                "user_id": user.id,
                "action": "transition_attempt",
            },
        )

    @staticmethod
    def log_transition_success(order, from_status: str, to_status: str, user: User):
        """Log transición exitosa"""
        logger.info(
            f"Transition success: Order #{order.id} | "
            f"{from_status} → {to_status} | "
            f"By: {user.email}",
            extra={
                "order_id": order.id,
                "from_status": from_status,
                "to_status": to_status,
                "user_id": user.id,
                "action": "transition_success",
            },
        )

    @staticmethod
    def log_transition_blocked(order, to_status: str, user: User, reason: str):
        """Log transición bloqueada"""
        logger.warning(
            f"Transition blocked: Order #{order.id} → {to_status} | "
            f"By: {user.email} | "
            f"Reason: {reason}",
            extra={
                "order_id": order.id,
                "to_status": to_status,
                "user_id": user.id,
                "reason": reason,
                "action": "transition_blocked",
            },
        )

    @staticmethod
    def log_permission_denied(order, user: User, action: str):
        """Log denegación de permiso"""
        logger.warning(
            f"Permission denied: Order #{order.id} | "
            f"Action: {action} | "
            f"User: {user.email}",
            extra={
                "order_id": order.id,
                "user_id": user.id,
                "action": action,
                "event": "permission_denied",
            },
        )

    @staticmethod
    def log_measurements_closed(order, user: Optional[User] = None):
        """Log cierre de medidas"""
        user_info = f"By: {user.email}" if user else "Auto-closed"

        logger.info(
            f"Measurements closed: Order #{order.id} | {user_info}",
            extra={
                "order_id": order.id,
                "user_id": user.id if user else None,
                "action": "measurements_closed",
            },
        )

    @staticmethod
    def log_measurements_locked(order, user: Optional[User] = None):
        """Log bloqueo definitivo de medidas"""
        user_info = f"By: {user.email}" if user else "System"

        logger.info(
            f"Measurements locked: Order #{order.id} | {user_info}",
            extra={
                "order_id": order.id,
                "user_id": user.id if user else None,
                "action": "measurements_locked",
            },
        )

    @staticmethod
    def log_design_uploaded(order, user: User, is_final: bool):
        """Log subida de diseño"""
        design_type = "FINAL" if is_final else "Draft"

        logger.info(
            f"Design uploaded: Order #{order.id} | "
            f"Type: {design_type} | "
            f"By: {user.email}",
            extra={
                "order_id": order.id,
                "user_id": user.id,
                "is_final": is_final,
                "action": "design_uploaded",
            },
        )

    @staticmethod
    def log_error(message: str, extra: Optional[Dict[str, Any]] = None):
        """Log error general"""
        logger.error(message, extra=extra or {})

    @staticmethod
    def log_exception(
        message: str, exc_info=True, extra: Optional[Dict[str, Any]] = None
    ):
        """Log excepción con traceback"""
        logger.exception(message, exc_info=exc_info, extra=extra or {})


class MeasurementLogger:
    """Logger para operaciones de medidas"""

    @staticmethod
    def log_measurement_saved(athlete_item, field_name: str, user: User):
        """Log guardado de medida"""
        logger.info(
            f"Measurement saved: Order #{athlete_item.order_item.order.id} | "
            f"Athlete: {athlete_item.athlete.email} | "
            f"Field: {field_name} | "
            f"By: {user.email}",
            extra={
                "order_id": athlete_item.order_item.order.id,
                "athlete_id": athlete_item.athlete.id,
                "field": field_name,
                "user_id": user.id,
                "action": "measurement_saved",
            },
        )

    @staticmethod
    def log_measurements_populated(order_item, athlete, user: User):
        """Log población de medidas desde perfil"""
        logger.info(
            f"Measurements populated: Order #{order_item.order.id} | "
            f"Product: {order_item.product.name} | "
            f"Athlete: {athlete.email} | "
            f"By: {user.email}",
            extra={
                "order_id": order_item.order.id,
                "product_id": order_item.product.id,
                "athlete_id": athlete.id,
                "user_id": user.id,
                "action": "measurements_populated",
            },
        )
