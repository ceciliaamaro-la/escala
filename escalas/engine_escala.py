"""
Motor de geração automática de escala — Algoritmo de Ponteiro por Coluna.

╔══════════════════════════════════════════════════════════════════════╗
║  LÓGICA DA MATRIZ                                                    ║
║                                                                      ║
║  Linhas  = militares, do mais moderno (índice 0, BASE) ao           ║
║            mais antigo (índice n-1, TOPO)                            ║
║                                                                      ║
║  Colunas = rodadas de serviço. Na coluna k cada militar recebe       ║
║            seu (k+1)-ésimo serviço.                                  ║
║                                                                      ║
║  Leitura: BASE → TOPO dentro de cada coluna, depois avança          ║
║           para a próxima coluna à direita e reinicia da BASE.        ║
║                                                                      ║
║  Regra de folga:                                                     ║
║    • Cada serviço dura 24h (configurável). Após encerrar, o          ║
║      militar cumpre folga mínima antes do próximo serviço.           ║
║    • A folga é contada dentro do MESMO tipo de escala               ║
║      (Permanência não bloqueia Sobreaviso e vice-versa).             ║
║    • Cada TipoEscala pode ter sua própria folga_minima_horas;        ║
║      se vazio, usa a configuração global da OM.                      ║
║    • Fallback: quando todos estão em folga obrigatória,              ║
║      escala o que tem menos tempo de folga faltando.                 ║
╚══════════════════════════════════════════════════════════════════════╝
"""

from datetime import date as date_type, timedelta
from typing import Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Algoritmo principal: ponteiro por coluna
# ---------------------------------------------------------------------------

def gerar_escala_ponteiro(
    lista_militares: list,
    lista_dias: list,
    indisponibilidades: Dict[int, Set[date_type]],
    quadrinhos_inicio: Dict[int, int],
    ultimo_militar_id: Optional[int] = None,
    config=None,
    tipo_escala=None,
) -> Tuple[List[Tuple], Optional[int]]:
    """
    Gera a escala para UMA sequência de dias (todos do mesmo tipo de serviço)
    usando o algoritmo de ponteiro BASE→TOPO, coluna por coluna.

    Args:
        lista_militares  : militares ordenados [mais_moderno … mais_antigo].
                           Índice 0 = base (mais moderno/junior).
        lista_dias       : CalendarioDia a preencher, ordem cronológica.
                           Devem ser todos do mesmo TipoServico.
        indisponibilidades: {militar_id: set(datas bloqueadas)}.
                           Já inclui carryover do mês anterior FILTRADO
                           pelo mesmo tipo de escala.
        quadrinhos_inicio: {militar_id: n_servicos} — contagem ANTES deste mês.
        ultimo_militar_id: pk do último militar escalado no mês anterior
                           para este tipo de serviço (None = início do sistema).
        config           : ConfiguracaoEscala (folga global da OM).
        tipo_escala      : TipoEscala (pode ter folga_minima_horas específica).

    Returns:
        (resultado, novo_ultimo_militar_id)
        resultado = [(CalendarioDia, Militar|None), …]
    """
    if not lista_militares or not lista_dias:
        return [], ultimo_militar_id

    n = len(lista_militares)

    # Cópia local dos contadores (serão incrementados conforme atribuição)
    counts = {m.id: quadrinhos_inicio.get(m.id, 0) for m in lista_militares}

    # Índice → militar (base=0, topo=n-1)
    idx_por_id = {m.id: i for i, m in enumerate(lista_militares)}

    # ── Determinar janela de folga ───────────────────────────────────────────
    # Prioridade: folga específica do TipoEscala > global da OM > padrão 2 dias
    duracao_dias = 1  # padrão: 24h = 1 dia
    folga_dias   = 2  # padrão: 48h = 2 dias

    if config is not None:
        duracao_dias = config.duracao_servico_dias
        folga_dias   = config.folga_minima_dias

    if tipo_escala is not None and tipo_escala.folga_minima_horas is not None:
        folga_dias = max(1, tipo_escala.folga_minima_horas // 24)

    # janela_bloqueio: quantos dias após o início do serviço o militar fica impedido
    # serviço começa no dia D → fica bloqueado em D+1 … D+(duracao_dias+folga_dias)
    janela_bloqueio = duracao_dias + folga_dias

    # ── Determinar ponteiro de início ───────────────────────────────────────
    min_count = min(counts.values())

    if ultimo_militar_id and ultimo_militar_id in idx_por_id:
        ultimo_idx  = idx_por_id[ultimo_militar_id]
        proximo_idx = ultimo_idx + 1
        if proximo_idx >= n:
            proximo_idx = 0
        start_idx = proximo_idx
        start_col = min_count
    else:
        start_col = min_count
        start_idx = next(
            (i for i, m in enumerate(lista_militares) if counts[m.id] == min_count),
            0,
        )

    # ── Folga intra-mês: datas bloqueadas pelos serviços gerados NESTE mês ──
    # {militar_id: set(datas bloqueadas pela folga gerada aqui)}
    folga_intra: Dict[int, Set[date_type]] = {m.id: set() for m in lista_militares}

    # ── Processamento cronológico ────────────────────────────────────────────
    resultado: List[Tuple] = []
    ultimo_atribuido_id: Optional[int] = ultimo_militar_id

    idx = start_idx
    col = start_col

    for dia in lista_dias:
        data = dia.data
        atribuido = None

        # ── Tenta encontrar militar disponível na ordem ponteiro ─────────────
        tentativas = 0
        pos = idx
        coluna = col

        while tentativas < n * 3:
            if pos >= n:
                pos    = 0
                coluna += 1

            militar = lista_militares[pos]
            mil_count = counts[militar.id]

            if mil_count == coluna:
                bloqueado_indisp = data in indisponibilidades.get(militar.id, set())
                bloqueado_folga  = data in folga_intra.get(militar.id, set())
                if not bloqueado_indisp and not bloqueado_folga:
                    atribuido = militar
                    break

            pos        += 1
            tentativas += 1

        # ── Fallback: todos em folga → escala o com menos folga restante ─────
        if atribuido is None:
            candidatos_fallback = []
            for m in lista_militares:
                if data in indisponibilidades.get(m.id, set()):
                    continue  # indisponibilidade real (férias/afastamento) — não viola
                if data in folga_intra.get(m.id, set()):
                    # calcula quanto tempo de folga ainda falta (menor = preferido)
                    bloqueado_ate = max(
                        (d for d in folga_intra[m.id] if d >= data),
                        default=data,
                    )
                    dias_faltando = (bloqueado_ate - data).days
                    candidatos_fallback.append((dias_faltando, idx_por_id[m.id], m))
            if candidatos_fallback:
                candidatos_fallback.sort()
                atribuido = candidatos_fallback[0][2]

        # ── Registra resultado ───────────────────────────────────────────────
        if atribuido:
            counts[atribuido.id] += 1
            ultimo_atribuido_id = atribuido.id

            # Avança ponteiro
            pos_atribuido = idx_por_id[atribuido.id]
            idx = pos_atribuido + 1
            col = counts[atribuido.id] - 1  # coluna que acabou de completar

            # Marca folga intra-mês
            if janela_bloqueio > 0:
                dias_lista_datas = {d.data for d in lista_dias}
                for k in range(1, janela_bloqueio + 1):
                    data_bloqueada = data + timedelta(days=k)
                    if data_bloqueada in dias_lista_datas:
                        folga_intra[atribuido.id].add(data_bloqueada)

        resultado.append((dia, atribuido))

    return resultado, ultimo_atribuido_id


# ---------------------------------------------------------------------------
# Indisponibilidades + carryover inter-mês (filtrado por tipo_escala)
# ---------------------------------------------------------------------------

def obter_indisponibilidades(
    militares: list,
    data_inicio,
    data_fim,
    config=None,
    tipo_escala=None,
) -> Dict[int, Set[date_type]]:
    """
    Retorna {militar_id: set(datas bloqueadas)} para o intervalo [data_inicio, data_fim].

    Aplica:
      1. Indisponibilidades diretas (férias, licença, etc.) — bloqueiam em QUALQUER escala.
      2. Bloqueio pré/pós-indisponibilidade (configurável).
      3. Folga mínima pós-serviço carryover do mês anterior — filtrado pelo
         MESMO tipo_escala, pois cada tipo tem fila independente.

    Args:
        tipo_escala: TipoEscala — se fornecido, o carryover só considera serviços
                     desta mesma escala. Se None, considera todos (legado).
    """
    from .models import EscalaItem, Indisponibilidade

    if not militares:
        return {}

    if config is None:
        from .models import ConfiguracaoEscala
        om = militares[0].organizacao_militar
        config = ConfiguracaoEscala.obter_para_om(om)

    duracao_dias = config.duracao_servico_dias

    # Folga efetiva: usa override do tipo de escala se existir
    if tipo_escala is not None and tipo_escala.folga_minima_horas is not None:
        folga_min_dias = max(1, tipo_escala.folga_minima_horas // 24)
    else:
        folga_min_dias = config.folga_minima_dias

    janela_total = duracao_dias + folga_min_dias

    militar_ids = [m.id for m in militares]
    resultado: Dict[int, Set[date_type]] = {}
    margem = timedelta(days=janela_total)

    # ── 1. Indisponibilidades diretas ────────────────────────────────────────
    registros = Indisponibilidade.objects.filter(
        militar_id__in=militar_ids,
        tipo__exclui_do_sorteio=True,
        data_inicio__lte=data_fim + margem,
        data_fim__gte=data_inicio - margem,
    ).values_list('militar_id', 'data_inicio', 'data_fim')

    for militar_id, ini, fim in registros:
        if militar_id not in resultado:
            resultado[militar_id] = set()

        cursor = ini
        while cursor <= fim:
            if data_inicio <= cursor <= data_fim:
                resultado[militar_id].add(cursor)
            cursor += timedelta(days=1)

        if config.bloquear_pre_ferias:
            pre_inicio = ini - timedelta(days=folga_min_dias)
            pre_fim    = ini - timedelta(days=1)
            cursor = max(data_inicio, pre_inicio)
            while cursor <= min(data_fim, pre_fim):
                resultado[militar_id].add(cursor)
                cursor += timedelta(days=1)

        if config.bloquear_pos_ferias:
            pos_inicio = fim + timedelta(days=1)
            pos_fim    = fim + timedelta(days=folga_min_dias)
            cursor = max(data_inicio, pos_inicio)
            while cursor <= min(data_fim, pos_fim):
                resultado[militar_id].add(cursor)
                cursor += timedelta(days=1)

    # ── 2. Carryover inter-mês: serviços anteriores que ainda bloqueiam ──────
    # IMPORTANTE: filtrado pelo mesmo tipo_escala para que Preto não bloqueie
    # Vermelho e vice-versa.
    lookback = data_inicio - timedelta(days=janela_total)
    qs_anteriores = EscalaItem.objects.filter(
        militar_id__in=militar_ids,
        calendario_dia__data__gte=lookback,
        calendario_dia__data__lt=data_inicio,
        forcar_escala=False,  # serviços forçados não geram folga
    )

    if tipo_escala is not None:
        qs_anteriores = qs_anteriores.filter(
            escala__tipo_escala=tipo_escala,
        )

    items_anteriores = qs_anteriores.values_list(
        'militar_id', 'calendario_dia__data'
    )

    for militar_id, data_servico in items_anteriores:
        if militar_id not in resultado:
            resultado[militar_id] = set()
        bloquear_inicio = data_servico + timedelta(days=1)
        bloquear_fim    = data_servico + timedelta(days=janela_total)
        cursor = max(data_inicio, bloquear_inicio)
        while cursor <= min(data_fim, bloquear_fim):
            resultado[militar_id].add(cursor)
            cursor += timedelta(days=1)

    return resultado
