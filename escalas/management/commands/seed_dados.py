"""Cria dados de exemplo para o Sistema de Escala Militar.

Uso:
    python manage.py seed_dados
    python manage.py seed_dados --reset   # apaga dados anteriores
"""
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from escalas.models import (
    CalendarioDia,
    Divisao,
    Especialidade,
    Militar,
    OrganizacaoMilitar,
    Posto,
    TipoEscala,
    TipoIndisponibilidade,
    TipoServico,
)


POSTOS = [
    ('Soldado', 'Sd', 1),
    ('Cabo', 'Cb', 2),
    ('3º Sargento', '3º Sgt', 3),
    ('2º Sargento', '2º Sgt', 4),
    ('1º Sargento', '1º Sgt', 5),
    ('Subtenente', 'SubTen', 6),
    ('Aspirante a Oficial', 'Asp', 7),
    ('2º Tenente', '2º Ten', 8),
    ('1º Tenente', '1º Ten', 9),
    ('Capitão', 'Cap', 10),
    ('Major', 'Maj', 11),
    ('Tenente-Coronel', 'TC', 12),
    ('Coronel', 'Cel', 13),
]

ESPECIALIDADES = [
    ('Comunicações', 'COM'),
    ('Mecânica', 'MEC'),
    ('Enfermagem', 'ENF'),
    ('Infantaria', 'INF'),
    ('Logística', 'LOG'),
    ('Inteligência', 'INT'),
]

DIVISOES = [
    ('Divisão de Pessoal', 'DPE', 'Gestão de pessoal e RH'),
    ('Divisão de Operações', 'DOP', 'Planejamento e operações táticas'),
    ('Divisão de Logística', 'DLG', 'Suprimento, transporte e manutenção'),
    ('Divisão Administrativa', 'DAD', 'Administração geral da OM'),
]

MILITARES = [
    # nome_completo, nome_guerra, cpf, matricula, posto_sigla, esp_sigla, div_sigla, nasc
    ('Carlos Eduardo da Silva', 'SILVA', '11122233344', '0001', 'Cap', 'INF', 'DOP', date(1985, 3, 12)),
    ('Marcos Antônio Pereira', 'PEREIRA', '22233344455', '0002', '1º Ten', 'COM', 'DOP', date(1990, 7, 21)),
    ('João Batista Souza', 'SOUZA', '33344455566', '0003', '2º Sgt', 'MEC', 'DLG', date(1992, 11, 5)),
    ('Rafael Almeida Costa', 'COSTA', '44455566677', '0004', '3º Sgt', 'LOG', 'DLG', date(1994, 1, 30)),
    ('Bruno Henrique Lima', 'LIMA', '55566677788', '0005', 'Cb', 'INF', 'DOP', date(1998, 5, 18)),
    ('André Luiz Martins', 'MARTINS', '66677788899', '0006', 'Sd', 'ENF', 'DPE', date(2001, 9, 9)),
    ('Felipe Rodrigues Nunes', 'NUNES', '77788899900', '0007', '1º Sgt', 'INT', 'DAD', date(1988, 4, 25)),
    ('Diego Oliveira Ramos', 'RAMOS', '88899900011', '0008', 'Maj', 'INF', 'DOP', date(1980, 12, 3)),
]

TIPOS_SERVICO = [
    ('Preto', '#1a1a1a', 'Segunda a sexta — dias úteis', 1),
    ('Vermelho', '#a01818', 'Sábado e domingo', 2),
    ('Roxo', '#5a1a7a', 'Feriados e datas especiais', 3),
]

TIPOS_ESCALA = [
    ('Permanência', 'Serviço de 24h na OM'),
    ('Sobreaviso', 'Disponibilidade para chamada'),
    ('Serviço Administrativo', 'Expediente em horário comercial'),
]

TIPOS_INDISPONIBILIDADE = [
    ('Férias', 'Período de férias regulamentares', True),
    ('Licença Médica', 'Afastamento por motivo de saúde', True),
    ('Missão', 'Em missão fora da OM', True),
    ('Dispensa', 'Dispensa do serviço', True),
    ('Curso', 'Em curso/capacitação', True),
]


class Command(BaseCommand):
    help = 'Popula o banco com dados de exemplo para o Sistema de Escala Militar.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Apaga dados de exemplo anteriores antes de inserir.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write(self.style.WARNING('Removendo dados existentes...'))
            CalendarioDia.objects.all().delete()
            Militar.objects.all().delete()
            Divisao.objects.all().delete()
            TipoServico.objects.all().delete()
            OrganizacaoMilitar.objects.all().delete()
            Posto.objects.all().delete()
            Especialidade.objects.all().delete()
            TipoEscala.objects.all().delete()
            TipoIndisponibilidade.objects.all().delete()

        # ---- Postos
        self.stdout.write('Postos...')
        postos = {}
        for nome, sigla, ordem in POSTOS:
            obj, _ = Posto.objects.get_or_create(
                sigla=sigla,
                defaults={'nome': nome, 'ordem_hierarquica': ordem, 'ativo': True},
            )
            postos[sigla] = obj

        # ---- Especialidades
        self.stdout.write('Especialidades...')
        especialidades = {}
        for nome, sigla in ESPECIALIDADES:
            obj, _ = Especialidade.objects.get_or_create(
                sigla=sigla,
                defaults={'nome': nome, 'ativo': True},
            )
            especialidades[sigla] = obj

        # ---- OM
        self.stdout.write('Organização Militar...')
        om, _ = OrganizacaoMilitar.objects.get_or_create(
            sigla='1ºBI',
            defaults={
                'nome': '1º Batalhão de Infantaria',
                'tipo': 'batalhao',
                'comandante': 'Cel Roberto Andrade',
                'endereco': 'Av. dos Quartéis, 1000 — Brasília/DF',
                'telefone': '(61) 3000-0000',
                'email': 'comando@1bi.mil.br',
                'ativo': True,
            },
        )

        # ---- Divisões
        self.stdout.write('Divisões...')
        divisoes = {}
        for nome, sigla, descricao in DIVISOES:
            obj, _ = Divisao.objects.get_or_create(
                organizacao_militar=om,
                sigla=sigla,
                defaults={'nome': nome, 'descricao': descricao, 'ativo': True},
            )
            divisoes[sigla] = obj

        # ---- Tipos de serviço
        self.stdout.write('Tipos de serviço...')
        for nome, cor, descricao, ordem in TIPOS_SERVICO:
            TipoServico.objects.get_or_create(
                organizacao_militar=om,
                nome=nome,
                defaults={
                    'cor_hex': cor,
                    'descricao': descricao,
                    'ordem': ordem,
                    'ativo': True,
                },
            )

        # ---- Tipos de escala
        self.stdout.write('Tipos de escala...')
        for nome, descricao in TIPOS_ESCALA:
            TipoEscala.objects.get_or_create(
                nome=nome,
                defaults={'descricao': descricao, 'ativo': True},
            )

        # ---- Tipos de indisponibilidade
        self.stdout.write('Tipos de indisponibilidade...')
        for nome, descricao, exclui in TIPOS_INDISPONIBILIDADE:
            TipoIndisponibilidade.objects.get_or_create(
                nome=nome,
                defaults={
                    'descricao': descricao,
                    'exclui_do_sorteio': exclui,
                    'ativo': True,
                },
            )

        # ---- Militares
        self.stdout.write('Militares...')
        for (nome_c, ng, cpf, mat, posto_s, esp_s, div_s, nasc) in MILITARES:
            Militar.objects.update_or_create(
                cpf=cpf,
                defaults={
                    'organizacao_militar': om,
                    'divisao': divisoes.get(div_s),
                    'posto': postos[posto_s],
                    'especialidade': especialidades.get(esp_s),
                    'nome_guerra': ng,
                    'nome_completo': nome_c,
                    'matricula': mat,
                    'data_nascimento': nasc,
                    'ativo': True,
                },
            )

        # ---- Calendário 2026
        self.stdout.write('Calendário 2026 (auto)...')
        try:
            CalendarioDia.gerar_calendario_automatico(om, 2026)
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(self.style.WARNING(f'Calendário: {exc}'))

        self.stdout.write(self.style.SUCCESS('Seed concluído com sucesso.'))
        self.stdout.write(
            f'  - OM: {om.sigla} / {om.nome}\n'
            f'  - Postos: {Posto.objects.count()}\n'
            f'  - Especialidades: {Especialidade.objects.count()}\n'
            f'  - Divisões: {Divisao.objects.filter(organizacao_militar=om).count()}\n'
            f'  - Militares: {Militar.objects.filter(organizacao_militar=om).count()}\n'
            f'  - Tipos de serviço: {TipoServico.objects.filter(organizacao_militar=om).count()}\n'
            f'  - Dias no calendário: {CalendarioDia.objects.filter(organizacao_militar=om).count()}'
        )
