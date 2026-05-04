from django import template

register = template.Library()


@register.filter
def index(lista, i):
    """Retorna lista[i] — ex: {{ nomes_meses|index:escala.mes }}"""
    try:
        return lista[int(i)]
    except (IndexError, TypeError, ValueError):
        return ''
