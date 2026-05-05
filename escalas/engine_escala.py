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
║  Ponto de início do mês:                                             ║
║    • Encontra o militar com MENOR quadrinho (tipo_servico atual).    ║
║    • A coluna inicial é igual a esse valor mínimo.                   ║
║    • A linha inicial é a posição desse militar (base da coluna).     ║
║    • Se houver ponteiro salvo do mês anterior, retoma de lá.         ║
║                                                                      ║
║  Continuidade:                                                       ║
║    • Ao final de cada geração, salva (ultimo_militar_id) no banco.  ║
║    • O mês seguinte retoma DEPOIS desse militar.                     ║
║                                                                      ║
║  Separação por tipo:                                                 ║
║    • Escala Preta (dias úteis) e Vermelha (fins de semana/feriados)  ║
║      têm ponteiros e contadores INDEPENDENTES.                       ║
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
        quadrinhos_inicio: {militar_id: n_servicos} — contagem ANTES deste mês.
        ultimo_militar_id: pk do último militar escalado no mês anterior
                           para este tipo de serviço (None = início do sistema).
        config           : ConfiguracaoEscala (usado para folga pós-serviço).

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

    # ── Determinar ponteiro de início ───────────────────────────────────────
    min_count = min(counts.values())

    if ultimo_militar_id and ultimo_militar_id in idx_por_id:
        # Retoma após o último militar do mês anterior.
        # Os quadrinhos já refletem o mês anterior, então min_count já aponta
        # para a coluna correta (não incrementar aqui).
        ultimo_idx = idx_por_id[ultimo_militar_id]
        proximo_idx = ultimo_idx + 1
        if proximo_idx >= n:
            # Chegou ao topo → base da mesma coluna (o col avança naturalmente
            # quando não houver ninguém com count == col no próximo varredura)
            proximo_idx = 0
        start_idx = proximo_idx
        start_col = min_count
    else:
        # Início do sistema: começa na base da coluna do militar com menos serviços.
        start_col = min_count
        # Base da coluna = militar mais moderno (menor índice) com count == min_count
        start_idx = next(
            (i for i, m in enumerate(lista_militares) if counts[m.id] == min_count),
            0,
        )

    # ── Janela de folga pós-serviço (bloqueio dentro do mês) ────────────────
    janela_folga = 0
    if config is not None:
        janela_folga = config.duracao_servico_dias + config.folga_minima_dias

    # Conjunto de datas bloqueadas por folga pós-serviço geradas NESTE mês
    # (acumula conforme vamos atribuindo serviços)
    folga_extra: Dict[int, Set[date_type]] = {m.id: set() for m in lista_militares}

    # ── Processamento cronológico ────────────────────────────────────────────
    resultado: List[Tuple] = []
    ultimo_atribuido_id: Optional[int] = ultimo_militar_id

    idx = start_idx
    col = start_col

    for dia in lista_dias:
        data = dia.data
        atribuido = None

        # Busca o próximo militar disponível na coluna atual (base→topo)
        tentativas = 0
        pos = idx
        coluna = col

        while tentativas < n * 3:          # teto de segurança
            if pos >= n:
                # Chegou ao topo → próxima coluna, reinicia na base
                pos = 0
                coluna += 1

            militar = lista_militares[pos]
            mil_count = counts[militar.id]

            if mil_count == coluna:
                # Este militar está nesta coluna; verificar disponibilidade
                bloqueado_indisp = data in indisponibilidades.get(militar.id, set())
                bloqueado_folga  = data in folga_extra.get(militar.id, set())
                if not bloqueado_indisp and not bloqueado_folga:
                    atribuido = militar
                    break

            pos += 1
            tentativas += 1

        if atribuido:
            counts[atribuido.id] += 1
            ultimo_atribuido_id = atribuido.id

            # Avança ponteiro para a próxima posição APÓS o atribuído
            idx = pos + 1
            col = coluna

            # Marca folga pós-serviço para os dias seguintes
            if janela_folga > 0:
                dias_lista_datas = {d.data for d in lista_dias}
                for k in range(1, janela_folga + 1):
                    data_bloqueada = data + timedelta(days=k)
                    if data_bloqueada in dias_lista_datas:
                        folga_extra[atribuido.id].add(data_bloqueada)

        resultado.append((dia, atribuido))

    return resultado, ultimo_atribuido_id


# ---------------------------------------------------------------------------
# Indisponibilidades (inalterado — ainda usado pela view)
# ---------------------------------------------------------------------------

def obter_indisponibilidades(
    militares: list,
    data_inicio,
    data_fim,
    config=None,
) -> Dict[int, Set[date_type]]:
    """
    Consulta o banco e retorna {militar_id: set(datas bloqueadas)}
    para o intervalo [data_inicio, data_fim].

    Aplica:
      1. Indisponibilidades diretas (férias, licença, etc.)
      2. Bloqueio pré-indisponibilidade (configurável)
      3. Bloqueio pós-indisponibilidade (configurável)
      4. Folga mínima pós-serviço carryover do mês anterior
    """
    from .models import EscalaItem, Indisponibilidade

    if not militares:
        return {}

    if config is None:
        from .models import ConfiguracaoEscala
        om = militares[0].organizacao_militar
        config = ConfiguracaoEscala.obter_para_om(om)

    folga_min_dias = config.folga_minima_dias
    duracao_dias   = config.duracao_servico_dias
    janela_total   = duracao_dias + folga_min_dias

    militar_ids = [m.id for m in militares]
    resultado: Dict[int, Set[date_type]] = {}
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

    # Carryover inter-mês: serviços do mês anterior que ainda bloqueiam este mês
    lookback = data_inicio - timedelta(days=janela_total)
    items_anteriores = EscalaItem.objects.filter(
        militar_id__in=militar_ids,
        calendario_dia__data__gte=lookback,
        calendario_dia__data__lt=data_inicio,
    ).values_list('militar_id', 'calendario_dia__data')

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
