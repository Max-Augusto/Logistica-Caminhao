from django.test import TestCase, Client
from django.contrib.auth.models import User
from logistica.models import Empresa, Caminhao, Viagem, Despesa, PerfilUsuario
from pagamentos.models import LogEmail
from datetime import date
from decimal import Decimal
import json
from unittest.mock import patch

class PagamentosFunctionalTest(TestCase):
    def setUp(self):
        # Setup básico: Empresa, User Admin, Caminhão
        self.empresa = Empresa.objects.create(nome="Transportadora Teste")
        self.user = User.objects.create_user(username="admin_teste", email="teste@empresa.com", password="123")
        self.perfil = PerfilUsuario.objects.create(user=self.user, empresa=self.empresa, e_administrador=True)
        
        self.caminhao = Caminhao.objects.create(
            empresa=self.empresa,
            placa="GOL-1234",
            modelo="Scania R450",
            comissao_percentual=Decimal('10.00'), # 10%
        )
        
        self.client = Client()

    def test_idempotencia_comissao(self):
        """ Teste se salvar a mesma viagem 2x gera apenas 1 despesa de comissão """
        viagem = Viagem(
            caminhao=self.caminhao,
            data=date(2025, 2, 1),
            rota="SP x RJ",
            valor_frete=Decimal('2000.00'),
            motorista="João da Silva"
        )
        viagem.save() # Primeiro Salvamento
        
        # Verifica se criou 1 comissão
        qtd_comissoes = Despesa.objects.filter(viagem_origem=viagem, categoria='comissao').count()
        self.assertEqual(qtd_comissoes, 1, "Deveria ter criado exatamente 1 comissão")
        
        # Segundo Salvamento (Simulando Update ou Race Condition)
        viagem.save() 
        qtd_comissoes_pos = Despesa.objects.filter(viagem_origem=viagem, categoria='comissao').count()
        self.assertEqual(qtd_comissoes_pos, 1, "Mesmo após salvar novamente, deve manter apenas 1 comissão")

    def test_calculo_exato_comissao(self):
        """ Teste se o valor da comissão é exatamente o percentual do caminhão """
        viagem = Viagem.objects.create(
            caminhao=self.caminhao,
            data=date(2025, 2, 5),
            rota="Curitiba x SP",
            valor_frete=Decimal('5000.00'),
            motorista="Pedro"
        )
        
        comissao = Despesa.objects.get(viagem_origem=viagem, categoria='comissao')
        valor_esperado = Decimal('5000.00') * Decimal('0.10') # 500.00
        
        self.assertEqual(comissao.valor, valor_esperado, f"Comissão deve ser {valor_esperado}")

    @patch('mercadopago.SDK')
    @patch('django.core.mail.send_mail')
    def test_log_email_webhook(self, mock_send_mail, mock_sdk):
        """ Simula o Webhook de pagamento Aprovado e verifica se cria LogEmail """
        
        # Mock do SDK do Mercado Pago para retornar pagamento aprovado
        mock_payment_instance = mock_sdk.return_value.payment.return_value
        mock_payment_instance.get.return_value = {
            "status": 200,
            "response": {
                "status": "approved",
                "external_reference": str(self.empresa.id),
                "transaction_amount": 100.00
            }
        }

        # Payload simulado do Webhook
        payload = {
            "type": "payment",
            "data": {"id": "123456789"}
        }

        response = self.client.post(
            '/pagamentos/webhook/',
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        
        # Verifica se o LogEmail foi criado com Sucesso
        log = LogEmail.objects.filter(destinatario=self.user.email).last()
        self.assertIsNotNone(log, "LogEmail deveria ter sido criado")
        self.assertEqual(log.status, 'Sucesso', "Status do log deveria ser Sucesso")
        self.assertIn("Bem-vindo", log.assunto)
