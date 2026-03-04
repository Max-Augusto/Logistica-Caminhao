from django.test import TestCase
from django.contrib.auth.models import User
from logistica.models import Empresa, Caminhao, Viagem, Despesa
from logistica.forms import DespesaForm
from datetime import date
from decimal import Decimal

class LogisticaBusinessLogicTest(TestCase):
    def setUp(self):
        # Setup básico: Empresa, User, Caminhão
        self.empresa = Empresa.objects.create(nome="Empresa Teste")
        self.user = User.objects.create_user(username="motorista", password="123")
        self.caminhao = Caminhao.objects.create(
            empresa=self.empresa,
            placa="TEST-9999",
            modelo="Volvo FH",
            comissao_percentual=Decimal('10.00'),
            motorista_responsavel=self.user
        )

    def test_calculo_comissao_automatico(self):
        """Teste se a comissão é gerada automaticamente ao criar Viagem"""
        viagem = Viagem.objects.create(
            caminhao=self.caminhao,
            data=date(2025, 1, 1),
            rota="SP x BH",
            valor_frete=Decimal('1000.00'),
            motorista="João"
        )
        
        # Verifica se criou a despesa de comissão
        comissao = Despesa.objects.filter(viagem_origem=viagem, categoria='comissao').first()
        self.assertIsNotNone(comissao)
        self.assertEqual(comissao.valor, Decimal('100.00')) # 10% de 1000

    def test_validacao_km_decrescente(self):
        """Teste se o Form impede lançar KM menor que o anterior"""
        # 1. Cria um abastecimento antigo com KM 1000
        Despesa.objects.create(
            caminhao=self.caminhao,
            categoria='abastecimento',
            data=date(2025, 1, 1),
            km_atual=Decimal('1000'),
            valor=Decimal('500'),
            descricao='Diesel'
        )

        # 2. Tenta lançar KM 900 no dia seguinte (deve falhar)
        form_data = {
            'caminhao': self.caminhao.id,
            'data': date(2025, 1, 2),
            'categoria': 'abastecimento',
            'km_atual': 900, # INVÁLIDO (Menor que 1000)
            'valor': 200,
            'litros': 50
        }
        
        form = DespesaForm(data=form_data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('km_atual', form.errors)
