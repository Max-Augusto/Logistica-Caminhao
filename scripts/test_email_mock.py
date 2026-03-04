import os
import django
import sys

# Adiciona o diretório base ao sys.path para o Django encontrar as configurações
sys.path.append(os.getcwd())

# Configura o ambiente Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings

def test_send_email():
    destinatario = 'renatosanches9293@gmail.com'
    assunto = 'Teste de Entrega - Sistema Betim Express'
    mensagem = 'Este é um teste de e-mail mock para validar a entrega via Resend e Anymail.'
    html_mensagem = f"""
    <div style="font-family: Arial, sans-serif; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
        <h2 style="color: #27ae60;">Teste de Entrega Real</h2>
        <p>Olá,</p>
        <p>Este e-mail foi disparado para validar a entrega no endereço: <strong>{destinatario}</strong>.</p>
        <p>Por favor, ignore se este e-mail chegar à sua caixa de entrada.</p>
        <hr>
        <p style="font-size: 12px; color: #777;">Enviado via Resend API.</p>
    </div>
    """

    print(f"Iniciando envio de e-mail para: {destinatario}...")
    try:
        resultado = send_mail(
            subject=assunto,
            message=mensagem,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[destinatario],
            html_message=html_mensagem,
            fail_silently=False,
        )
        print(f"Envio concluído. Resultado: {resultado} (1 significa sucesso)")
        print(f"Verifique o console da Railway para o status 200 do Resend.")
    except Exception as e:
        print(f"ERRO ao enviar e-mail: {e}")

if __name__ == "__main__":
    test_send_email()
