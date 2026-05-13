"""
Motor de Geração de Escala Vertical

Algoritmo de distribuição equilibrada que percorre dias em ordem cronológica
e para cada dia escolhe o militar mais adequado baseado em:
1. Menor quantidade de serviços no mês
2. Maior distância do último serviço
3. Ordem natural da matriz

Este motor substitui completamente o algoritmo anterior de "dia mais vazio".
"""

import logging
from datetime import date, timedelta
from typing import Dict, List, Optional, Set, Tuple
from django.db import transaction
from django.core.exceptions import ValidationError

from .models import (
    CalendarioDia,
    ConfiguracaoEscala,
    Escala,
    EscalaItem,
    Indisponibilidade,
    Militar,
    Quadrinho,
    TipoEscala,
    TipoServico,
)

logger = logging.getLogger(__name__)


class MotorEscalaVertical:
    """
    Motor de geração de escala com distribuição vertical equilibrada.

    Fluxo:
        1. Limpar itens antigos da escala do mês/tipo
        2. Para cada dia do mês (ordem cronológica 01→30):
           a. Ordenar militares por: menor qtd → maior distância último → ordem natural
           b. Subir verticalmente e escolher primeiro militar disponível
           c. Criar EscalaItem e atualizar Quadrinho
        3. Retornar resultado com contadores e alertas
    """

    def __init__(self, escala: Escala):
        self.escala = escala
        self.om = escala.organizacao_militar
        self.tipo_escala = escala.tipo_escala
        self.ano = escala.ano
        self.mes = escala.mes
        self.config = ConfiguracaoEscala.obter_para_om(self.om)

        # Dados carregados
        self.lista_dias: List[CalendarioDia] = []
        self.lista_militares: List[Militar] = []
        self.indisponibilidades: Dict[int, Set[date]] = {}

        # Estado dinâmico
        self.contagem_servicos: Dict[int, int] = {}  # militar_id → qtd no mês
        self.ultimo_servico: Dict[int, Optional[date]] = {}  # militar_id → última data

        # Resultados
        self.alocacoes_criadas = 0
        self.dias_sem_militar: List[date] = []
        self.alertas: List[str] = []

    def executar(self) -> Dict:
        """
        Executa o algoritmo completo de geração de escala vertical.

        Returns:
            dict com chaves: 'alocacoes_criadas', 'dias_sem_militar', 'alertas', 'sucesso'
        """
        logger.info(f"Iniciando MotorEscalaVertical para escala {self.escala}")

        with transaction.atomic():
            # PASSO 1: Limpar itens antigos
            self._limpar_itens_existentes()

            # PASSO 2: Carregar dados necessários
            self._carregar_dados()

            # PASSO 3: Processar cada dia em ordem cronológica
            self._processar_dias()

        # Retornar resultado
        return {
            'sucesso': True,
            'alocacoes_criadas': self.alocacoes_criadas,
            'dias_sem_militar': len(self.dias_sem_militar),
            'alertas': self.alertas,
        }

    def _limpar_itens_existentes(self):
        """Remove todos os itens existentes da escala."""
        count = self.escala.itens.count()
        if count > 0:
            logger.info(f"Removendo {count} itens existentes da escala {self.escala}")
            self.escala.itens.all().delete()

    def _carregar_dados(self):
        """Carrega dias, militares e indisponibilidades do período."""
        # Dias do mês
        primeiro_dia = date(self.ano, self.mes, 1)
        ultimo_dia = date(self.ano, self.mes, self._obter_ultimo_dia_mes())

        self.lista_dias = list(
            CalendarioDia.objects.filter(
                organizacao_militar=self.om,
                data__range=(primeiro_dia, ultimo_dia),
            )
            .select_related('tipo_servico')
            .order_by('data')
        )

        if not self.lista_dias:
            raise ValidationError(
                f"Não há dias cadastrados no calendário para {self.mes}/{self.ano}. "
                "Cadastre os dias ou gere o calendário automático."
            )

        # Militares ativos da OM
        self.lista_militares = list(
            Militar.objects.filter(
                organizacao_militar=self.om, ativo=True
            )
            .select_related('posto', 'organizacao_militar')
            .order_by('posto__ordem_hierarquica', 'data_ultima_promocao', 'nome_guerra')
        )

        if not self.lista_militares:
            raise ValidationError("Nenhum militar ativo nesta OM.")

        # Inicializar contadores
        for militar in self.lista_militares:
            self.contagem_servicos[militar.id] = 0
            self.ultimo_servico[militar.id] = None

        # Carregar indisponibilidades do período
        self._carregar_indisponibilidades(primeiro_dia, ultimo_dia)

        logger.info(
            f"Dados carregados: {len(self.lista_dias)} dias, "
            f"{len(self.lista_militares)} militares"
        )

    def _carregar_indisponibilidades(self, data_inicio: date, data_fim: date):
        """
        Carrega todas as indisponibilidades do período.
        Inclui: férias, licença, missão, afastamentos, etc.
        """
        margem = timedelta(days=self.config.folga_minima_dias + self.config.duracao_servico_dias)

        registros = Indisponibilidade.objects.filter(
            militar__organizacao_militar=self.om,
            tipo__exclui_do_sorteio=True,
            data_inicio__lte=data_fim + margem,
            data_fim__gte=data_inicio - margem,
        ).values_list('militar_id', 'data_inicio', 'data_fim', 'tipo__nome')

        for militar_id, ini, fim, tipo_nome in registros:
            self.indisponibilidades.setdefault(militar_id, set())
            cursor = ini
            while cursor <= fim:
                if data_inicio <= cursor <= data_fim:
                    self.indisponibilidades[militar_id].add(cursor)
                cursor += timedelta(days=1)

            # Bloqueio pré-férias
            if self.config.bloquear_pre_ferias:
                cursor = max(data_inicio, ini - timedelta(days=self.config.folga_minima_dias))
                while cursor <= min(data_fim, ini - timedelta(days=1)):
                    self.indisponibilidades[militar_id].add(cursor)
                    cursor += timedelta(days=1)

            # Bloqueio pós-férias
            if self.config.bloquear_pos_ferias:
                cursor = max(data_inicio, fim + timedelta(days=1))
                while cursor <= min(data_fim, fim + timedelta(days=self.config.folga_minima_dias)):
                    self.indisponibilidades[militar_id].add(cursor)
                    cursor += timedelta(days=1)

    def _processar_dias(self):
        """Processa cada dia em ordem cronológica."""
        for dia in self.lista_dias:
            self._processar_dia(dia)

    def _processar_dia(self, dia: CalendarioDia):
        """Processa um único dia: escolhe o melhor militar e cria a alocação."""
        data = dia.data

        # PASSO 2a: Ordenar militares
        militares_ordenados = self._ordenar_militares(data)

        # PASSO 2b: Subir verticalmente e encontrar primeiro disponível
        militar_escolhido = self._buscar_militar_disponivel(militares_ordenados, data)

        if militar_escolhido is None:
            # Nenhum militar disponível
            self.dias_sem_militar.append(data)
            alerta = f"ALERTA: Nenhum militar disponível para {data.strftime('%d/%m/%Y')}"
            self.alertas.append(alerta)
            logger.warning(alerta)
            return

        # PASSO 2c: Criar EscalaItem
        self._criar_alocacao(dia, militar_escolhido)

    def _ordenar_militares(self, data: date) -> List[Militar]:
        """
        Ordena militares por:
        1. Menor quantidade de serviços no mês
        2. Maior distância do último serviço
        3. Ordem natural da matriz (posto → promoção → nome_guerra)
        """
        militar_com_prioridade = []

        for militar in self.lista_militares:
            qtd = self.contagem_servicos.get(militar.id, 0)
            ultimo = self.ultimo_servico.get(militar.id)

            # Calcular distância do último serviço
            if ultimo:
                distancia = (data - ultimo).days
            else:
                # Se nunca serviu, distância infinita (prioridade máxima)
                distancia = 9999

            # Posição na ordem natural da matriz
            posicao_natural = self.lista_militares.index(militar)

            militar_com_prioridade.append({
                'militar': militar,
                'quantidade': qtd,
                'distancia': distancia,
                'posicao_natural': posicao_natural,
            })

        # Ordenar: menor quantidade → maior distância → posição natural
        militar_com_prioridade.sort(key=lambda x: (
            x['quantidade'],
            -x['distancia'],  # negativo para ordem decrescente
            x['posicao_natural'],
        ))

        return [item['militar'] for item in militar_com_prioridade]

    def _buscar_militar_disponivel(
        self,
        militares_ordenados: List[Militar],
        data: date
    ) -> Optional[Militar]:
        """
        Sob a lista ordenada, o primeiro militar disponível assume o dia.
        Verifica: indisponibilidades, folga mínima, forcar_escala.
        """
        for militar in militares_ordenados:
            if self._militar_pode_trabalhar(militar, data):
                return militar
        return None

    def _militar_pode_trabalhar(self, militar: Militar, data: date) -> bool:
        """
        Verifica se o militar pode trabalhar na data especificada.
        Considera:
        - Indisponibilidades (férias, licença, missão)
        - Folga mínima entre serviços
        - Carryover de meses anteriores
        """
        # 1. Verificar indisponibilidades diretas
        if militar.id in self.indisponibilidades:
            if data in self.indisponibilidades[militar.id]:
                return False

        # 2. Verificar folga mínima desde o último serviço
        ultimo = self.ultimo_servico.get(militar.id)
        if ultimo:
            dias_desde_ultimo = (data - ultimo).days
            folga_minima = self._obter_folga_minima()

            if dias_desde_ultimo < folga_minima:
                return False

        # 3. Verificar carryover de meses anteriores
        if self._tem_servico_mes_anterior(militar, data):
            return False

        return True

    def _tem_servico_mes_anterior(self, militar: Militar, data: date) -> bool:
        """
        Verifica se o militar tem serviço no período de folga anterior ao mês atual.
        Considera qualquer serviço do tipo de escala no mês anterior que ainda
        esteja no período de folga.
        """
        # Calcular período de bloqueio (duração serviço + folga mínima)
        janela_bloqueio = self.config.duracao_servico_dias + self._obter_folga_minima()
        data_inicio_periodo = data - timedelta(days=janela_bloqueio)

        # Se o período de bloqueio inclui dias do mês anterior
        if data_inicio_periodo.month == self.mes or data_inicio_periodo.month == (self.mes - 1 or 12):
            # Buscar escala do mês anterior
            mes_anterior = self.mes - 1 if self.mes > 1 else 12
            ano_anterior = self.ano if self.mes > 1 else self.ano - 1

            escala_mes_anterior = Escala.objects.filter(
                organizacao_militar=self.om,
                tipo_escala=self.tipo_escala,
                mes=mes_anterior,
                ano=ano_anterior,
                status='publicada',
            ).first()

            if not escala_mes_anterior:
                return False

            # Verificar se o militar tem serviço no período de bloqueio
            return EscalaItem.objects.filter(
                escala=escala_mes_anterior,
                militar=militar,
                calendario_dia__data__gte=data_inicio_periodo,
                calendario_dia__data__lt=date(self.ano, self.mes, 1),
                forcar_escala=False,
            ).exists()

        return False

    def _obter_folga_minima(self) -> int:
        """Retorna a folga mínima em dias (do tipo_escala ou da config)."""
        if self.tipo_escala.folga_minima_horas is not None:
            return max(1, self.tipo_escala.folga_minima_horas // 24)
        return self.config.folga_minima_dias

    def _criar_alocacao(self, dia: CalendarioDia, militar: Militar):
        """Cria o EscalaItem e atualiza os contadores."""
        # Criar item
        EscalaItem.objects.create(
            escala=self.escala,
            militar=militar,
            calendario_dia=dia,
            observacao='Gerado automaticamente (motor vertical)',
        )

        # Atualizar contadores
        self.contagem_servicos[militar.id] = self.contagem_servicos.get(militar.id, 0) + 1
        self.ultimo_servico[militar.id] = dia.data

        # Atualizar Quadrinho
        Quadrinho.incrementar(
            militar=militar,
            tipo_escala=self.tipo_escala,
            tipo_servico=dia.tipo_servico,
            ano=self.ano,
        )

        self.alocacoes_criadas += 1
        logger.debug(
            f"Alocado: {militar.nome_guerra} em {dia.data.strftime('%d/%m/%Y')}"
        )

    def _obter_ultimo_dia_mes(self) -> int:
        """Retorna o último dia do mês atual."""
        import calendar
        return calendar.monthrange(self.ano, self.mes)[1]


def gerar_escala_vertical(escala: Escala) -> int:
    """
    Função de alto nível para geração de escala vertical.
    Substitui o método anterior em Escala.gerar_escala_vertical().

    Args:
        escala: Instância de Escala em rascunho ou previsão

    Returns:
        int: Total de alocações criadas

    Raises:
        ValidationError: Se escala não estiver em rascunho/previsão,
                        ou se não houver militares/dias cadastrados
    """
    if escala.status not in ('rascunho', 'previsao'):
        raise ValidationError(
            "Apenas escalas em Rascunho ou Previsão podem ser geradas."
        )

    motor = MotorEscalaVertical(escala)
    resultado = motor.executar()

    return resultado['alocacoes_criadas']