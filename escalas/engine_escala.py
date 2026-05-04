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
  5. Marcar células de folga do escolhido como 'indisponivel' na matriz
     (regra de folga mínima entre serviços).
"""

from datetime import date as date_type, timedelta
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


def _gerar_grupo(
    lista_militares: list,
    dias_grupo: list,
    dias_todos: list,
    matrix: List[List],
    n_m: int,
    janela_folga_dias: int = 0,
) -> List[Tuple]:
    """
    Gera atribuições para um grupo de dias (ex: só Pretos ou só Vermelhos).
    Usa a matrix compartilhada para registrar resultados, mas os contadores
    de serviço e "último serviço" são calculados apenas dentro do próprio grupo.

    Após cada atribuição, marca os dias de folga subsequentes como
    'indisponivel' na matrix (regra de folga mínima entre serviços).

    dias_grupo      : subconjunto de dias a processar nesta passagem
    dias_todos      : lista completa de dias do mês (para saber os índices na matrix)
    janela_folga_dias: duração_serviço_dias + folga_minima_dias; 0 = desativado
    """
    # Mapear data → índice de coluna na matrix completa
    col_por_data = {dia.data: j for j, dia in enumerate(dias_todos)}
    n_d = len(dias_todos)

    resultado: List[Tuple] = []

    # Contadores locais do grupo (para critérios 1 e 2)
    count_grupo = [0] * n_m           # qtd de serviços no grupo até agora
    ultimo_col_grupo = [-9999] * n_m  # índice da última col do grupo em que trabalhou

    for pos, dia in enumerate(dias_grupo):
        j = col_por_data[dia.data]  # coluna real na matrix

        # Candidatos disponíveis neste dia
        candidatos = [i for i in range(n_m) if matrix[i][j] != 'indisponivel']

        if not candidatos:
            resultado.append((dia, None))
            continue

        # Ordenação pelos critérios — usando acumuladores locais do grupo
        candidatos.sort(key=lambda i: (
            count_grupo[i],           # 1. menos serviços no grupo (ASC)
            ultimo_col_grupo[i],      # 2. mais tempo atrás no grupo (ASC, -9999 = nunca)
            -i,                       # 3. base→topo: índice maior primeiro
        ))

        # Evitar consecutivos dentro do grupo (restrição suave)
        escolhido_idx = None
        if pos > 0:
            dia_anterior = dias_grupo[pos - 1]
            j_ant = col_por_data[dia_anterior.data]
            for i in candidatos:
                if not isinstance(matrix[i][j_ant], date_type):
                    escolhido_idx = i
                    break
            if escolhido_idx is None:
                escolhido_idx = candidatos[0]
        else:
            escolhido_idx = candidatos[0]

        # Registrar na matrix e atualizar acumuladores do grupo
        matrix[escolhido_idx][j] = dia.data
        count_grupo[escolhido_idx] += 1
        ultimo_col_grupo[escolhido_idx] = j
        resultado.append((dia, lista_militares[escolhido_idx]))

        # ── Marcar folga mínima pós-serviço na matrix ──────────────────────
        # Bloqueia dias j+1 até j+janela_folga_dias para o militar escolhido,
        # desde que a célula ainda esteja livre (None).
        if janela_folga_dias > 0:
            for k in range(j + 1, min(j + janela_folga_dias + 1, n_d)):
                if matrix[escolhido_idx][k] is None:
                    matrix[escolhido_idx][k] = 'indisponivel'

    return resultado


def gerar_escala_matriz(
    lista_militares: list,
    lista_dias: list,
    indisponibilidades: Dict[int, Set[date_type]],
    config=None,
) -> List[Tuple]:
    """
    Executa o algoritmo de geração automática por matriz.

    Os dias são processados em dois grupos, na ordem:
      1. Dias "Pretos" (dias úteis comuns) — mês inteiro
      2. Demais dias (Vermelhos, Roxos, feriados) — mês inteiro

    Dentro de cada grupo, os critérios são:
      a) menos serviços acumulados no próprio grupo
      b) maior tempo desde o último serviço no grupo
      c) posição na matriz: base → topo (índice maior primeiro)

    Após cada atribuição, marca os dias de folga na matrix (regra de folga
    mínima entre serviços), afetando ambos os grupos.

    Args:
        config: instância de ConfiguracaoEscala (opcional). Se None, usa padrão 0 (sem folga).

    Returns:
        Lista de tuplas (CalendarioDia, Militar | None), na ordem cronológica
        original dos dias.
    """
    if not lista_militares or not lista_dias:
        return []

    n_m = len(lista_militares)
    matrix = construir_matriz(lista_militares, lista_dias, indisponibilidades)

    # Calcular janela de folga para marcar na matrix após cada serviço
    if config is not None:
        janela_folga_dias = config.duracao_servico_dias + config.folga_minima_dias
    else:
        janela_folga_dias = 0  # sem regra de folga (compatibilidade retroativa)

    # Separar dias por grupo
    def _e_preto(dia) -> bool:
        ts = dia.tipo_servico
        nome = (ts.nome or '').lower()
        cor = (ts.cor_hex or '').lower()
        return 'pret' in nome or cor in ('#1a1a1a', '#000000', '#111111')

    dias_pretos = [d for d in lista_dias if _e_preto(d)]
    dias_outros = [d for d in lista_dias if not _e_preto(d)]

    # Gerar grupo 1 (Pretos) depois grupo 2 (Vermelhos/Roxos)
    # A matrix é compartilhada: folgas marcadas no grupo 1 afetam o grupo 2
    res_pretos = _gerar_grupo(lista_militares, dias_pretos, lista_dias, matrix, n_m, janela_folga_dias)
    res_outros = _gerar_grupo(lista_militares, dias_outros, lista_dias, matrix, n_m, janela_folga_dias)

    # Recompor resultado em ordem cronológica
    mapa: dict = {}
    for dia, mil in res_pretos + res_outros:
        mapa[dia.data] = (dia, mil)

    return [mapa[dia.data] for dia in lista_dias if dia.data in mapa]


def obter_indisponibilidades(
    militares: list,
    data_inicio,
    data_fim,
    config=None,
) -> Dict[int, Set[date_type]]:
    """
    Consulta o banco e retorna dicionário {militar_id: set(datas indisponíveis)}
    para o intervalo [data_inicio, data_fim].

    Aplica (conforme ConfiguracaoEscala):
      1. Indisponibilidades diretas (férias, licença, etc.)
      2. Folga mínima entre serviços (baseada em EscalaItems do mês anterior)
      3. Bloqueio pré-férias: janela antes do início de uma indisponibilidade
      4. Bloqueio pós-férias: janela após o término de uma indisponibilidade

    Args:
        militares : lista de objetos Militar
        data_inicio, data_fim : intervalo do mês a gerar
        config    : ConfiguracaoEscala (opcional). Se None, busca do banco ou usa padrão.
    """
    from .models import Indisponibilidade, EscalaItem

    if not militares:
        return {}

    # Obter configuração se não fornecida
    if config is None:
        from .models import ConfiguracaoEscala
        om = militares[0].organizacao_militar
        config = ConfiguracaoEscala.obter_para_om(om)

    folga_min_dias = config.folga_minima_dias
    duracao_dias = config.duracao_servico_dias
    janela_total = duracao_dias + folga_min_dias  # dias bloqueados após início do serviço

    militar_ids = [m.id for m in militares]
    resultado: Dict[int, Set[date_type]] = {}

    # ── 1. Indisponibilidades diretas ───────────────────────────────────────
    # Busca com margem extra para capturar registros que afetam pré/pós bloqueio
    margem = timedelta(days=janela_total)
    registros = Indisponibilidade.objects.filter(
        militar_id__in=militar_ids,
        tipo__exclui_do_sorteio=True,
        data_inicio__lte=data_fim + margem,
        data_fim__gte=data_inicio - margem,
    ).values_list('militar_id', 'data_inicio', 'data_fim')

    for militar_id, ini, fim in registros:
        if militar_id not in resultado:
            resultado[militar_id] = set()

        # Datas da própria indisponibilidade dentro do range
        cursor = ini
        while cursor <= fim:
            if data_inicio <= cursor <= data_fim:
                resultado[militar_id].add(cursor)
            cursor += timedelta(days=1)

        # ── 2. Bloqueio pré-férias ──────────────────────────────────────────
        # Serviços nos últimos folga_min_dias antes da indisponibilidade
        # terminariam dentro da janela de folga que sobrepõe o início das férias.
        # Bloqueia: [ini - folga_min_dias, ini - 1]
        if config.bloquear_pre_ferias:
            bloquear_pre_inicio = ini - timedelta(days=folga_min_dias)
            bloquear_pre_fim = ini - timedelta(days=1)
            cursor = max(data_inicio, bloquear_pre_inicio)
            while cursor <= min(data_fim, bloquear_pre_fim):
                resultado[militar_id].add(cursor)
                cursor += timedelta(days=1)

        # ── 3. Bloqueio pós-férias ──────────────────────────────────────────
        # Após retorno (fim + 1), o militar precisa de folga_min_dias antes
        # de assumir novo serviço.
        # Bloqueia: [fim + 1, fim + folga_min_dias]
        if config.bloquear_pos_ferias:
            bloquear_pos_inicio = fim + timedelta(days=1)
            bloquear_pos_fim = fim + timedelta(days=folga_min_dias)
            cursor = max(data_inicio, bloquear_pos_inicio)
            while cursor <= min(data_fim, bloquear_pos_fim):
                resultado[militar_id].add(cursor)
                cursor += timedelta(days=1)

    # ── 4. Folga mínima pós-serviço (inter-mês) ────────────────────────────
    # Busca serviços de meses anteriores que ainda "bloqueiam" o início do mês.
    # Janela de lookback: janela_total dias antes de data_inicio.
    lookback = data_inicio - timedelta(days=janela_total)
    items_anteriores = EscalaItem.objects.filter(
        militar_id__in=militar_ids,
        calendario_dia__data__gte=lookback,
        calendario_dia__data__lt=data_inicio,
    ).values_list('militar_id', 'calendario_dia__data')

    for militar_id, data_servico in items_anteriores:
        if militar_id not in resultado:
            resultado[militar_id] = set()
        # Bloqueio: [data_servico + 1, data_servico + janela_total]
        bloquear_inicio = data_servico + timedelta(days=1)
        bloquear_fim_inter = data_servico + timedelta(days=janela_total)
        cursor = max(data_inicio, bloquear_inicio)
        while cursor <= min(data_fim, bloquear_fim_inter):
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
