"""ModelForms simples para os cadastros básicos."""
from datetime import date

from django import forms
from django.core.exceptions import ValidationError

from .models import (
    Divisao,
    Especialidade,
    Militar,
    OrganizacaoMilitar,
    Posto,
    TipoIndisponibilidade,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class BootstrapFormMixin:
    """Aplica `form-control`/`form-select` em todos os widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            css = widget.attrs.get('class', '')
            if isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs['class'] = (css + ' form-select').strip()
            elif isinstance(widget, forms.CheckboxInput):
                widget.attrs['class'] = (css + ' form-check-input').strip()
            elif isinstance(widget, forms.Textarea):
                widget.attrs['class'] = (css + ' form-control').strip()
            else:
                widget.attrs['class'] = (css + ' form-control').strip()


# ---------------------------------------------------------------------------
# Organização Militar
# ---------------------------------------------------------------------------

class OrganizacaoMilitarForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = OrganizacaoMilitar
        fields = [
            'nome', 'sigla', 'tipo', 'comandante',
            'endereco', 'telefone', 'email', 'logo',
        ]


# ---------------------------------------------------------------------------
# Posto
# ---------------------------------------------------------------------------

class PostoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Posto
        fields = ['nome', 'sigla', 'ordem_hierarquica', 'ativo']


# ---------------------------------------------------------------------------
# Especialidade
# ---------------------------------------------------------------------------

class EspecialidadeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Especialidade
        fields = ['nome', 'sigla', 'descricao', 'ativo']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
        }


# ---------------------------------------------------------------------------
# Tipo de Indisponibilidade
# ---------------------------------------------------------------------------

class TipoIndisponibilidadeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TipoIndisponibilidade
        fields = ['nome', 'descricao', 'exclui_do_sorteio', 'ativo']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
        }


# ---------------------------------------------------------------------------
# Divisão
# ---------------------------------------------------------------------------

class DivisaoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Divisao
        fields = ['nome', 'sigla', 'descricao', 'chefe', 'ativo']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
        }


# ---------------------------------------------------------------------------
# Militar
# ---------------------------------------------------------------------------

class MilitarForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Militar
        fields = [
            'posto', 'especialidade', 'divisao',
            'nome_guerra', 'nome_completo',
            'cpf', 'matricula', 'data_nascimento',
            'ativo',
        ]
        widgets = {
            'data_nascimento': forms.DateInput(attrs={'type': 'date'}),
            'cpf': forms.TextInput(attrs={'placeholder': 'somente números (11 dígitos)'}),
            'nome_guerra': forms.TextInput(attrs={'placeholder': 'Ex: SILVA'}),
        }

    def __init__(self, *args, om=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.om = om
        self.fields['posto'].queryset = Posto.objects.filter(ativo=True).order_by(
            'ordem_hierarquica'
        )
        self.fields['especialidade'].queryset = Especialidade.objects.filter(
            ativo=True
        ).order_by('nome')
        self.fields['especialidade'].required = False
        self.fields['divisao'].required = False
        if om is not None:
            self.fields['divisao'].queryset = Divisao.objects.filter(
                organizacao_militar=om, ativo=True
            ).order_by('nome')
        else:
            self.fields['divisao'].queryset = Divisao.objects.none()

    def clean_cpf(self):
        cpf = (self.cleaned_data.get('cpf') or '').strip()
        cpf = ''.join(filter(str.isdigit, cpf))
        if len(cpf) != 11:
            raise ValidationError('CPF deve conter exatamente 11 dígitos.')
        qs = Militar.objects.filter(cpf=cpf)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError('Já existe um militar cadastrado com este CPF.')
        return cpf

    def clean_matricula(self):
        matricula = (self.cleaned_data.get('matricula') or '').strip()
        if not matricula:
            raise ValidationError('Matrícula é obrigatória.')
        if self.om is not None:
            qs = Militar.objects.filter(
                organizacao_militar=self.om, matricula=matricula
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(
                    'Já existe um militar com esta matrícula nesta OM.'
                )
        return matricula

    def clean_data_nascimento(self):
        data_nascimento = self.cleaned_data.get('data_nascimento')
        if data_nascimento:
            hoje = date.today()
            idade = (
                hoje.year - data_nascimento.year
                - ((hoje.month, hoje.day) < (data_nascimento.month, data_nascimento.day))
            )
            if idade < 18:
                raise ValidationError('Militar deve ter no mínimo 18 anos.')
        return data_nascimento
