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


@register.filter
def posto_nome(militar):
    """Formata militar como '1º Sgt ALVES' (sigla do posto + nome_guerra em maiúsculas).
    Uso: {{ militar|posto_nome }}
    """
    if militar is None:
        return ''
    try:
        sigla = militar.posto.sigla if militar.posto else ''
        nome = militar.nome_guerra.upper() if militar.nome_guerra else ''
        if sigla and nome:
            return f'{sigla} {nome}'
        return nome or sigla
    except AttributeError:
        return str(militar)


@register.filter
def range_filter(value):
    """Retorna uma lista de 1 a N — ex: {{ 5|range }} retorna [1,2,3,4,5]"""
    try:
        return list(range(1, int(value) + 1))
    except (ValueError, TypeError):
        return []
