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

Algoritmo por coluna (dia), processados em ORDEM CRONOLÓGICA:
  1. Filtrar militares disponíveis (célula != 'indisponivel')
  2. Ordenar por:
       a) menor qtd de serviços totais já atribuídos no mês (ASC) — contador único
       b) maior tempo desde o último serviço (ASC, -9999 = nunca)
       c) posição na matriz de baixo para cima (índice maior = mais antigo = prioridade)
  3. Evitar dias consecutivos: se o melhor candidato trabalhou no dia anterior,
     tentar o próximo; só volta ao melhor se não houver alternativa.
  4. Alocar o escolhido e registrar a data na célula correspondente.
  5. Marcar células de folga pós-serviço como 'indisponivel' na matrix.
     Regra: serviço no dia D, duração S dias → folga de F dias após saída.
     Bloqueado: D+1 .. D+S+F  (inclusive ambos os extremos).
     Pode servir novamente: D+S+F+1.

Exemplo com duração=1 dia e folga=2 dias:
  Entra dia 02, sai dia 03 → bloqueado 03, 04 → pode servir em 05? Não.
  Saiu dia 03 (09h) + 48h = dia 05 (09h) ainda em folga → LIVRE dia 06.
  Portanto bloqueados: 03, 04, 05 → pode servir em 06.
  janela = duracao_servico_dias + folga_minima_dias = 1 + 2 = 3
  Bloqueados: j+1 .. j+3 (3 células após o serviço).
"""

from datetime import date as date_type, timedelta
from typing import List, Optional, Tuple, Dict, Set


# ---------------------------------------------------------------------------
# Tipo de célula da matriz
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


def gerar_escala_matriz(
    lista_militares: list,
    lista_dias: list,
    indisponibilidades: Dict[int, Set[date_type]],
    config=None,
) -> List[Tuple]:
    """
    Executa o algoritmo de geração automática por matriz.

    Todos os dias são processados em ORDEM CRONOLÓGICA (não por tipo).
    O balanceamento usa um CONTADOR ÚNICO por militar (Preto + Vermelho juntos).

    A janela de bloqueio pós-serviço é:
        janela = duracao_servico_dias + folga_minima_dias
        Bloqueados: j+1 .. j+janela  (inclusive)
        Próximo serviço possível: j + janela + 1

    Args:
        config: instância de ConfiguracaoEscala (opcional). Se None, sem folga.

    Returns:
        Lista de tuplas (CalendarioDia, Militar | None), ordem cronológica.
    """
    if not lista_militares or not lista_dias:
        return []

    n_m = len(lista_militares)
    n_d = len(lista_dias)
    matrix = construir_matriz(lista_militares, lista_dias, indisponibilidades)

    # Janela de bloqueio pós-serviço
    # duracao=1, folga=2 → janela=3 → bloqueia j+1, j+2, j+3 → livre em j+4
    if config is not None:
        janela_folga_dias = config.duracao_servico_dias + config.folga_minima_dias
    else:
        janela_folga_dias = 0

    # Mapear data → índice de coluna
    col_por_data = {dia.data: j for j, dia in enumerate(lista_dias)}

    # Contadores globais por militar (únicos, independem do tipo do dia)
    count_total = [0] * n_m          # total de serviços atribuídos no mês
    ultimo_col = [-9999] * n_m       # índice da última coluna em que trabalhou

    resultado: List[Tuple] = []

    for j, dia in enumerate(lista_dias):
        # Candidatos disponíveis neste dia
        candidatos = [i for i in range(n_m) if matrix[i][j] != 'indisponivel']

        if not candidatos:
            resultado.append((dia, None))
            continue

        # Ordenação pelos critérios usando contadores globais
        candidatos.sort(key=lambda i: (
            count_total[i],    # 1. menos serviços totais no mês (ASC)
            ultimo_col[i],     # 2. maior tempo desde último serviço (ASC, -9999=nunca)
            -i,                # 3. base→topo: índice maior = mais antigo = prioridade
        ))

        # Evitar dias consecutivos (restrição suave)
        escolhido_idx = None
        dia_anterior_data = dia.data - timedelta(days=1)
        if dia_anterior_data in col_por_data:
            j_ant = col_por_data[dia_anterior_data]
            for i in candidatos:
                if not isinstance(matrix[i][j_ant], date_type):
                    escolhido_idx = i
                    break
        if escolhido_idx is None:
            escolhido_idx = candidatos[0]

        # Registrar na matrix e atualizar contadores globais
        matrix[escolhido_idx][j] = dia.data
        count_total[escolhido_idx] += 1
        ultimo_col[escolhido_idx] = j
        resultado.append((dia, lista_militares[escolhido_idx]))

        # ── Marcar folga mínima pós-serviço ────────────────────────────────
        # Bloqueia j+1 .. j+janela_folga_dias (inclusive).
        # Sobrescreve None; células já marcadas (indisponivel ou data) ficam.
        if janela_folga_dias > 0:
            for k in range(j + 1, min(j + janela_folga_dias + 1, n_d)):
                if matrix[escolhido_idx][k] is None:
                    matrix[escolhido_idx][k] = 'indisponivel'

    return resultado


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
      2. Bloqueio pré-férias: janela antes do início de uma indisponibilidade
      3. Bloqueio pós-férias: janela após o término de uma indisponibilidade
      4. Folga mínima pós-serviço inter-mês (serviços do mês anterior)

    Regras de bloqueio pós-serviço DENTRO do mês são tratadas pela matrix
    em gerar_escala_matriz (processamento cronológico em tempo real).

    Args:
        militares   : lista de objetos Militar
        data_inicio : primeiro dia do mês a gerar
        data_fim    : último dia do mês a gerar
        config      : ConfiguracaoEscala (opcional)
    """
    from .models import Indisponibilidade, EscalaItem

    if not militares:
        return {}

    if config is None:
        from .models import ConfiguracaoEscala
        om = militares[0].organizacao_militar
        config = ConfiguracaoEscala.obter_para_om(om)

    folga_min_dias = config.folga_minima_dias
    duracao_dias = config.duracao_servico_dias
    # Janela total: dias bloqueados APÓS o dia do serviço
    # (igual à janela usada na matrix)
    janela_total = duracao_dias + folga_min_dias

    militar_ids = [m.id for m in militares]
    resultado: Dict[int, Set[date_type]] = {}

    # ── 1+2+3. Indisponibilidades diretas + bloqueios pré/pós ──────────────
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

        # ── Bloqueio pré-férias ─────────────────────────────────────────────
        # Um serviço nos folga_min_dias antes do início das férias causaria
        # violação da folga mínima. Bloqueia: [ini - folga_min_dias, ini - 1]
        if config.bloquear_pre_ferias:
            pre_inicio = ini - timedelta(days=folga_min_dias)
            pre_fim = ini - timedelta(days=1)
            cursor = max(data_inicio, pre_inicio)
            while cursor <= min(data_fim, pre_fim):
                resultado[militar_id].add(cursor)
                cursor += timedelta(days=1)

        # ── Bloqueio pós-férias ─────────────────────────────────────────────
        # Após retorno (fim+1), o militar ainda precisa de folga_min_dias.
        # Bloqueia: [fim + 1, fim + folga_min_dias]
        if config.bloquear_pos_ferias:
            pos_inicio = fim + timedelta(days=1)
            pos_fim = fim + timedelta(days=folga_min_dias)
            cursor = max(data_inicio, pos_inicio)
            while cursor <= min(data_fim, pos_fim):
                resultado[militar_id].add(cursor)
                cursor += timedelta(days=1)

    # ── 4. Folga mínima pós-serviço inter-mês ──────────────────────────────
    # Serviços no final do mês anterior que ainda bloqueiam o início deste mês.
    # Busca janela_total dias antes de data_inicio.
    lookback = data_inicio - timedelta(days=janela_total)
    items_anteriores = EscalaItem.objects.filter(
        militar_id__in=militar_ids,
        calendario_dia__data__gte=lookback,
        calendario_dia__data__lt=data_inicio,
    ).values_list('militar_id', 'calendario_dia__data')

    for militar_id, data_servico in items_anteriores:
        if militar_id not in resultado:
            resultado[militar_id] = set()
        # Bloqueado: data_servico+1 .. data_servico+janela_total
        bloquear_inicio = data_servico + timedelta(days=1)
        bloquear_fim = data_servico + timedelta(days=janela_total)
        cursor = max(data_inicio, bloquear_inicio)
        while cursor <= min(data_fim, bloquear_fim):
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
