import os
import re
import magic
from django.core.exceptions import ValidationError

# =============================================================================
# VALIDATORS DE ARCHIVOS (Magic Bytes)
# =============================================================================

def validate_audio_magic(file):
    """
    Valida que el archivo subido sea realmente un archivo de audio o contenedor media válido.
    """
    valid_mime_types = [
        'audio/mpeg', 'audio/wav', 'audio/mp4', 'audio/aac',
        'audio/x-m4a', 'video/mp4', 'audio/ogg'
    ]
    
    file_mime_type = magic.from_buffer(file.read(2048), mime=True)
    file.seek(0)
    
    if file_mime_type not in valid_mime_types:
        raise ValidationError(
            f'Archivo de audio no soportado ({file_mime_type}). Solo MP3, WAV, AAC o M4A.'
        )

def validate_image_magic(file):
    """
    Valida que el archivo subido sea realmente una imagen leyendo sus Magic Bytes.
    Evita que un archivo ejecutable renombrado a .jpg pase como foto real.
    """
    valid_mime_types = ['image/jpeg', 'image/png', 'image/webp']
    
    # Leemos los primeros 2048 bytes para determinar los magic bytes genuinos
    file_mime_type = magic.from_buffer(file.read(2048), mime=True)
    
    # Importante: Retornar el puntero del archivo a 0 para que no falle el guardado posterior
    file.seek(0)
    
    if file_mime_type not in valid_mime_types:
        raise ValidationError(
            f'Archivo no soportado ({file_mime_type}). Solo se permiten imágenes JPG, PNG y WEBP.'
        )

def validate_min_size_35mb(file):
    """
    Valida que el archivo subido pese al menos 35 MB.
    """
    thirty_five_mb = 35 * 1024 * 1024
    if file.size < thirty_five_mb:
        raise ValidationError(
            f'El diseño debe tener un tamaño mínimo de 35 MB para asegurar una alta resolución. '
            f'Archivo actual: {file.size / (1024 * 1024):.2f} MB.'
        )

# =============================================================================
# GENERADORES DE RUTAS DINÁMICAS (upload_to)
# =============================================================================

def _sanitize_path_component(value: str) -> str:
    """
    Elimina caracteres peligrosos de un componente de ruta de archivo.
    Previene path traversal (../) y caracteres especiales de sistema de archivos.
    """
    # Conservar solo alfanuméricos, guión y guión bajo
    return re.sub(r'[^a-zA-Z0-9_-]', '_', value)


def user_profile_photo_path(instance, filename):
    """
    Genera: media/accounts/perfiles/<username_sanitizado>/<filename>
    Sanitiza el username para prevenir path traversal.
    """
    safe_filename = os.path.basename(filename)
    safe_username = _sanitize_path_component(instance.username)
    return f'accounts/perfiles/{safe_username}/{safe_filename}'

def team_photo_path(instance, filename):
    """
    Genera: media/teams/fotos/<team_name_sanitizado>/<filename>
    """
    safe_filename = os.path.basename(filename)
    safe_team_name = _sanitize_path_component(instance.name.replace(" ", "_").lower())
    return f'teams/fotos/{safe_team_name}/{safe_filename}'

def team_song_path(instance, filename):
    """
    Genera: media/teams/songs/<team_name_sanitizado>/<filename>
    """
    safe_filename = os.path.basename(filename)
    safe_team_name = _sanitize_path_component(instance.team.name.replace(" ", "_").lower())
    return f'teams/songs/{safe_team_name}/{safe_filename}'

def product_image_path(instance, filename):
    """
    Genera: media/products/<sku>/<filename>
    """
    safe_filename = os.path.basename(filename)
    # Suponiendo que el producto tiene un SKU único
    return f'products/{instance.sku}/{safe_filename}'

def design_upload_path(instance, filename):
    """
    Genera: media/designs/<username>/<filename>
    """
    safe_filename = os.path.basename(filename)
    # Dependiendo de tu modelo de diseño, puede asignarse al usuario que lo subió o a una orden
    # Asumimos que instance tiene un campo user o team vinculado.
    if hasattr(instance, 'user'):
        folder = instance.user.username
    elif hasattr(instance, 'team'):
        folder = instance.team.name.replace(" ", "_").lower()
    else:
        folder = 'general'
    
    return f'designs/{folder}/{safe_filename}'
