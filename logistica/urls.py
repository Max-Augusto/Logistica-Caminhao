from django.urls import path, include
from . import views

urlpatterns = [
    # === ÁREA DO MOTORISTA ===
    path('', views.home_motorista, name='home_motorista'),
    path('registrar-viagem/', views.registrar_viagem, name='registrar_viagem'),
    path('registrar-despesa/tipo/', views.escolher_tipo_despesa, name='escolher_tipo_despesa'),
    path('registrar-despesa/', views.registrar_despesa, name='registrar_despesa'),

     # === LOGIN ===

    path('pagamentos/', include('pagamentos.urls')),
    
    # Rotas de Onboarding
    path('checar-perfil/', views.checar_perfil, name='checar_perfil'),
    #path('configurar-empresa/', views.configurar_empresa, name='configurar_empresa'),

    # === ÁREA ADMINISTRATIVA (PAINEL GESTÃO) ===
    
    # NÍVEL 0: Seleção do Caminhão (Página de Cards)
    path('painel/caminhoes/', views.selecionar_caminhao, name='selecionar_caminhao'),

    path('caminhao/adicionar/', views.adicionar_caminhao, name='adicionar_caminhao'),
    path('caminhao/editar/<int:caminhao_id>/', views.editar_caminhao, name='editar_caminhao'),
    path('caminhao/excluir/<int:caminhao_id>/', views.excluir_caminhao, name='excluir_caminhao'),

    # NÍVEL 1: Seleção de Ano
    path('painel/<int:caminhao_id>/anos/', views.selecao_ano, name='selecao_ano'), 
    
    # NÍVEL 2: Seleção de Meses
    path('painel/<int:caminhao_id>/<int:ano>/meses/', views.selecao_mes, name='selecao_mes'), 
    
    # NÍVEL 3: Dashboard Detalhado e Consultas
    path('dashboard/<int:caminhao_id>/<int:mes>/<int:ano>/', views.dashboard_detalhado, name='dashboard_detalhado'),
    path('comissoes/<int:caminhao_id>/<int:mes>/<int:ano>/', views.comissoes_por_motorista, name='comissoes_motoristas'),
    path('consumo/<int:caminhao_id>/<int:mes>/<int:ano>/', views.media_consumo, name='media_consumo'),

    path('caminhao/<int:caminhao_id>/dashboard/<int:mes>/<int:ano>/pdf/', views.dashboard_pdf, name='dashboard_pdf'),

    # === RELATÓRIOS (WEB E PDF) ===
    path('dashboard/<int:caminhao_id>/<int:mes>/<int:ano>/relatorio-custos/', 
         views.relatorio_custos, name='relatorio_custos'),
    
    path('dashboard/<int:caminhao_id>/<int:mes>/<int:ano>/relatorio-custos/pdf/', 
         views.gerar_pdf_custos, name='gerar_pdf_custos'),

    # === IMPRESSÃO DE COMISSÕES (PDF) ===
    path('caminhao/<int:caminhao_id>/comissoes/<int:mes>/<int:ano>/imprimir/', 
         views.gerar_pdf_comissoes_geral, name='gerar_pdf_comissoes_geral'),

    path('caminhao/<int:caminhao_id>/comissoes/<int:mes>/<int:ano>/imprimir/<str:motorista_nome>/', 
         views.gerar_pdf_comissao_individual, name='gerar_pdf_comissao_individual'),

    # === EDIÇÃO E EXCLUSÃO ===
    path('viagem/editar/<int:caminhao_id>/<int:pk>/<int:mes>/<int:ano>/', views.editar_viagem, name='editar_viagem'),
    path('viagem/excluir/<int:caminhao_id>/<int:pk>/', views.excluir_viagem, name='excluir_viagem'),
    path('despesa/editar/<int:caminhao_id>/<int:pk>/<int:mes>/<int:ano>/', views.editar_despesa, name='editar_despesa'),
    path('despesa/excluir/<int:caminhao_id>/<int:pk>/', views.excluir_despesa, name='excluir_despesa'),
]