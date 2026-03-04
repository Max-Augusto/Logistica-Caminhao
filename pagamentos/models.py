from django.db import models
from logistica.models import Empresa

class AssinaturaMP(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('authorized', 'Autorizado/Ativo'),
        ('paused', 'Pausado'),
        ('cancelled', 'Cancelado'),
    ]

    empresa = models.OneToOneField(Empresa, on_delete=models.CASCADE, related_name='assinatura_detalhes')
    
    # ID único da assinatura no Mercado Pago (Preapproval ID)
    # Fundamental para atualizar o valor quando a frota aumentar
    preapproval_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    
    # Armazena o valor que está sendo cobrado atualmente no Mercado Pago
    valor_atual = models.DecimalField(max_digits=10, decimal_places=2)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Para histórico e auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    ultima_atualizacao = models.DateTimeField(auto_now=True)
    
    # Caso queira guardar o e-mail de quem pagou no cartão (pode ser diferente do login)
    payer_email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return f"{self.empresa.nome} - {self.status} (R$ {self.valor_atual})"

    class Meta:
        verbose_name = "Assinatura Mercado Pago"
        verbose_name = "Assinaturas Mercado Pago"

class HistoricoPagamento(models.Model):
    """Guarda o histórico de cada mensalidade paga individualmente"""
    assinatura = models.ForeignKey(AssinaturaMP, on_delete=models.CASCADE, related_name='pagamentos')
    payment_id = models.CharField(max_length=100, unique=True) # ID do pagamento no MP
    valor_pago = models.DecimalField(max_digits=10, decimal_places=2)
    data_pagamento = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Pagamento {self.payment_id} - R$ {self.valor_pago}"


class LogEmail(models.Model):
    STATUS_CHOICES = [
        ('Sucesso', 'Sucesso'),
        ('Erro', 'Erro'),
    ]
    
    destinatario = models.EmailField()
    assunto = models.CharField(max_length=255)
    corpo = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    erro_detalhe = models.TextField(blank=True, null=True)
    data_envio = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.data_envio.strftime('%d/%m/%Y %H:%M')} - {self.destinatario} - {self.status}"

    class Meta:
        verbose_name = "Log de E-mail"
        verbose_name_plural = "Logs de E-mail"
        ordering = ['-data_envio']
