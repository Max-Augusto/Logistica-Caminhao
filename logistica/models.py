from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

# Função auxiliar para o cálculo do Trial
def tres_dias_depois():
    return timezone.now() + timedelta(days=3)

import datetime
from django.utils import timezone
from django.db import models

class Empresa(models.Model):
    nome = models.CharField(max_length=100)
    data_cadastro = models.DateTimeField(auto_now_add=True)
    teste_ate = models.DateTimeField(default=tres_dias_depois)
    limite_veiculos = models.IntegerField(default=2)
    assinatura_ativa = models.BooleanField(default=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Se o dado vier do banco como 'date', converte para 'datetime' aware na hora
        if isinstance(self.teste_ate, datetime.date) and not isinstance(self.teste_ate, datetime.datetime):
            self.teste_ate = timezone.make_aware(datetime.datetime.combine(self.teste_ate, datetime.time.min))

    def save(self, *args, **kwargs):
        # Garante que nunca salve um objeto 'date' puro em um DateTimeField
        if isinstance(self.teste_ate, datetime.date) and not isinstance(self.teste_ate, datetime.datetime):
            self.teste_ate = timezone.make_aware(datetime.datetime.combine(self.teste_ate, datetime.time.min))
        super().save(*args, **kwargs)

    def em_dia(self):
        """Verifica acesso. Agora self.teste_ate já está garantido pelo __init__"""
        return timezone.now() <= self.teste_ate or self.assinatura_ativa

    def calcular_valor_assinatura(self):
        qtd_caminhoes = self.caminhoes.count() 
        base_preco = Decimal('50.00')
        if qtd_caminhoes <= 2:
            return base_preco
        extras = qtd_caminhoes - 2
        return base_preco + (Decimal(extras) * Decimal('15.00'))

    def __str__(self):
        return self.nome

class PerfilUsuario(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, null=True, blank=True)
    e_administrador = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username

class Caminhao(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='caminhoes')
    placa = models.CharField(max_length=10, unique=True, verbose_name="Placa")
    modelo = models.CharField(max_length=100, verbose_name="Modelo/Cor")
    motorista_responsavel = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="caminhao")
    
    # CAMPO DE COMISSÃO ADICIONADO AQUI
    comissao_percentual = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=13.00, 
        verbose_name="Comissão (%)"
    )

    def __str__(self):
        return f"{self.placa} - {self.modelo}"

class Viagem(models.Model):
    caminhao = models.ForeignKey(Caminhao, on_delete=models.CASCADE, related_name="viagens", null=True, blank=True)
    data = models.DateField(verbose_name="Data da Viagem")
    rota = models.CharField(max_length=255, verbose_name="Rota / Produto")
    valor_frete = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor do Frete")
    motorista = models.CharField(max_length=100, verbose_name="Motorista", default="//")

    class Meta:
        indexes = [
            models.Index(fields=['caminhao', 'data']),
            models.Index(fields=['data']),
        ]
        ordering = ['-data', '-id']

    def __str__(self):
        return f"{self.data} - {self.rota}"

class Despesa(models.Model):
    caminhao = models.ForeignKey(Caminhao, on_delete=models.CASCADE, related_name="despesas", null=True, blank=True)
    CATEGORIA_CHOICES = [
        ('abastecimento', 'Abastecimento'),
        ('comissao', 'Comissão'),
        ('manutencao', 'Manutenção'),
        ('outro', 'Outro'),
    ]
    
    viagem_origem = models.ForeignKey(Viagem, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Viagem Relacionada")
    data = models.DateField()
    descricao = models.CharField(max_length=255)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES)
    
    km_atual = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    litros = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    class Meta:
        ordering = ['-data', '-km_atual']  # Ordenação por data e KM
        indexes = [
            models.Index(fields=['caminhao', 'data']),
            models.Index(fields=['data']),
        ]

    def __str__(self):
        return f"{self.descricao} - R$ {self.valor}"

# LÓGICA DE AUTOMAÇÃO DA COMISSÃO
@receiver(post_save, sender=Viagem)
def gerenciar_comissao_automatica(sender, instance, created, **kwargs):
    if instance.caminhao:
        percentual = instance.caminhao.comissao_percentual
        valor_calculado = (instance.valor_frete * percentual) / 100

        # FIX: Usar update_or_create para evitar duplicação em caso de re-save ou race condition
        Despesa.objects.update_or_create(
            viagem_origem=instance,
            categoria='comissao',
            defaults={
                'caminhao': instance.caminhao,
                'data': instance.data,
                'descricao': instance.rota,
                'valor': valor_calculado
            }
        )

# @receiver(post_save, sender=User)
# def garantir_perfil_usuario(sender, instance, created, **kwargs):
#     if created:
#         # Se o perfil já existe (ex: criado via motorista_create), não faz nada
#         if hasattr(instance, 'perfil'):
#             return
# 
#         # APENAS criamos o PerfilUsuario, SEM criar uma Empresa.
#         # O campo 'empresa' no seu model PerfilUsuario deve aceitar null=True
#         # para que o usuário possa logar e depois escolher a empresa na sua View.
#         PerfilUsuario.objects.get_or_create(
#             user=instance,
#             defaults={'e_administrador': True} 
#         )