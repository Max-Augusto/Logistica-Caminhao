from django.contrib import admin
from .models import AssinaturaMP, HistoricoPagamento, LogEmail

@admin.register(AssinaturaMP)
class AssinaturaMPAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'status', 'valor_atual', 'preapproval_id', 'data_criacao')
    search_fields = ('empresa__nome', 'preapproval_id')
    list_filter = ('status',)

@admin.register(HistoricoPagamento)
class HistoricoPagamentoAdmin(admin.ModelAdmin):
    list_display = ('payment_id', 'assinatura', 'valor_pago', 'data_pagamento')

@admin.register(LogEmail)
class LogEmailAdmin(admin.ModelAdmin):
    list_display = ('data_envio', 'destinatario', 'assunto', 'status')
    list_filter = ('status', 'data_envio')
    search_fields = ('destinatario', 'assunto', 'erro_detalhe')
    readonly_fields = ('data_envio', 'erro_detalhe')