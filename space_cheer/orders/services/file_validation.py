"""
Validación robusta de archivos subidos.
Previene ataques mediante archivos maliciosos.
"""

from django.core.exceptions import ValidationError
from PIL import Image
from io import BytesIO
import magic  # python-magic


class FileValidator:
    """Validador de archivos subidos"""

    # Tipos MIME permitidos
    ALLOWED_IMAGE_TYPES = {
        "image/jpeg": ["jpg", "jpeg"],
        "image/png": ["png"],
        "image/webp": ["webp"],
    }

    MAX_IMAGE_SIZE_MB = 10
    MAX_IMAGE_DIMENSIONS = (5000, 5000)  # width, height

    @classmethod
    def validate_image(cls, uploaded_file):
        """
        Valida que un archivo subido sea una imagen real y segura.

        Args:
            uploaded_file: UploadedFile de Django

        Raises:
            ValidationError: Si la validación falla
        """
        # 1. Validar tamaño
        cls._validate_size(uploaded_file)

        # 2. Validar MIME type real (no confiar en header HTTP)
        cls._validate_mime_type(uploaded_file)

        # 3. Validar que sea imagen real con Pillow
        cls._validate_image_content(uploaded_file)

        # 4. Validar dimensiones
        cls._validate_dimensions(uploaded_file)

        return True

    @classmethod
    def _validate_size(cls, uploaded_file):
        """Valida el tamaño del archivo"""
        max_size_bytes = cls.MAX_IMAGE_SIZE_MB * 1024 * 1024

        if uploaded_file.size > max_size_bytes:
            raise ValidationError(
                f"El archivo es demasiado grande. "
                f"Máximo permitido: {cls.MAX_IMAGE_SIZE_MB} MB"
            )

    @classmethod
    def _validate_mime_type(cls, uploaded_file):
        """
        Valida el MIME type REAL del archivo usando libmagic.
        No confía en el content_type del header HTTP.
        """
        uploaded_file.seek(0)
        file_content = uploaded_file.read(2048)  # Leer primeros 2KB
        uploaded_file.seek(0)

        mime = magic.from_buffer(file_content, mime=True)

        if mime not in cls.ALLOWED_IMAGE_TYPES:
            raise ValidationError(
                f"Tipo de archivo no permitido. "
                f"Tipos válidos: JPG, PNG, WEBP. "
                f"Detectado: {mime}"
            )

    @classmethod
    def _validate_image_content(cls, uploaded_file):
        """
        Valida que el archivo sea una imagen REAL usando Pillow.
        Previene archivos .php disfrazados como .jpg
        """
        try:
            uploaded_file.seek(0)
            img = Image.open(BytesIO(uploaded_file.read()))
            img.verify()  # Verifica integridad
            uploaded_file.seek(0)

            # Validar formato
            if img.format.lower() not in ["jpeg", "png", "webp"]:
                raise ValidationError(f"Formato de imagen no válido: {img.format}")

        except Exception as e:
            raise ValidationError(f"El archivo no es una imagen válida: {str(e)}")

    @classmethod
    def _validate_dimensions(cls, uploaded_file):
        """Valida que las dimensiones sean razonables"""
        uploaded_file.seek(0)
        img = Image.open(uploaded_file)

        width, height = img.size
        max_width, max_height = cls.MAX_IMAGE_DIMENSIONS

        if width > max_width or height > max_height:
            raise ValidationError(
                f"Dimensiones de imagen exceden el límite. "
                f"Máximo: {max_width}x{max_height}px. "
                f"Actual: {width}x{height}px"
            )

        uploaded_file.seek(0)


class DesignImageValidator:
    """Validador específico para imágenes de diseño de órdenes"""

    @classmethod
    def validate(cls, uploaded_file, order):
        """
        Valida una imagen de diseño para una orden.

        Args:
            uploaded_file: Archivo subido
            order: Instancia de Order
        """
        # 1. Validaciones generales de imagen
        FileValidator.validate_image(uploaded_file)

        # 2. Validaciones específicas de diseño
        # (Podrías agregar reglas adicionales aquí)
        # Ej: validar que no exista ya un diseño final

        return True
