from django import template

register = template.Library()


@register.filter
def index(lista, i):
    """Retorna lista[i] — ex: {{ nomes_meses|index:escala.mes }}"""
    try:
        return lista[int(i)]
    except (IndexError, TypeError, ValueError):
        return ''


@register.filter
def get_item(dictionary, key):
    """Retorna o valor de uma chave em um dicionário — ex: {{ dict|get_item:key }}"""
    try:
        return dictionary.get(key, [])
    except (AttributeError, TypeError):
        return []
