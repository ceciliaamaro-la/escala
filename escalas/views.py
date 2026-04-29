"""
Views do Sistema de Escala Militar.
Foco atual: dashboard, autenticação e cadastros (OM, Divisões, Postos,
Especialidades, Militares). As views de geração de escala estão em
`views_escala_legado.py` e serão integradas em uma próxima etapa.

Suporta múltiplas OMs: a OM ativa é mantida na sessão do usuário
(`request.session['om_id_ativa']`) e selecionada via dropdown na navbar.
"""
from datetime import date as _date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .context_processors import SESSION_KEY_OM, obter_om_da_sessao
from .forms_cadastro import (
    DivisaoForm,
    EspecialidadeForm,
    MilitarForm,
    OrganizacaoMilitarForm,
    PostoForm,
    QuadrinhoForm,
    TipoEscalaForm,
    TipoIndisponibilidadeForm,
)
from .models import (
    Divisao,
    EscalaItem,
    Especialidade,
    Militar,
    OrganizacaoMilitar,
    Posto,
    Quadrinho,
    TipoEscala,
    TipoIndisponibilidade,
    TipoServico,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def obter_om_ativa(request):
    """Retorna a OM ativa do usuário (sessão) ou None se nenhuma cadastrada."""
    return obter_om_da_sessao(request)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@login_required
def dashboard(request):
    om = obter_om_ativa(request)

    contexto = {
        'om': om,
        'total_militares': 0,
        'total_divisoes': 0,
        'total_postos': Posto.objects.filter(ativo=True).count(),
        'total_especialidades': Especialidade.objects.filter(ativo=True).count(),
        'total_oms': OrganizacaoMilitar.objects.filter(ativo=True).count(),
        'militares_recentes': [],
        'divisoes_resumo': [],
    }

    if om:
        contexto.update({
            'total_militares': Militar.objects.filter(
                organizacao_militar=om, ativo=True
            ).count(),
            'total_divisoes': Divisao.objects.filter(
                organizacao_militar=om, ativo=True
            ).count(),
            'militares_recentes': Militar.objects.filter(
                organizacao_militar=om, ativo=True
            ).select_related('posto', 'divisao', 'especialidade').order_by(
                '-data_criacao'
            )[:6],
            'divisoes_resumo': Divisao.objects.filter(
                organizacao_militar=om, ativo=True
            ).annotate(
                total_militares=Count('militares', filter=Q(militares__ativo=True))
            ).order_by('nome'),
        })

    return render(request, 'dashboard.html', contexto)


# ---------------------------------------------------------------------------
# Organizações Militares (multi-OM)
# ---------------------------------------------------------------------------

@login_required
def organizacao_listar(request):
    oms = OrganizacaoMilitar.objects.annotate(
        total_militares=Count('militares', filter=Q(militares__ativo=True)),
        total_divisoes=Count('divisoes', filter=Q(divisoes__ativo=True), distinct=True),
    ).order_by('-ativo', 'sigla')
    return render(request, 'cadastro/organizacao_list.html', {'oms': oms})


@login_required
def organizacao_detalhe(request, om_id=None):
    """Detalhe de uma OM. Se om_id não informado, usa a OM ativa."""
    if om_id is None:
        om = obter_om_ativa(request)
        if om is None:
            return redirect('organizacao_novo')
    else:
        om = get_object_or_404(OrganizacaoMilitar, pk=om_id)
    return render(request, 'cadastro/organizacao_detail.html', {'om': om})


@login_required
def organizacao_form(request, om_id=None):
    instancia = get_object_or_404(OrganizacaoMilitar, pk=om_id) if om_id else None
    if request.method == 'POST':
        form = OrganizacaoMilitarForm(request.POST, request.FILES, instance=instancia)
        if form.is_valid():
            om = form.save()
            # se for a primeira, ativa na sessão
            if not request.session.get(SESSION_KEY_OM):
                request.session[SESSION_KEY_OM] = om.id
            messages.success(
                request,
                f'OM {om.sigla} {"atualizada" if instancia else "cadastrada"} com sucesso.',
            )
            return redirect('organizacao_detalhe', om_id=om.id)
    else:
        form = OrganizacaoMilitarForm(instance=instancia)
    return render(
        request,
        'cadastro/organizacao_form.html',
        {'form': form, 'om': instancia},
    )


@login_required
@require_POST
def organizacao_trocar(request):
    """Define a OM ativa na sessão e volta para a página anterior."""
    om_id_raw = request.POST.get('om_id')
    proximo = request.POST.get('next') or 'dashboard'
    try:
        om_id = int(om_id_raw) if om_id_raw not in (None, '', 'None') else None
    except (TypeError, ValueError):
        om_id = None
    if om_id:
        om = OrganizacaoMilitar.objects.filter(pk=om_id, ativo=True).first()
        if om:
            request.session[SESSION_KEY_OM] = om.id
            messages.success(request, f'OM ativa alterada para {om.sigla}.')
        else:
            messages.error(request, 'OM inválida ou inativa.')
    return redirect(proximo)


# ---------------------------------------------------------------------------
# Postos (lista global, hierarquia militar)
# ---------------------------------------------------------------------------

@login_required
def posto_listar(request):
    postos = Posto.objects.all().order_by('ordem_hierarquica')
    return render(request, 'cadastro/posto_list.html', {'postos': postos})


@login_required
def posto_form(request, posto_id=None):
    instancia = get_object_or_404(Posto, pk=posto_id) if posto_id else None
    if request.method == 'POST':
        form = PostoForm(request.POST, instance=instancia)
        if form.is_valid():
            form.save()
            messages.success(request, 'Posto salvo com sucesso.')
            return redirect('posto_listar')
    else:
        form = PostoForm(instance=instancia)
    return render(
        request,
        'cadastro/posto_form.html',
        {'form': form, 'posto': instancia},
    )


@login_required
def posto_excluir(request, posto_id):
    posto = get_object_or_404(Posto, pk=posto_id)
    if request.method == 'POST':
        if posto.militares.filter(ativo=True).exists():
            messages.error(
                request,
                'Existem militares ativos com este posto. '
                'Desative o posto ao invés de excluir.',
            )
        else:
            posto.ativo = False
            posto.save()
            messages.success(request, 'Posto desativado.')
        return redirect('posto_listar')
    return render(
        request,
        'cadastro/posto_confirm_delete.html',
        {'posto': posto},
    )


# ---------------------------------------------------------------------------
# Especialidades
# ---------------------------------------------------------------------------

@login_required
def especialidade_listar(request):
    especialidades = Especialidade.objects.all().order_by('nome')
    return render(
        request,
        'cadastro/especialidade_list.html',
        {'especialidades': especialidades},
    )


@login_required
def especialidade_form(request, especialidade_id=None):
    instancia = (
        get_object_or_404(Especialidade, pk=especialidade_id)
        if especialidade_id else None
    )
    if request.method == 'POST':
        form = EspecialidadeForm(request.POST, instance=instancia)
        if form.is_valid():
            form.save()
            messages.success(request, 'Especialidade salva com sucesso.')
            return redirect('especialidade_listar')
    else:
        form = EspecialidadeForm(instance=instancia)
    return render(
        request,
        'cadastro/especialidade_form.html',
        {'form': form, 'especialidade': instancia},
    )


@login_required
def especialidade_excluir(request, especialidade_id):
    esp = get_object_or_404(Especialidade, pk=especialidade_id)
    if request.method == 'POST':
        esp.ativo = False
        esp.save()
        messages.success(request, 'Especialidade desativada.')
        return redirect('especialidade_listar')
    return render(
        request,
        'cadastro/especialidade_confirm_delete.html',
        {'especialidade': esp},
    )


# ---------------------------------------------------------------------------
# Tipos de Indisponibilidade (lista global)
# ---------------------------------------------------------------------------

@login_required
def tipo_indisponibilidade_listar(request):
    tipos = TipoIndisponibilidade.objects.all().order_by('nome')
    return render(
        request,
        'cadastro/tipo_indisponibilidade_list.html',
        {'tipos': tipos},
    )


@login_required
def tipo_indisponibilidade_form(request, tipo_id=None):
    instancia = (
        get_object_or_404(TipoIndisponibilidade, pk=tipo_id) if tipo_id else None
    )
    if request.method == 'POST':
        form = TipoIndisponibilidadeForm(request.POST, instance=instancia)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tipo de indisponibilidade salvo com sucesso.')
            return redirect('tipo_indisponibilidade_listar')
    else:
        form = TipoIndisponibilidadeForm(instance=instancia)
    return render(
        request,
        'cadastro/tipo_indisponibilidade_form.html',
        {'form': form, 'tipo': instancia},
    )


@login_required
def tipo_indisponibilidade_excluir(request, tipo_id):
    tipo = get_object_or_404(TipoIndisponibilidade, pk=tipo_id)
    if request.method == 'POST':
        if tipo.indisponibilidades.exists():
            tipo.ativo = False
            tipo.save()
            messages.success(
                request,
                'Tipo de indisponibilidade desativado (existem registros vinculados, '
                'histórico preservado).',
            )
        else:
            tipo.delete()
            messages.success(request, 'Tipo de indisponibilidade excluído.')
        return redirect('tipo_indisponibilidade_listar')
    return render(
        request,
        'cadastro/tipo_indisponibilidade_confirm_delete.html',
        {'tipo': tipo},
    )


# ---------------------------------------------------------------------------
# Tipos de Escala (cadastro global, não escopado por OM)
# ---------------------------------------------------------------------------

@login_required
def tipo_escala_listar(request):
    tipos = (
        TipoEscala.objects.all()
        .annotate(
            qtd_escalas=Count('escalas', distinct=True),
            qtd_quadrinhos=Count('quadrinhos', distinct=True),
        )
        .order_by('-ativo', 'nome')
    )
    return render(
        request,
        'cadastro/tipo_escala_list.html',
        {'tipos': tipos},
    )


@login_required
def tipo_escala_form(request, tipo_id=None):
    instancia = get_object_or_404(TipoEscala, pk=tipo_id) if tipo_id else None
    if request.method == 'POST':
        form = TipoEscalaForm(request.POST, instance=instancia)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tipo de escala salvo com sucesso.')
            return redirect('tipo_escala_listar')
    else:
        form = TipoEscalaForm(instance=instancia)
    return render(
        request,
        'cadastro/tipo_escala_form.html',
        {'form': form, 'tipo': instancia},
    )


@login_required
def tipo_escala_excluir(request, tipo_id):
    tipo = get_object_or_404(TipoEscala, pk=tipo_id)
    tem_vinculos = tipo.escalas.exists() or tipo.quadrinhos.exists()
    if request.method == 'POST':
        if tem_vinculos:
            tipo.ativo = False
            tipo.save()
            messages.success(
                request,
                'Tipo de escala desativado (existem escalas ou quadrinhos '
                'vinculados, histórico preservado).',
            )
        else:
            tipo.delete()
            messages.success(request, 'Tipo de escala excluído.')
        return redirect('tipo_escala_listar')
    return render(
        request,
        'cadastro/tipo_escala_confirm_delete.html',
        {
            'tipo': tipo,
            'qtd_escalas': tipo.escalas.count(),
            'qtd_quadrinhos': tipo.quadrinhos.count(),
            'tem_vinculos': tem_vinculos,
        },
    )


# ---------------------------------------------------------------------------
# Divisões (escopo: OM ativa)
# ---------------------------------------------------------------------------

@login_required
def divisao_listar(request):
    om = obter_om_ativa(request)
    divisoes = (
        Divisao.objects.filter(organizacao_militar=om).annotate(
            total_militares=Count('militares', filter=Q(militares__ativo=True))
        ).order_by('nome')
        if om else Divisao.objects.none()
    )
    return render(
        request,
        'cadastro/divisao_list.html',
        {'divisoes': divisoes, 'om': om},
    )


@login_required
def divisao_form(request, divisao_id=None):
    om = obter_om_ativa(request)
    if om is None:
        messages.error(request, 'Cadastre uma Organização Militar antes.')
        return redirect('organizacao_novo')

    instancia = get_object_or_404(Divisao, pk=divisao_id) if divisao_id else None

    if request.method == 'POST':
        form = DivisaoForm(request.POST, instance=instancia)
        if form.is_valid():
            divisao = form.save(commit=False)
            divisao.organizacao_militar = om
            divisao.save()
            messages.success(request, 'Divisão salva com sucesso.')
            return redirect('divisao_listar')
    else:
        form = DivisaoForm(instance=instancia)

    return render(
        request,
        'cadastro/divisao_form.html',
        {'form': form, 'divisao': instancia, 'om': om},
    )


@login_required
def divisao_excluir(request, divisao_id):
    divisao = get_object_or_404(Divisao, pk=divisao_id)
    if request.method == 'POST':
        divisao.ativo = False
        divisao.save()
        messages.success(request, 'Divisão desativada.')
        return redirect('divisao_listar')
    return render(
        request,
        'cadastro/divisao_confirm_delete.html',
        {'divisao': divisao},
    )


# ---------------------------------------------------------------------------
# Militares (escopo: OM ativa)
# ---------------------------------------------------------------------------

@login_required
def militar_listar(request):
    om = obter_om_ativa(request)
    q = request.GET.get('q', '').strip()
    divisao_filtro = request.GET.get('divisao', '')
    posto_filtro = request.GET.get('posto', '')

    ano_atual = _date.today().year
    try:
        ano = int(request.GET.get('ano') or ano_atual)
    except ValueError:
        ano = ano_atual

    tipo_escala_filtro = request.GET.get('tipo_escala', '')

    militares_qs = (
        Militar.objects.filter(organizacao_militar=om, ativo=True)
        if om else Militar.objects.none()
    )
    militares_qs = militares_qs.select_related('posto', 'divisao', 'especialidade')

    if q:
        militares_qs = militares_qs.filter(
            Q(nome_guerra__icontains=q)
            | Q(nome_completo__icontains=q)
            | Q(matricula__icontains=q)
            | Q(cpf__icontains=q)
        )

    if divisao_filtro:
        militares_qs = militares_qs.filter(divisao_id=divisao_filtro)

    if posto_filtro:
        militares_qs = militares_qs.filter(posto_id=posto_filtro)

    militares_qs = militares_qs.order_by('-posto__ordem_hierarquica', 'nome_guerra')
    militares = list(militares_qs)

    divisoes = (
        Divisao.objects.filter(organizacao_militar=om, ativo=True).order_by('nome')
        if om else Divisao.objects.none()
    )
    postos = Posto.objects.filter(ativo=True).order_by('-ordem_hierarquica')

    tipos_escala = list(TipoEscala.objects.filter(ativo=True).order_by('nome'))
    tipo_escala_atual = None
    if tipo_escala_filtro:
        tipo_escala_atual = next(
            (t for t in tipos_escala if str(t.id) == tipo_escala_filtro), None
        )
    if tipo_escala_atual is None and tipos_escala:
        tipo_escala_atual = tipos_escala[0]
        tipo_escala_filtro = str(tipo_escala_atual.id)

    tipos_servico = (
        list(om.tipos_servico.filter(ativo=True).order_by('ordem')) if om else []
    )

    quadrinhos_map = {}
    if om and tipo_escala_atual and militares:
        for qd in Quadrinho.objects.filter(
            militar__in=militares,
            tipo_escala=tipo_escala_atual,
            ano=ano,
        ):
            quadrinhos_map[(qd.militar_id, qd.tipo_servico_id)] = qd

    militares_lista = []
    for m in militares:
        celulas = []
        total = 0
        for ts in tipos_servico:
            qd = quadrinhos_map.get((m.id, ts.id))
            valor = qd.total if qd else 0
            celulas.append({'tipo_servico': ts, 'valor': valor})
            total += valor
        militares_lista.append({'militar': m, 'celulas': celulas, 'total': total})

    anos_opcoes = list(range(ano_atual + 1, ano_atual - 5, -1))

    return render(
        request,
        'cadastro/militar_list.html',
        {
            'militares_lista': militares_lista,
            'tipos_servico': tipos_servico,
            'tipos_escala': tipos_escala,
            'tipo_escala_atual': tipo_escala_atual,
            'tipo_escala_filtro': tipo_escala_filtro,
            'ano': ano,
            'anos_opcoes': anos_opcoes,
            'divisoes': divisoes,
            'postos': postos,
            'om': om,
            'q': q,
            'divisao_filtro': divisao_filtro,
            'posto_filtro': posto_filtro,
            'total_militares': len(militares),
        },
    )


@login_required
def militar_detalhe(request, militar_id):
    militar = get_object_or_404(
        Militar.objects.select_related(
            'posto', 'divisao', 'especialidade', 'organizacao_militar'
        ),
        pk=militar_id,
    )

    om = militar.organizacao_militar
    ano_atual = _date.today().year
    try:
        ano = int(request.GET.get('ano') or ano_atual)
    except ValueError:
        ano = ano_atual

    tipos_servico = list(om.tipos_servico.filter(ativo=True).order_by('ordem'))
    tipos_escala = list(TipoEscala.objects.filter(ativo=True).order_by('nome'))

    quadrinhos = Quadrinho.objects.filter(militar=militar, ano=ano).select_related(
        'tipo_escala', 'tipo_servico'
    )
    quadrinhos_map = {(q.tipo_escala_id, q.tipo_servico_id): q for q in quadrinhos}

    contadores = []
    for te in tipos_escala:
        celulas = []
        total = 0
        tem_dado = False
        for ts in tipos_servico:
            qd = quadrinhos_map.get((te.id, ts.id))
            valor = qd.total if qd else 0
            celulas.append({
                'tipo_servico': ts,
                'valor': valor,
                'quadrinho': qd,
            })
            total += valor
            if qd:
                tem_dado = True
        contadores.append({
            'tipo_escala': te,
            'celulas': celulas,
            'total': total,
            'tem_dado': tem_dado,
        })

    itens_qs = (
        EscalaItem.objects.filter(
            militar=militar,
            calendario_dia__data__year=ano,
        )
        .select_related(
            'escala__tipo_escala',
            'calendario_dia__tipo_servico',
        )
        .order_by('calendario_dia__data')
    )
    itens = list(itens_qs)

    dias_servico = {it.calendario_dia.data: it for it in itens}

    DIAS_SEMANA_ABREV = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']

    import calendar as _cal
    cal = _cal.Calendar(firstweekday=0)
    meses = []
    for mes_num in range(1, 13):
        nome_mes = _cal.month_name[mes_num].capitalize() if False else [
            'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
            'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro',
        ][mes_num - 1]
        semanas = []
        tem_servico_no_mes = False
        for semana in cal.monthdatescalendar(ano, mes_num):
            dias_semana = []
            for d in semana:
                pertence_mes = d.month == mes_num
                item = dias_servico.get(d) if pertence_mes else None
                if item:
                    tem_servico_no_mes = True
                dias_semana.append({
                    'data': d,
                    'pertence_mes': pertence_mes,
                    'item': item,
                })
            semanas.append(dias_semana)
        meses.append({
            'numero': mes_num,
            'nome': nome_mes,
            'semanas': semanas,
            'tem_servico': tem_servico_no_mes,
        })

    anos_opcoes = list(range(ano_atual + 1, ano_atual - 5, -1))

    return render(
        request,
        'cadastro/militar_detail.html',
        {
            'militar': militar,
            'ano': ano,
            'anos_opcoes': anos_opcoes,
            'contadores': contadores,
            'tipos_servico': tipos_servico,
            'itens': itens,
            'meses': meses,
            'dias_semana_abrev': DIAS_SEMANA_ABREV,
            'total_servicos_ano': len(itens),
        },
    )


# ---------------------------------------------------------------------------
# Quadrinho (visão geral por OM × Tipo de Escala × Ano)
# ---------------------------------------------------------------------------

@login_required
def quadrinho_visao(request):
    om = obter_om_ativa(request)

    ano_atual = _date.today().year
    try:
        ano = int(request.GET.get('ano') or ano_atual)
    except ValueError:
        ano = ano_atual

    tipo_escala_param = request.GET.get('tipo_escala', '')

    tipos_escala = list(TipoEscala.objects.filter(ativo=True).order_by('nome'))
    tipo_escala_atual = None
    if tipo_escala_param:
        tipo_escala_atual = next(
            (t for t in tipos_escala if str(t.id) == tipo_escala_param), None
        )
    if tipo_escala_atual is None and tipos_escala:
        tipo_escala_atual = tipos_escala[0]

    tipos_servico = (
        list(om.tipos_servico.filter(ativo=True).order_by('ordem')) if om else []
    )

    militares = (
        list(
            Militar.objects.filter(organizacao_militar=om, ativo=True)
            .select_related('posto', 'divisao')
        )
        if om else []
    )

    quadrinhos_map = {}
    if om and tipo_escala_atual and militares and tipos_servico:
        for qd in Quadrinho.objects.filter(
            militar__in=militares,
            tipo_escala=tipo_escala_atual,
            tipo_servico__in=tipos_servico,
            ano=ano,
        ):
            quadrinhos_map[(qd.militar_id, qd.tipo_servico_id)] = qd

    linhas = []
    totais_coluna = {ts.id: 0 for ts in tipos_servico}
    total_geral = 0
    for m in militares:
        celulas = []
        total_militar = 0
        for ts in tipos_servico:
            qd = quadrinhos_map.get((m.id, ts.id))
            valor = qd.total if qd else 0
            celulas.append({
                'tipo_servico': ts,
                'quadrinho': qd,
                'valor': valor,
                'ajuste_inicial': qd.ajuste_inicial if qd else 0,
                'quantidade': qd.quantidade if qd else 0,
            })
            totais_coluna[ts.id] += valor
            total_militar += valor
        linhas.append({
            'militar': m,
            'celulas': celulas,
            'total': total_militar,
        })
        total_geral += total_militar

    ordem = request.GET.get('ordem', 'desc')
    if ordem == 'asc':
        linhas.sort(key=lambda x: (x['total'], x['militar'].nome_guerra))
    elif ordem == 'nome':
        linhas.sort(key=lambda x: x['militar'].nome_guerra.lower())
    else:
        linhas.sort(key=lambda x: (-x['total'], x['militar'].nome_guerra))

    totais_coluna_lista = [
        {'tipo_servico': ts, 'valor': totais_coluna[ts.id]} for ts in tipos_servico
    ]

    anos_opcoes = list(range(ano_atual + 1, ano_atual - 5, -1))

    return render(
        request,
        'cadastro/quadrinho_visao.html',
        {
            'om': om,
            'ano': ano,
            'anos_opcoes': anos_opcoes,
            'tipos_escala': tipos_escala,
            'tipo_escala_atual': tipo_escala_atual,
            'tipos_servico': tipos_servico,
            'linhas': linhas,
            'totais_coluna': totais_coluna_lista,
            'total_geral': total_geral,
            'ordem': ordem,
        },
    )


@login_required
def quadrinho_editar(request, militar_id, tipo_escala_id, tipo_servico_id, ano):
    om = obter_om_ativa(request)
    militar = get_object_or_404(
        Militar.objects.select_related('posto', 'organizacao_militar'),
        pk=militar_id,
    )
    if om and militar.organizacao_militar_id != om.id:
        messages.error(request, 'O militar não pertence à OM ativa.')
        return redirect('quadrinho_visao')

    tipo_escala = get_object_or_404(TipoEscala, pk=tipo_escala_id)
    tipo_servico = get_object_or_404(
        TipoServico, pk=tipo_servico_id, organizacao_militar=militar.organizacao_militar
    )

    quadrinho, _ = Quadrinho.objects.get_or_create(
        militar=militar,
        tipo_escala=tipo_escala,
        tipo_servico=tipo_servico,
        ano=ano,
        defaults={'quantidade': 0, 'ajuste_inicial': 0},
    )

    voltar_para = request.GET.get('voltar', 'quadrinho_visao')

    if request.method == 'POST':
        form = QuadrinhoForm(request.POST, instance=quadrinho)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'Quadrinho de {militar.nome_guerra} atualizado '
                f'({tipo_escala.nome} / {tipo_servico.nome}).'
            )
            if voltar_para == 'militar_detalhe':
                return redirect(
                    f"{reverse('militar_detalhe', args=[militar.id])}?ano={ano}"
                )
            return redirect(
                f"{reverse('quadrinho_visao')}?ano={ano}"
                f"&tipo_escala={tipo_escala.id}"
            )
    else:
        form = QuadrinhoForm(instance=quadrinho)

    return render(
        request,
        'cadastro/quadrinho_form.html',
        {
            'form': form,
            'quadrinho': quadrinho,
            'militar': militar,
            'tipo_escala': tipo_escala,
            'tipo_servico': tipo_servico,
            'ano': ano,
            'voltar_para': voltar_para,
        },
    )


@login_required
def militar_form(request, militar_id=None):
    om = obter_om_ativa(request)
    if om is None:
        messages.error(request, 'Cadastre uma Organização Militar antes.')
        return redirect('organizacao_novo')

    instancia = get_object_or_404(Militar, pk=militar_id) if militar_id else None

    if request.method == 'POST':
        form = MilitarForm(request.POST, instance=instancia, om=om)
        if form.is_valid():
            militar = form.save(commit=False)
            militar.organizacao_militar = om
            militar.save()
            messages.success(
                request,
                f'Militar {militar.nome_guerra} salvo com sucesso.',
            )
            return redirect('militar_detalhe', militar_id=militar.id)
    else:
        form = MilitarForm(instance=instancia, om=om)

    return render(
        request,
        'cadastro/militar_form.html',
        {'form': form, 'militar': instancia, 'om': om},
    )


@login_required
def militar_excluir(request, militar_id):
    militar = get_object_or_404(Militar, pk=militar_id)
    if request.method == 'POST':
        militar.ativo = False
        militar.save()
        messages.success(
            request,
            f'Militar {militar.nome_guerra} desativado (histórico preservado).',
        )
        return redirect('militar_listar')
    return render(
        request,
        'cadastro/militar_confirm_delete.html',
        {'militar': militar},
    )
