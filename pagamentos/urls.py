from django.urls import path
from . import views

urlpatterns = [
    # Esta é a página principal onde o usuário vê o valor e tem o botão
    path('assinatura/', views.central_assinatura, name='central_assinatura'),
    
    path('assinatura/faturas/', views.listar_faturas, name='listar_faturas'),

    # Rota para o cancelamento
    path('assinatura/cancelar/', views.cancelar_assinatura, name='cancelar_assinatura'),
    
    # Webhook para o Mercado Pago nos avisar do pagamento
    path('webhook/', views.webhook_mercadopago, name='webhook_mp'),

    path('gerar-pix/', views.gerar_pix_producao, name='gerar_pix'),
]