"""El orden de las tallas, en un solo lugar.

`order_by("size")` devuelve L, M, S, XL, XS, XXL, que no es el orden de ninguna
etiqueta de ropa. Manda la escala del alumno; una talla fuera de ella (calzado
numerico, por ejemplo) va al final en vez de inventarle una posicion.
"""


def size_sort_key(size):
    from measures.models import AthleteStandardSize

    escala = [code for code, _ in AthleteStandardSize.SIZE_CHOICES]
    posicion = {code: indice for indice, code in enumerate(escala)}
    return (posicion.get(size, len(escala)), size)
