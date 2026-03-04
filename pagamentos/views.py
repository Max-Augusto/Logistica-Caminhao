import os
from .models import HistoricoPagamento, AssinaturaMP, LogEmail
import mercadopago
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from logistica.models import Empresa # Certifique-se que o import aponta para o local correto
import logging
from django.utils import timezone
from datetime import timedelta
import traceback
import resend
from django.urls import reverse
from django.contrib.sites.models import Site

logger = logging.getLogger(__name__)

def gerar_pix_producao(request):
    import mercadopago
    sdk = mercadopago.SDK(os.getenv('MERCADO_PAGO_ACCESS_TOKEN'))

    payment_data = {
        "transaction_amount": 1.00,
        "description": "Validacao Sistema Logistica",
        "payment_method_id": "pix",
        "payer": {
            "email": "maxaugusto6474@gmail.com", # Use seu e-mail real aqui
            "first_name": "Max",
            "last_name": "Augusto",
            "identification": {
                "type": "CPF",
                "number": "16793059645" # COLOQUE SEU CPF REAL AQUI (Só números)
            }
        },
        "notification_url": request.build_absolute_uri(reverse('webhook_mp'))
    }

    payment_response = sdk.payment().create(payment_data)
    payment = payment_response["response"]

    # LOG PARA DEBUG (Ver no terminal se der erro de novo)
    if payment_response["status"] != 201:
        print(f"ERRO MP: {payment}")
        return render(request, 'pagamentos/erro.html', {'erro': payment})

    context = {
        'pix_copia_e_cola': payment['point_of_interaction']['transaction_data']['qr_code'],
        'qr_code_base64': payment['point_of_interaction']['transaction_data']['qr_code_base64'],
        'valor': 1.00
    }
    return render(request, 'pagamentos/pix_checkout.html', context)

@login_required
def central_assinatura(request):
    # 1. Acesso seguro ao perfil e empresa
    perfil = getattr(request.user, 'perfil', None)
    empresa = perfil.empresa if perfil else None
    
    # 2. SE A EMPRESA AINDA FOR NONE (mesmo com o login automático)
    # Redirecionamos para o onboarding ou criamos um fallback
    if not empresa:
        messages.warning(request, "Sua empresa está sendo configurada. Por favor, tente novamente em instantes.")
        return redirect('configurar_empresa')

    # 3. Agora é seguro acessar os métodos da empresa
    qtd_caminhoes = empresa.caminhoes.count()
    valor_mensal = empresa.calcular_valor_assinatura()
    
    # 4. Busca o token do settings
    token = getattr(settings, 'MERCADO_PAGO_ACCESS_TOKEN', "")
    link_pagamento = "#" 

    if token and token != "TOKEN_NAO_CONFIGURADO":
        try:
            sdk = mercadopago.SDK(token)
            
            # Configura a assinatura recorrente
            subscription_data = {
                "reason": f"Plano Profissional - {empresa.nome}",
                "auto_recurring": {
                    "frequency": 1,
                    "frequency_type": "months",
                    "transaction_amount": float(valor_mensal),
                    "currency_id": "BRL"
                },
                "back_url": request.build_absolute_uri(reverse('checar_perfil')),
                "notification_url": request.build_absolute_uri(reverse('webhook_mp')),
                "payer_email": request.user.email or "email_de_teste@gmail.com",
                "external_reference": str(empresa.id),
                "status": "pending"
            }

            result = sdk.preapproval().create(subscription_data)
            
            if result["status"] in [200, 201]:
                link_pagamento = result["response"].get("init_point")
            else:
                # Log do erro para debug mas sem travar a tela
                print(f"Erro MP: {result['status']} - {result['response']}")
                messages.error(request, "Não foi possível gerar o link de pagamento. Tente mais tarde.")
                
        except Exception as e:
            messages.error(request, f"Erro de conexão com o meio de pagamento: {e}")
    else:
        messages.warning(request, "Atenção: Sistema de pagamentos em manutenção.")

    context = {
        'empresa': empresa,
        'qtd_caminhoes': qtd_caminhoes,
        'valor_mensal': valor_mensal,
        'link_pagamento': link_pagamento,
        'em_dia': empresa.em_dia(), # Agora seguro pois empresa != None
    }
    return render(request, 'pagamentos/central.html', context)


def enviar_email_assinatura_ativa(empresa, valor="---", id_pagamento="---", email_cliente_pagante=None):
    """
    Envia e-mail de confirmação com template HTML profissional.
    O destinatário (to) é o cliente, e o administrador recebe BCC.
    """
    try:
        from logistica.models import PerfilUsuario
        admin_perfil = PerfilUsuario.objects.filter(empresa=empresa, e_administrador=True).first()
        
        # 1. Definir Destinatário Principal (TO): E-mail do Comprador
        # Prioridade 1: E-mail capturado diretamente do Mercado Pago (Pix/Card/Assinatura)
        # Prioridade 2: E-mail do administrador da empresa no sistema
        # Prioridade 3: E-mail de suporte (fallback de segurança)
        email_comprador = email_cliente_pagante
        if not email_comprador:
            email_comprador = admin_perfil.user.email if (admin_perfil and admin_perfil.user.email) else None
        
        if not email_comprador:
            email_comprador = "suporte@betimexpress.com.br" # Fallback caso nada seja encontrado

        print(f"DEBUG E-MAIL: Destinatário principal (email_comprador): {email_comprador}")
        print(f"DEBUG E-MAIL: email_cliente_pagante recebido: {email_cliente_pagante}")

        destinatarios = [email_comprador] # APENAS o comprador aqui
        
        # 2. Definir Cópia Oculta (BCC): E-mail do Vendedor/Administrador do Sistema
        email_vendedor = "maxaugusto6474@gmail.com"
        copia_oculta = [email_vendedor] # Vendedor APENAS no BCC

        print(f"DEBUG E-MAIL: BCC (email_vendedor): {copia_oculta}")
        print(f"Enviando para: {email_comprador}")
        
        nome_usuario = admin_perfil.user.get_full_name() or admin_perfil.user.username if admin_perfil else "Cliente"
        data_expiracao = empresa.teste_ate.strftime('%d/%m/%Y')
        
        current_site = Site.objects.get_current()
        link_dashboard = f"https://{current_site.domain}{reverse('selecionar_caminhao')}"
        
        assunto = f"🚛 Assinatura Ativa: {empresa.nome}"
        
        html_content = f"""
<div style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; border: 1px solid #eee; padding: 20px; border-radius: 8px;">
    <h2 style="color: #2c3e50; text-align: center;">🚛 Pagamento Confirmado!</h2>
    <p>Olá <strong>{nome_usuario}</strong>,</p>
    <p>Sua assinatura no <strong>Sistema Betim Express</strong> foi ativada com sucesso.</p>
    
    <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0;">
        <p style="margin: 5px 0;"><strong>ID do Pedido:</strong> #{id_pagamento}</p>
        <p style="margin: 5px 0;"><strong>Valor:</strong> R$ {valor}</p>
        <p style="margin: 5px 0;"><strong>Empresa:</strong> {empresa.nome}</p>
        <p style="margin: 5px 0;"><strong>Expira em:</strong> {data_expiracao}</p>
    </div>

    <div style="text-align: center; margin: 30px 0;">
        <a href="{link_dashboard}" style="background-color: #27ae60; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">Acessar Painel de Controle</a>
    </div>

    <p style="font-size: 14px; color: #7f8c8d;">Se você tiver qualquer dúvida, responda a este e-mail ou entre em contato com nosso suporte.</p>
    <hr style="border: 0; border-top: 1px solid #eee;">
    <p style="text-align: center; font-size: 12px; color: #bdc3c7;">Betim Express - Logística de Caminhão</p>
</div>
        """
        
        resend.api_key = settings.RESEND_API_KEY
        params = {
            "from": settings.DEFAULT_FROM_EMAIL,
            "to": destinatarios,
            "bcc": copia_oculta,
            "subject": assunto,
            "html": html_content,
        }
        resend.Emails.send(params)
        
        LogEmail.objects.create(
            destinatario=email_comprador,
            assunto=assunto,
            corpo=f"HTML enviado para {email_comprador}",
            status='Sucesso'
        )
        return True
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        return False

@csrf_exempt
def webhook_mercadopago(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            resource_id = data.get('data', {}).get('id')
            # O MP costuma enviar 'type', mas é bom garantir
            topic = data.get('type') or data.get('action') 

            # Usando o Token correto que configuramos
            sdk = mercadopago.SDK(settings.MERCADO_PAGO_ACCESS_TOKEN)

            # 1. LÓGICA DE FATURAS (PAGAMENTOS INDIVIDUAIS)
            if topic == 'payment':
                res = sdk.payment().get(resource_id)
                if res["status"] in [200, 201]:
                    pagamento_mp = res["response"]
                    empresa_id = pagamento_mp.get("external_reference")
                    
                    if empresa_id and pagamento_mp.get("status") == "approved":
                        try:
                            empresa = Empresa.objects.get(id=int(empresa_id))
                            empresa.assinatura_ativa = True
                            empresa.teste_ate = timezone.now() + timedelta(days=30)
                            empresa.save()
                            assinatura_mp = getattr(empresa, 'assinatura_detalhes', None)
                            print(f"WEBHOOK: Empresa {empresa.nome} ativada e data estendida até {empresa.teste_ate}")
                            
                            # --- DISPARO DE E-MAIL ---
                            valor_pago = pagamento_mp.get("transaction_amount", 0)
                            email_mp = pagamento_mp.get("payer", {}).get("email")
                            enviar_email_assinatura_ativa(empresa, valor=f"{float(valor_pago):.2f}", id_pagamento=str(resource_id), email_cliente_pagante=email_mp)
                            
                            
                            if assinatura_mp:
                                HistoricoPagamento.objects.get_or_create(
                                    payment_id=str(resource_id),
                                    defaults={
                                        'assinatura': assinatura_mp,
                                        'valor_pago': pagamento_mp.get("transaction_amount"),
                                    }
                                )
                        except (Empresa.DoesNotExist, ValueError):
                            print(f"Empresa ID {empresa_id} não encontrada no pagamento.")

            # 2. LÓGICA de STATUS DA ASSINATURA (Sincronização Automática)
            elif topic in ['subscription', 'preapproval', 'preapproval_plan', 'subscription_preapproval', 'subscription_authorized']:
                res = sdk.preapproval().get(resource_id)
                if res["status"] in [200, 201]:
                    dados_assinatura = res["response"]
                    empresa_id = dados_assinatura.get("external_reference")
                    status = dados_assinatura.get("status")

                    if empresa_id:
                        try:
                            empresa = Empresa.objects.get(id=int(empresa_id))
                            
                            # Atualiza o booleano na Empresa
                            if status == "authorized":
                                empresa.assinatura_ativa = True
                                # Garante que ao autorizar a assinatura, o prazo seja renovado
                                empresa.teste_ate = timezone.now() + timedelta(days=30)
                                # --- DISPARO DE E-MAIL (Sincronização) ---
                                valor_assinatura = dados_assinatura.get('auto_recurring', {}).get('transaction_amount', 0)
                                email_assinante = dados_assinatura.get('payer', {}).get('email') or dados_assinatura.get('payer_email')
                                enviar_email_assinatura_ativa(empresa, valor=f"{float(valor_assinatura):.2f}", id_pagamento=str(resource_id), email_cliente_pagante=email_assinante)
                            elif status in ["cancelled", "paused"]:
                                empresa.assinatura_ativa = False
                            empresa.save()

                            # ATUALIZA OU CRIA OS DETALHES DA ASSINATURA NO BANCO
                            # Isso evita o erro de "Assinatura não encontrada" futuramente
                            AssinaturaMP.objects.update_or_create(
                                empresa=empresa,  # Critério de busca
                                defaults={
                                    'preapproval_id': resource_id,
                                    'status': status,
                                    'valor_atual': dados_assinatura.get('auto_recurring', {}).get('transaction_amount', 0),
                                }
                            )
                            print(f"Assinatura sincronizada: Empresa {empresa.nome} -> {status}")

                        except (Empresa.DoesNotExist, ValueError):
                            print(f"Empresa ID {empresa_id} não encontrada na assinatura.")

        except Exception as e:
            print(f"ERRO CRÍTICO NO WEBHOOK: {e}")
            traceback.print_exc() # Isso mostra a linha exata no log da Railway
        
        # O Mercado Pago exige um retorno 200 ou 201 para não ficar reenviando o aviso
        return HttpResponse(status=200)
        
    return HttpResponse(status=400)

@login_required
def listar_faturas(request):
    empresa = request.user.perfil.empresa
    # Buscamos os pagamentos através da assinatura vinculada à empresa
    faturas = HistoricoPagamento.objects.filter(
        assinatura__empresa=empresa
    ).order_by('-data_pagamento')
    
    return render(request, 'pagamentos/faturas.html', {'faturas': faturas})

@login_required
def cancelar_assinatura(request):
    if request.method == "POST":
        perfil = getattr(request.user, 'perfil', None)
        empresa = perfil.empresa if perfil else None
        
        if not empresa:
            return redirect('central_assinatura')

        assinatura_mp = getattr(empresa, 'assinatura_detalhes', None)

        # Se existe um ID do Mercado Pago, tentamos cancelar lá
        if assinatura_mp and assinatura_mp.preapproval_id:
            try:
                sdk = mercadopago.SDK(settings.MERCADO_PAGO_ACCESS_TOKEN)
                result = sdk.preapproval().update(assinatura_mp.preapproval_id, {"status": "cancelled"})
                
                # Se a API confirmou o cancelamento
                if result["status"] in [200, 201]:
                    messages.success(request, "Assinatura cancelada no Mercado Pago com sucesso.")
                else:
                    # Se a API falhou (ex: ID não encontrado ou já cancelado no painel do MP)
                    # Ainda desativamos aqui para liberar o usuário
                    messages.warning(request, "A assinatura foi removida do sistema, mas não conseguimos confirmar o cancelamento automático no Mercado Pago. Verifique seu painel do MP.")
                
                # Atualização Local Obrigatória (Independente do sucesso da API)
                assinatura_mp.status = 'cancelled'
                assinatura_mp.save()
            except Exception as e:
                messages.error(request, f"Erro de conexão: {e}. Desativando apenas localmente.")

        # Desativa o acesso da empresa no Django
        if empresa.assinatura_ativa:
            empresa.assinatura_ativa = False
            empresa.save()
            if not messages.get_messages(request): # Evita duplicar mensagens
                messages.success(request, "Assinatura desativada no sistema.")
        
    return redirect('central_assinatura')
