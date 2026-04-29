"""URLs do módulo escalas (foco atual: cadastros)."""
from django.urls import path

from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    # Organização militar (singleton)
    path('organizacao/', views.organizacao_detalhe, name='organizacao_detalhe'),
    path('organizacao/editar/', views.organizacao_editar, name='organizacao_editar'),

    # Postos
    path('postos/', views.posto_listar, name='posto_listar'),
    path('postos/novo/', views.posto_form, name='posto_novo'),
    path('postos/<int:posto_id>/editar/', views.posto_form, name='posto_editar'),
    path('postos/<int:posto_id>/excluir/', views.posto_excluir, name='posto_excluir'),

    # Especialidades
    path('especialidades/', views.especialidade_listar, name='especialidade_listar'),
    path('especialidades/novo/', views.especialidade_form, name='especialidade_novo'),
    path(
        'especialidades/<int:especialidade_id>/editar/',
        views.especialidade_form,
        name='especialidade_editar',
    ),
    path(
        'especialidades/<int:especialidade_id>/excluir/',
        views.especialidade_excluir,
        name='especialidade_excluir',
    ),

    # Divisões
    path('divisoes/', views.divisao_listar, name='divisao_listar'),
    path('divisoes/novo/', views.divisao_form, name='divisao_novo'),
    path('divisoes/<int:divisao_id>/editar/', views.divisao_form, name='divisao_editar'),
    path('divisoes/<int:divisao_id>/excluir/', views.divisao_excluir, name='divisao_excluir'),

    # Militares
    path('militares/', views.militar_listar, name='militar_listar'),
    path('militares/novo/', views.militar_form, name='militar_novo'),
    path('militares/<int:militar_id>/', views.militar_detalhe, name='militar_detalhe'),
    path('militares/<int:militar_id>/editar/', views.militar_form, name='militar_editar'),
    path(
        'militares/<int:militar_id>/excluir/',
        views.militar_excluir,
        name='militar_excluir',
    ),
]
