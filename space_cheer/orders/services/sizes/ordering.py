"""El orden de las tallas, en un solo lugar.

`order_by("size")` devuelve L, M, S, XL, XS, XXL, que no es el orden de ninguna
etiqueta de ropa. Manda la escala del alumno; una talla fuera de ella (calzado
numerico, por ejemplo) va al final en vez de inventarle una posicion.
"""


def _escala():
    from measures.models import AthleteStandardSize

    return [code for code, _ in AthleteStandardSize.SIZE_CHOICES]


def size_sort_key(size):
    escala = _escala()
    posicion = {code: indice for indice, code in enumerate(escala)}
    return (posicion.get(size, len(escala)), size)


def order_by_size(queryset, campo="size"):
    """El mismo orden que `size_sort_key`, pero resuelto por la base de datos.

    Los consumidores que quedaban con `order_by("size")` ordenan querysets, y
    dos de ellos lo hacen dentro de un `Prefetch`: ahi no hay lista que
    reordenar en Python despues, la escala tiene que viajar como SQL.
    """
    from django.db.models import Case, IntegerField, Value, When

    escala = _escala()
    posicion = Case(
        *[
            When(**{campo: code, "then": Value(indice)})
            for indice, code in enumerate(escala)
        ],
        default=Value(len(escala)),
        output_field=IntegerField(),
    )
    # El segundo criterio es el desempate de `size_sort_key`: mantiene juntas y
    # estables las tallas que caen fuera de la escala (calzado numerico).
    return queryset.order_by(posicion, campo)
