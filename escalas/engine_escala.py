"""
Motor de geração automática de escala por algoritmo de MATRIZ.

Estrutura da matriz:
  linhas  = militares, de baixo para cima (mais moderno → mais antigo)
             → índice 0 = mais moderno/junior (bottom)
  colunas = dias do mês, da esquerda para direita (dia 1 → último dia)

Valores possíveis por célula:
  date          → militar trabalhou naquele dia
  'indisponivel' → indisponível (não pode ser escalado)
  None           → disponível

Algoritmo por coluna (dia):
  1. Filtrar militares disponíveis (célula != 'indisponivel')
  2. Ordenar por:
       a) menor qtd de serviços já atribuídos no mês (ASC)
       b) maior tempo desde o último serviço, i.e., menor índice do último dia
          em que trabalhou (ASC)
       c) posição na matriz de baixo para cima, i.e., menor índice = mais
          moderno (ASC)
  3. Evitar dias consecutivos: se o melhor candidato trabalhou no dia anterior,
     tentar o próximo; só volta ao melhor se não houver alternativa.
  4. Alocar o escolhido e registrar a data na célula correspondente.
"""

from datetime import date as date_type
from typing import List, Optional, Tuple, Dict, Set


# ---------------------------------------------------------------------------
# Tipo de linha da matriz
# ---------------------------------------------------------------------------
CelulaMatriz = Optional[date_type]   # None | date | 'indisponivel'


def construir_matriz(
    lista_militares: list,
    lista_dias: list,
    indisponibilidades: Dict[int, Set[date_type]],
) -> List[List]:
    """
    Cria a matriz (lista de listas) e pré-preenche as células de
    indisponibilidade.

    Args:
        lista_militares : lista de objetos Militar (índice 0 = mais moderno)
        lista_dias      : lista de objetos CalendarioDia (índice 0 = 1º dia)
        indisponibilidades: {militar_id: {datas indisponíveis}}

    Returns:
        matrix[i][j] onde i = índice do militar, j = índice do dia
    """
    n_m = len(lista_militares)
    n_d = len(lista_dias)
    matrix: List[List] = [[None] * n_d for _ in range(n_m)]

    for i, militar in enumerate(lista_militares):
        datas_indisp = indisponibilidades.get(militar.id, set())
        for j, dia in enumerate(lista_dias):
            if dia.data in datas_indisp:
                matrix[i][j] = 'indisponivel'

    return matrix


def _contar_servicos_no_mes(matrix: List[List], i: int, ate_col: int) -> int:
    """Conta serviços atribuídos ao militar i nas colunas 0..ate_col-1."""
    return sum(
        1 for k in range(ate_col) if isinstance(matrix[i][k], date_type)
    )


def _ultimo_servico_col(matrix: List[List], i: int, ate_col: int) -> int:
    """
    Retorna o índice da última coluna em que o militar i trabalhou
    (antes da coluna atual). Retorna -9999 se nunca trabalhou
    (= prioridade máxima na segunda chave de ordenação).
    """
    ultimo = -9999
    for k in range(ate_col):
        if isinstance(matrix[i][k], date_type):
            ultimo = k
    return ultimo


def gerar_escala_matriz(
    lista_militares: list,
    lista_dias: list,
    indisponibilidades: Dict[int, Set[date_type]],
) -> List[Tuple]:
    """
    Executa o algoritmo de geração automática por matriz.

    Returns:
        Lista de tuplas (CalendarioDia, Militar | None) — uma por dia.
        Militar é None quando nenhum candidato está disponível no dia.
    """
    if not lista_militares or not lista_dias:
        return []

    n_m = len(lista_militares)
    matrix = construir_matriz(lista_militares, lista_dias, indisponibilidades)

    resultado: List[Tuple] = []

    for j, dia in enumerate(lista_dias):

        # --- Candidatos disponíveis neste dia ---
        candidatos = [
            i for i in range(n_m)
            if matrix[i][j] != 'indisponivel'
        ]

        if not candidatos:
            resultado.append((dia, None))
            continue

        # --- Ordenação conforme as regras ---
        # Convenção: menor ordem_hierarquica = mais antigo (topo da matriz)
        #            maior ordem_hierarquica = mais moderno (base da matriz)
        # A lista já está ordenada ASC por ordem_hierarquica:
        #   índice 0  = mais antigo  = TOPO
        #   índice -1 = mais moderno = BASE
        # Leitura de baixo para cima → desempate prefere índice MAIOR (base)
        candidatos.sort(key=lambda i: (
            _contar_servicos_no_mes(matrix, i, j),   # 1. menos serviços (ASC)
            _ultimo_servico_col(matrix, i, j),        # 2. mais tempo atrás (ASC)
            -i,                                       # 3. base→topo: índice maior primeiro
        ))

        # --- Evitar consecutivos (restrição suave) ---
        escolhido_idx = None
        if j > 0:
            # Preferir alguém que NÃO trabalhou no dia anterior
            for i in candidatos:
                if not isinstance(matrix[i][j - 1], date_type):
                    escolhido_idx = i
                    break
            # Se não há alternativa (ex: 1 militar só), usa o melhor ranqueado
            if escolhido_idx is None:
                escolhido_idx = candidatos[0]
        else:
            escolhido_idx = candidatos[0]

        # --- Registrar na matriz e no resultado ---
        matrix[escolhido_idx][j] = dia.data
        resultado.append((dia, lista_militares[escolhido_idx]))

    return resultado


def obter_indisponibilidades(militares: list, data_inicio, data_fim) -> Dict[int, Set[date_type]]:
    """
    Consulta o banco e retorna dicionário {militar_id: set(datas indisponíveis)}
    para o intervalo [data_inicio, data_fim].
    """
    from .models import Indisponibilidade
    from datetime import timedelta

    militar_ids = [m.id for m in militares]

    registros = Indisponibilidade.objects.filter(
        militar_id__in=militar_ids,
        tipo__exclui_do_sorteio=True,
        data_inicio__lte=data_fim,
        data_fim__gte=data_inicio,
    ).select_related('tipo').values_list('militar_id', 'data_inicio', 'data_fim')

    resultado: Dict[int, Set[date_type]] = {}

    for militar_id, ini, fim in registros:
        if militar_id not in resultado:
            resultado[militar_id] = set()
        # Expandir intervalo em datas individuais
        cursor = ini
        while cursor <= fim:
            if data_inicio <= cursor <= data_fim:
                resultado[militar_id].add(cursor)
            cursor += timedelta(days=1)

    return resultado


def resumo_matriz(
    lista_militares: list,
    lista_dias: list,
    resultado: List[Tuple],
) -> List[dict]:
    """
    Gera um resumo por militar: nome, total de serviços atribuídos,
    datas atribuídas — útil para exibir na tela após a geração.
    """
    contagem: Dict[int, dict] = {}
    for militar in lista_militares:
        contagem[militar.id] = {
            'militar': militar,
            'servicos': 0,
            'datas': [],
        }

    for dia, militar in resultado:
        if militar is not None:
            contagem[militar.id]['servicos'] += 1
            contagem[militar.id]['datas'].append(dia.data)

    return sorted(
        contagem.values(),
        key=lambda x: x['servicos'],
        reverse=True,
    )
