from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Q
from django.db.models.functions import ExtractMonth, ExtractYear, Lower
from decimal import Decimal
from .models import Viagem, Despesa, Caminhao, PerfilUsuario, Empresa
from .forms import ViagemForm, DespesaForm
from django.utils import timezone
from django.contrib import messages
from io import BytesIO
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.db.models import Min, Max
from .forms import AdicionarCaminhaoForm, EditarCaminhaoForm
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from pagamentos.decorators import check_assinatura
from django.db import IntegrityError, transaction

# Variável Global para evitar repetição e erros de digitação
LISTA_MESES = ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']

def obter_dados_financeiros(caminhao, mes, ano):
    """Função auxiliar para centralizar os cálculos financeiros"""
    viagens = Viagem.objects.filter(caminhao=caminhao, data__month=mes, data__year=ano).distinct()
    # REMOVIDO .distinct() daqui para igualar ao Card de Resumo (que não usa distinct e mostra o valor correto).
    # Como filtro é direto na tabela Despesa, não deve haver duplicação por Joins.
    todas_despesas = Despesa.objects.filter(caminhao=caminhao, data__month=mes, data__year=ano)

    # Agregados
    total_fretes = viagens.aggregate(Sum('valor_frete'))['valor_frete__sum'] or Decimal('0')
    
    # --- CÁLCULO EXPLÍCITO (Igual ao Card) ---
    # Garante que Abastecimento e Comissão batam 100% com o resumo
    total_abastecimento = todas_despesas.filter(categoria__iexact='abastecimento').aggregate(Sum('valor'))['valor__sum'] or Decimal('0')
    total_comissao = todas_despesas.filter(categoria__iexact='comissao').aggregate(Sum('valor'))['valor__sum'] or Decimal('0')
    
    # Para as outras categorias (manutenção, outro, etc), usamos o agrupamento padrão
    outras_cats = todas_despesas.exclude(Q(categoria__iexact='abastecimento') | Q(categoria__iexact='comissao')) \
                                .annotate(cat_lower=Lower('categoria')) \
                                .values('cat_lower') \
                                .annotate(total=Sum('valor'))
                                
    dados_dict = {}
    if total_abastecimento > 0:
        dados_dict['abastecimento'] = total_abastecimento
    if total_comissao > 0:
        dados_dict['comissao'] = total_comissao
        
    for item in outras_cats:
        # Safeguard: ensure category name is string and valid
        cat_name = item['cat_lower'] or 'outros'
        val_total = item['total'] or Decimal('0')
        dados_dict[cat_name] = val_total

    # Totais Gerais
    # Despesas operacionais = Tudo menos comissão
    total_despesas_operacionais = total_abastecimento + sum((item['total'] or Decimal('0')) for item in outras_cats)
    
    total_saidas = total_comissao + total_despesas_operacionais
    sobra = total_fretes - total_saidas

    return {
        'viagens': viagens.select_related('caminhao').order_by('-data', '-id'),
        'todas_despesas': todas_despesas.select_related('viagem_origem').order_by('-data', '-km_atual'),
        'total_fretes': total_fretes,
        'total_comissao': total_comissao,
        'outras_despesas': total_despesas_operacionais, # Isso agora inclui 'abastecimento', 'manutencao', 'outro', etc
        'total_saidas': total_saidas,
        'sobra': sobra,
        'dados_grafico': dados_dict 
    }

# ==========================================
# VERIFICAÇÃO DE ASSINATURA
# ==========================================

@login_required
@check_assinatura
def dashboard_logistica(request):
    # Se a empresa não estiver "em dia", o decorator vai 
    # redirecionar automaticamente para a página de assinatura.
    return render(request, 'logistica/dashboard.html')

# ==========================================
# CRIAR EMPRESA
# ==========================================

@login_required
def checar_perfil(request):
    # 1. Sincroniza o banco
    request.user.refresh_from_db()

    # 2. Prioridade 1: Motorista vinculado a um Caminhão (Hierarquia solicitada)
    caminhao = getattr(request.user, 'caminhao', None)
    if caminhao and caminhao.empresa:
        # Se o caminhão tem empresa, usamos o status dela
        if not caminhao.empresa.em_dia():
            return redirect('central_assinatura')
        return redirect('home_motorista')

    # 3. Prioridade 2: Administrador (Dono) com Empresa no Perfil
    perfil = getattr(request.user, 'perfil', None)
    if perfil and perfil.e_administrador and perfil.empresa:
        if not perfil.empresa.em_dia():
            return redirect('central_assinatura')
        return redirect('selecionar_caminhao')

    # 4. Se não tem caminhão vinculado E não é admin com empresa -> Bloqueia
    return render(request, 'logistica/sem_empresa.html')

@login_required
def configurar_empresa(request):
    # Se o usuário já tem perfil E empresa, manda direto para os caminhões
    if hasattr(request.user, 'perfil') and request.user.perfil.empresa:
        return redirect('selecionar_caminhao')

    if request.method == 'POST':
        nome_da_empresa = request.POST.get('nome_empresa')
        
        if nome_da_empresa:
            # 1. Busca a empresa (Não cria mais automaticamente)
            try:
                nova_empresa = Empresa.objects.get(nome=nome_da_empresa)
            except Empresa.DoesNotExist:
                messages.error(request, f"Empresa {nome_da_empresa} não encontrada. Contate o suporte.")
                return render(request, 'logistica/configurar_empresa.html')
            
            # 2. Atualiza o perfil criado pelo Signal
            perfil, created = PerfilUsuario.objects.get_or_create(user=request.user)
            perfil.empresa = nova_empresa
            perfil.e_administrador = True
            perfil.save()
        
            messages.success(request, f"Empresa {nova_empresa.nome} criada com sucesso!")
            # Redireciona para a lista de caminhões (admin)
            return redirect('selecionar_caminhao')

    return render(request, 'logistica/configurar_empresa.html')


# ==========================================
# VERIFICAÇÕES DE ACESSO
# ==========================================

def e_admin_empresa(user):
    """ Verifica se o utilizador é administrador da empresa no perfil """
    return user.is_authenticated and (
        user.is_superuser or 
        (hasattr(user, 'perfil') and user.perfil.e_administrador)
    )

# ==========================================
# ADICIONAR CAMINHÃO
# ==========================================

from django.db import transaction, IntegrityError

@login_required
@user_passes_test(e_admin_empresa)
def adicionar_caminhao(request):
    perfil_admin = request.user.perfil
    empresa = perfil_admin.empresa

    if request.method == 'POST':
        form = AdicionarCaminhaoForm(request.POST)
        if form.is_valid():
            # Pegamos a placa e transformamos em maiúsculas para o login
            placa = form.cleaned_data['placa'].upper()
            senha = form.cleaned_data['senha_motorista']

            try:
                with transaction.atomic():
                    # 1. O USERNAME AGORA É A PLACA
                    user_motorista = User.objects.create_user(
                        username=placa, 
                        password=senha
                    )

                    # 2. Criamos o perfil vinculado
                    PerfilUsuario.objects.create(
                        user=user_motorista,
                        empresa=empresa,
                        e_administrador=False
                    )

                    # 3. Criamos o caminhão vinculando o usuário criado
                    caminhao = form.save(commit=False)
                    caminhao.empresa = empresa
                    caminhao.motorista_responsavel = user_motorista
                    caminhao.placa = placa # Garante que a placa salva é a mesma do user
                    caminhao.save()

                messages.success(request, f"Motorista cadastrado! Login: {placa}")
                return redirect('selecionar_caminhao')

            except IntegrityError:
                messages.error(request, f"A placa {placa} já está cadastrada no sistema.")
    
    else:
        form = AdicionarCaminhaoForm()
    
    return render(request, 'logistica/form_caminhao.html', {'form': form})

@login_required
@user_passes_test(e_admin_empresa)
def editar_caminhao(request, caminhao_id):
    caminhao = get_object_or_404(Caminhao, id=caminhao_id, empresa=request.user.perfil.empresa)
    
    if request.method == 'POST':
        form = EditarCaminhaoForm(request.POST, instance=caminhao)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # 1. Captura a nova placa (limpa e em maiúsculo)
                    nova_placa = form.cleaned_data['placa'].upper()
                    
                    # 2. Se a placa mudou, atualiza o USERNAME do motorista
                    motorista = caminhao.motorista_responsavel
                    if motorista and motorista.username != nova_placa:
                        motorista.username = nova_placa
                        motorista.save()

                    # 3. Processa troca de senha (se houver)
                    nova_senha = request.POST.get('nova_senha_motorista')
                    if nova_senha and nova_senha.strip():
                        motorista.set_password(nova_senha)
                        motorista.save()

                    # 4. Salva o caminhão com a nova placa
                    caminhao = form.save()
                
                messages.success(request, "Dados e login atualizados com sucesso!")
                return redirect('selecionar_caminhao')

            except IntegrityError:
                messages.error(request, "Erro: Esta nova placa já está em uso por outro caminhão.")
    else:
        form = EditarCaminhaoForm(instance=caminhao)
    
    return render(request, 'logistica/form_caminhao.html', {
        'form': form, 
        'titulo': f'Editar Caminhão: {caminhao.placa}',
        'caminhao': caminhao 
    })

@login_required
@user_passes_test(e_admin_empresa)
def excluir_caminhao(request, caminhao_id):
    caminhao = get_object_or_404(Caminhao, id=caminhao_id, empresa=request.user.perfil.empresa)
    
    if request.method == 'POST':
        senha = request.POST.get('senha_confirmacao')
        # Autentica o admin que está logado
        from django.contrib.auth import authenticate
        user = authenticate(username=request.user.username, password=senha)
        
        if user:
            # Se o motorista for um User vinculado, deletamos ele também
            if caminhao.motorista_responsavel:
                caminhao.motorista_responsavel.delete()
            caminhao.delete()
            return redirect('selecionar_caminhao')
        else:
            messages.error(request, "Senha incorreta! O caminhão não foi excluído.")
            return redirect('editar_caminhao', caminhao_id=caminhao.id)

    # Passamos 'obj' e 'tipo' para o template
    return render(request, 'logistica/confirmar_exclusao.html', {
        'obj': caminhao, 
        'tipo': 'caminhao'
    })

# ==========================================
# ÁREA DO MOTORISTA
# ==========================================

@login_required
def home_motorista(request):
    caminhao = getattr(request.user, 'caminhao', None)
    if not caminhao and not request.user.is_superuser:
        return render(request, 'logistica/home_motorista.html', {
            'erro': 'O seu utilizador não está vinculado a nenhum camião.'
        })
    return render(request, 'logistica/home_motorista.html', {'caminhao': caminhao})

@login_required
def registrar_despesa(request):
    tipo = request.GET.get('tipo', 'outro')
    titulo_exibicao = "Abastecimento" if tipo == 'abastecimento' else "Despesa"

    if request.method == 'POST':
        form = DespesaForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                despesa = form.save(commit=False)
                despesa.categoria = tipo
                
                # FIX: Removemos a lógica manual que sobrescrevia o caminhão.
                # O form.save() já pega o caminhão do cleaned_data, respeitando o form.
                # despesa.caminhao já está preenchido corretamente pelo ModelForm.

                # 2. Processamento de Abastecimento (Descrição e KM)
                if tipo == 'abastecimento':
                    # A validação de consistência (KM vs Data) agora é feita exclusivamente
                    # no form.clean_km_atual(), evitando duplicação de lógica.
                    km_digitado = form.cleaned_data.get('km_atual') or 0
                    litros_digitados = form.cleaned_data.get('litros') or 0
                    
                    despesa.km_atual = km_digitado
                    despesa.litros = litros_digitados
                    
                    if km_digitado > 0:
                        km_formatado = f"{km_digitado:g}".replace('.', ',')
                        despesa.descricao = f"Abastecimento - KM {km_formatado}"
                    else:
                        despesa.descricao = "Abastecimento - KM não informado"

                despesa.save()
                
                messages.success(request, f"{titulo_exibicao} registrado com sucesso!")
                return redirect('home_motorista')
                
            except Exception as e:
                # Caso ocorra erro de banco ou outro inesperado
                messages.error(request, f"Erro ao salvar registro: {e}")
                # Não redireciona, renderiza o form novamente com dados e erro
    else:
        hoje = timezone.localtime(timezone.now()).date()
        form = DespesaForm(user=request.user, initial={'data': hoje})
        
    return render(request, 'logistica/form_registro.html', {
        'form': form, 'tipo': tipo, 'titulo': titulo_exibicao
    })

@login_required
def registrar_viagem(request):
    # Definimos o form como None ou garantimos que ele seja criado em ambos os casos
    if request.method == 'POST':
        form = ViagemForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                viagem = form.save(commit=False)
                # FIX: Removemos a lógica manual. O motorista só vê seu próprio caminhão no form (queryset),
                # então o form.cleaned_data já traz o caminhão correto.
                
                viagem.save()
                messages.success(request, "Viagem registrada com sucesso!")
                return redirect('home_motorista')
            
            except Exception as e:
                messages.error(request, f"Erro ao salvar viagem: {e}")
        # Se o form NÃO for válido, ele cai aqui e desce para o render com os erros
    else:
        # Caminho para o método GET (quando você apenas abre a página)
        data_hoje = timezone.localtime(timezone.now()).date()
        form = ViagemForm(user=request.user, initial={'data': data_hoje})
        
    # Esta linha DEVE estar fora dos blocos 'if' para que 'form' sempre exista
    return render(request, 'logistica/form_viagem.html', {
        'form': form,
    })

@login_required
def escolher_tipo_despesa(request):
    return render(request, 'logistica/escolher_tipo_despesa.html')

# ==========================================
# ÁREA DO ADMINISTRADOR
# ==========================================

@login_required
@login_required
# REMOVIDO @user_passes_test(e_admin_empresa) para permitir o redirecionamento customizado abaixo
@check_assinatura
def selecionar_caminhao(request):
    # Trava de Segurança: Se não for admin, chuta para a home do motorista
    if not e_admin_empresa(request.user):
        return redirect('home_motorista')

    empresa_usuario = request.user.perfil.empresa
    caminhoes = Caminhao.objects.filter(empresa=empresa_usuario).select_related('empresa', 'motorista_responsavel')
    return render(request, 'logistica/selecionar_caminhao.html', {'caminhoes': caminhoes})

@login_required
@user_passes_test(e_admin_empresa)
def selecao_ano(request, caminhao_id):
    empresa_usuario = request.user.perfil.empresa
    caminhao = get_object_or_404(Caminhao.objects.select_related('empresa'), id=caminhao_id, empresa=empresa_usuario)
    
    # BUSCA TODOS OS CAMINHÕES PARA O SELETOR
    caminhoes_selector = Caminhao.objects.filter(empresa=empresa_usuario)

    anos_viagens = Viagem.objects.filter(caminhao=caminhao).annotate(ano_ref=ExtractYear('data')).values_list('ano_ref', flat=True).distinct()
    anos_despesas = Despesa.objects.filter(caminhao=caminhao).annotate(ano_ref=ExtractYear('data')).values_list('ano_ref', flat=True).distinct()

    todos_anos = sorted(list(set(anos_viagens) | set(anos_despesas)), reverse=True)
    dados_anos = []
    for ano_num in todos_anos:
        if ano_num:
            frete_total = Viagem.objects.filter(caminhao=caminhao, data__year=ano_num).aggregate(Sum('valor_frete'))['valor_frete__sum'] or Decimal('0')
            saidas_total = Despesa.objects.filter(caminhao=caminhao, data__year=ano_num).aggregate(Sum('valor'))['valor__sum'] or Decimal('0')
            dados_anos.append({
                'ano': ano_num, 'frete': frete_total, 'saidas': saidas_total, 'sobra': frete_total - saidas_total
            })
            
    # ADICIONE 'caminhoes_selector' NO DICIONÁRIO DE RETORNO
    return render(request, 'logistica/selecao_ano.html', {
        'dados_anos': dados_anos, 
        'caminhao': caminhao,
        'caminhoes_selector': caminhoes_selector
    })

@login_required
@user_passes_test(e_admin_empresa)
def selecao_mes(request, caminhao_id, ano):
    empresa_usuario = request.user.perfil.empresa
    caminhao = get_object_or_404(Caminhao.objects.select_related('empresa'), id=caminhao_id, empresa=empresa_usuario)

    # Busca os caminhões
    caminhoes_selector = Caminhao.objects.filter(empresa=empresa_usuario)
    
    viagens_meses = Viagem.objects.filter(caminhao=caminhao, data__year=ano).annotate(m=ExtractMonth('data')).values_list('m', flat=True).distinct()
    despesas_meses = Despesa.objects.filter(caminhao=caminhao, data__year=ano).annotate(m=ExtractMonth('data')).values_list('m', flat=True).distinct()
    meses_com_dados = sorted(list(set(viagens_meses) | set(despesas_meses)))

    dados_meses = []
    for m_num in meses_com_dados:
        if m_num:
            frete = Viagem.objects.filter(caminhao=caminhao, data__month=m_num, data__year=ano).aggregate(Sum('valor_frete'))['valor_frete__sum'] or Decimal('0')
            saidas = Despesa.objects.filter(caminhao=caminhao, data__month=m_num, data__year=ano).aggregate(Sum('valor'))['valor__sum'] or Decimal('0')
            dados_meses.append({
                'mes_num': m_num, 
                'ano': ano, 
                'mes_nome': LISTA_MESES[m_num], 
                'frete': frete, 
                'saidas': saidas, 
                'sobra': frete - saidas,
            })
    
    # Contexto corrigido: caminhoes_selector agora está na raiz
    return render(request, 'logistica/selecao_mes.html', {
        'dados_meses': dados_meses, 
        'ano_selecionado': ano, 
        'caminhao': caminhao,
        'caminhoes_selector': caminhoes_selector # ADICIONADO AQUI
    })

@login_required
@user_passes_test(e_admin_empresa)
@check_assinatura
def dashboard_detalhado(request, caminhao_id, mes, ano):
    empresa_usuario = request.user.perfil.empresa
    caminhao = get_object_or_404(Caminhao, id=caminhao_id, empresa=empresa_usuario)
    
    # 1. Cálculos financeiros
    financeiro = obter_dados_financeiros(caminhao, mes, ano)

    # 2. Cálculos do Trial (Período de teste)
    prazo = empresa_usuario.teste_ate
    agora = timezone.now()
    dias_restantes = (prazo - agora).days
    aviso_trial = dias_restantes if dias_restantes >= 0 else 0

    # 3. Montagem do dicionário de contexto (Tudo junto aqui)
    context = {
        'caminhoes_selector': Caminhao.objects.filter(empresa=empresa_usuario),
        'caminhao': caminhao,
        'viagens': financeiro['viagens'],
        'comissoes': financeiro['todas_despesas'].filter(categoria__iexact='comissao'),
        'despesas_operacionais': financeiro['todas_despesas'].exclude(categoria__iexact='comissao'),
        'total_fretes': financeiro['total_fretes'],
        'total_comissao': financeiro['total_comissao'],
        'outras_despesas': financeiro['outras_despesas'],
        'total_saidas': financeiro['total_saidas'],
        'sobra': financeiro['sobra'],
        'mes_nome': LISTA_MESES[int(mes)],
        'mes_num': int(mes),
        'ano': int(ano),
        'aviso_trial': aviso_trial, 
    }
    return render(request, 'logistica/dashboard.html', context)



# ==========================================
# EDIÇÃO E EXCLUSÃO
# ==========================================

@login_required
@user_passes_test(e_admin_empresa)
def editar_viagem(request, caminhao_id, pk, mes, ano):
    # IDOR FIX: Garante que o caminhão pertence à empresa do usuário
    viagem = get_object_or_404(Viagem, pk=pk, caminhao__id=caminhao_id, caminhao__empresa=request.user.perfil.empresa)
    if request.method == 'POST':
        form = ViagemForm(request.POST, instance=viagem, user=request.user)
        if form.is_valid():
            form.save()
            return redirect('dashboard_detalhado', caminhao_id=int(caminhao_id), mes=int(mes), ano=int(ano))
    else:
        form = ViagemForm(instance=viagem, user=request.user)
    return render(request, 'logistica/editar_registro.html', {'form': form, 'objeto': viagem, 'titulo': 'Editar Viagem', 'caminhao_id': caminhao_id, 'mes': mes, 'ano': ano})

@login_required
@user_passes_test(e_admin_empresa)
def excluir_viagem(request, caminhao_id, pk):
    # IDOR FIX: Filtro duplo por PK e Empresa
    viagem = get_object_or_404(Viagem, pk=pk, caminhao__id=caminhao_id, caminhao__empresa=request.user.perfil.empresa)
    mes, ano = viagem.data.month, viagem.data.year
    if request.method == 'POST':
        Despesa.objects.filter(viagem_origem=viagem, categoria__iexact='comissao').delete()
        viagem.delete()
        return redirect('dashboard_detalhado', caminhao_id=caminhao_id, mes=mes, ano=ano)
    return render(request, 'logistica/confirmar_exclusao.html', {'objeto': viagem, 'tipo': 'viagem', 'caminhao_id': caminhao_id, 'mes': mes, 'ano': ano})

@login_required
@user_passes_test(e_admin_empresa)
def editar_despesa(request, caminhao_id, pk, mes, ano):
    # IDOR FIX
    despesa = get_object_or_404(Despesa, pk=pk, caminhao__id=caminhao_id, caminhao__empresa=request.user.perfil.empresa)
    
    # Lógica de Cores e Títulos
    cat_lower = despesa.categoria.lower()
    if cat_lower == 'comissao':
        titulo = 'Editar Comissão'
        cor_header = 'bg-info'  # Azul/Ciano das comissões
    elif cat_lower == 'abastecimento':
        titulo = 'Editar Abastecimento'
        cor_header = 'bg-warning' # Amarelo dos abastecimentos
    else:
        titulo = 'Editar Despesa'
        cor_header = 'bg-danger'  # Vermelho das despesas operacionais

    if request.method == 'POST':
        form = DespesaForm(request.POST, instance=despesa, user=request.user)
        if form.is_valid():
            form.save()
            return redirect('dashboard_detalhado', caminhao_id=caminhao_id, mes=mes, ano=ano)
    else:
        form = DespesaForm(instance=despesa, user=request.user)
    
    context = {
        'form': form,
        'objeto': despesa,
        'titulo': titulo,
        'cor_header': cor_header, # Passando a cor para o HTML
        'tipo': despesa.categoria.lower().strip(), # Garante que venha "comissao" limpo
        'caminhao_id': caminhao_id,
        'mes': mes,
        'ano': ano
    }
    return render(request, 'logistica/editar_registro.html', context)

@login_required
@user_passes_test(e_admin_empresa)
def excluir_despesa(request, caminhao_id, pk):
    # IDOR FIX
    despesa = get_object_or_404(Despesa, pk=pk, caminhao__id=caminhao_id, caminhao__empresa=request.user.perfil.empresa)
    mes, ano = despesa.data.month, despesa.data.year
    if request.method == 'POST':
        despesa.delete()
        return redirect('dashboard_detalhado', caminhao_id=caminhao_id, mes=mes, ano=ano)
    return render(request, 'logistica/confirmar_exclusao.html', {'objeto': despesa, 'tipo': 'despesa', 'caminhao_id': caminhao_id, 'mes': mes, 'ano': ano})

# ==========================================
# RELATÓRIOS E PDF
# ==========================================

def render_to_pdf(template_src, context_dict={}):
    """ Função auxiliar para converter HTML em PDF """
    template = get_template(template_src)
    html = template.render(context_dict)
    result = BytesIO()
    # xhtml2pdf precisa de bytes
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
    if not pdf.err:
        return result.getvalue()
    return None

@login_required
@user_passes_test(e_admin_empresa)
def dashboard_pdf(request, caminhao_id, mes, ano):
    empresa_usuario = request.user.perfil.empresa
    caminhao = get_object_or_404(Caminhao, id=caminhao_id, empresa=empresa_usuario)
    
    # 1. Utilizamos a função que você já criou para garantir que os valores
    # do PDF sejam EXATAMENTE iguais aos que você vê na tela do Dashboard.
    dados = obter_dados_financeiros(caminhao, mes, ano)
    
    # 2. Separamos as despesas como você faz no dashboard detalhado
    comissoes = dados['todas_despesas'].filter(categoria__iexact='comissao')
    despesas_operacionais = dados['todas_despesas'].exclude(categoria__iexact='comissao')

    context = {
        'caminhao': caminhao,
        'mes_nome': LISTA_MESES[int(mes)],
        'ano': ano,
        'viagens': dados['viagens'],
        'comissoes': comissoes,
        'despesas_operacionais': despesas_operacionais,
        'total_frete': dados['total_fretes'],
        'total_comissao': dados['total_comissao'],
        'total_despesas': dados['outras_despesas'],
        'total_saidas': dados['total_saidas'],
        'sobra_liquida': dados['sobra'],
        'hoje': timezone.now(),
    }

    # Gera o PDF usando a função auxiliar render_to_pdf que você já tem
    pdf = render_to_pdf('logistica/pdf_dashboard.html', context)
    
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        filename = f"Relatorio_{caminhao.placa}_{mes}_{ano}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    
    return HttpResponse("Erro ao gerar PDF", status=400)

@login_required
@user_passes_test(e_admin_empresa)
@check_assinatura
def media_consumo(request, caminhao_id, mes, ano):
    empresa_usuario = request.user.perfil.empresa
    caminhao = get_object_or_404(Caminhao.objects.select_related('empresa'), id=caminhao_id, empresa=empresa_usuario)
    
    # 1. Pega TODOS os abastecimentos do mês (com ou sem KM)
    abastecimentos = Despesa.objects.filter(
        caminhao=caminhao, 
        categoria__iexact='abastecimento', 
        data__month=mes, 
        data__year=ano
    ).select_related('caminhao').order_by('data', 'km_atual') # Ordenar por data é melhor aqui

    # 2. Litros Totais para o CARD (Soma absolutamente tudo que foi colocado no tanque)
    # 2. Litros Totais para o CARD (Soma absolutamente tudo que foi colocado no tanque)
    litros_totais_card = abastecimentos.aggregate(Sum('litros'))['litros__sum'] or Decimal('0')
    custo_total_combustivel = abastecimentos.aggregate(Sum('valor'))['valor__sum'] or Decimal('0')
    
    caminhoes_selector = Caminhao.objects.filter(empresa=empresa_usuario)

    for a in abastecimentos:
        a.preco_por_litro = a.valor / a.litros if a.litros and a.litros > 0 else 0

    total_km, litros_para_media, media_geral = 0, 0, 0
    
    # 3. Lógica da MÉDIA (Apenas registros com KM > 0)
    abastecimentos_com_km = abastecimentos.filter(km_atual__gt=0).order_by('km_atual')
    
    if abastecimentos_com_km.count() >= 2:
        primeiro = abastecimentos_com_km.first() 
        ultimo = abastecimentos_com_km.last()
        
        total_km = ultimo.km_atual - primeiro.km_atual
        
        # Para a média, somamos os litros de todos os abastecimentos válidos, 
        # exceto o primeiro da série (tanque cheio inicial)
        litros_para_media = abastecimentos_com_km.exclude(id=primeiro.id).aggregate(Sum('litros'))['litros__sum'] or Decimal('0')
        
        if litros_para_media > 0: 
            media_geral = total_km / litros_para_media
    
    return render(request, 'logistica/media_consumo.html', {
        'abastecimentos': abastecimentos, 
        'total_km': total_km, 
        'total_litros': litros_totais_card, # <--- Agora o CARD recebe o total real
        'media_geral': media_geral, 
        'custo_total_combustivel': custo_total_combustivel,
        'mes_nome': LISTA_MESES[int(mes)], 
        'mes_num': mes, 
        'ano': ano, 
        'caminhao_id': caminhao_id,
        'caminhoes_selector': caminhoes_selector,
    })

@login_required
@user_passes_test(e_admin_empresa)
@check_assinatura
def comissoes_por_motorista(request, caminhao_id, mes, ano):
    """ Exibe a página Web com o resumo das comissões """
    empresa_usuario = request.user.perfil.empresa
    caminhao = get_object_or_404(Caminhao.objects.select_related('empresa'), id=caminhao_id, empresa=empresa_usuario)
    caminhoes_selector = Caminhao.objects.filter(empresa=empresa_usuario)
    
    comissoes = Despesa.objects.filter(caminhao=caminhao, categoria__iexact='comissao', data__month=mes, data__year=ano).select_related('viagem_origem').order_by().distinct()
    motoristas = Viagem.objects.filter(caminhao=caminhao, data__month=mes, data__year=ano).order_by().values_list('motorista', flat=True).distinct()

    extrato, total_geral = [], 0
    for m in motoristas:
        comissoes_m = comissoes.filter(viagem_origem__motorista=m)
        soma = comissoes_m.aggregate(Sum('valor'))['valor__sum'] or 0
        extrato.append({'nome': m, 'comissoes': comissoes_m, 'total': soma})
        total_geral += soma

    return render(request, 'logistica/comissoes_motoristas.html', {
        'extrato': extrato, 
        'total_geral': total_geral, 
        'mes_nome': LISTA_MESES[int(mes)], 
        'mes_num': mes, 
        'ano': ano, 
        'caminhao_id': caminhao_id,
        'caminhao': caminhao,
        'caminhoes_selector': caminhoes_selector,
    })

@login_required
@user_passes_test(e_admin_empresa)
def gerar_pdf_comissoes_geral(request, caminhao_id, mes, ano):
    """ Gera e faz o download do PDF com todos os motoristas do mês """
    empresa_usuario = request.user.perfil.empresa
    caminhao = get_object_or_404(Caminhao, id=caminhao_id, empresa=empresa_usuario)
    
    # Buscamos todas as despesas de comissão com a viagem relacionada
    comissoes_query = (Despesa.objects.filter(
        caminhao=caminhao, 
        categoria__iexact='comissao', 
        data__month=mes, 
        data__year=ano
    ).select_related('viagem_origem').only('data', 'valor', 'descricao', 'viagem_origem').distinct())

    motoristas = Viagem.objects.filter(
        caminhao=caminhao, 
        data__month=mes, 
        data__year=ano
    ).order_by().values_list('motorista', flat=True).distinct()

    extrato, total_geral = [], 0
    for m in motoristas:
        # Aqui filtramos a query principal para cada motorista e transformamos em lista
        comissoes_m = list(comissoes_query.filter(viagem_origem__motorista=m))
        soma = sum(item.valor for item in comissoes_m)
        extrato.append({'nome': m, 'comissoes': comissoes_m, 'total': soma})
        total_geral += soma

    context = {
        'extrato': extrato,
        'total_geral': total_geral,
        'mes_nome': LISTA_MESES[int(mes)],
        'ano': ano,
        'caminhao': caminhao,
        'data_emissao': timezone.now(),
        'is_pdf': True
    }
    
    pdf_content = render_to_pdf('logistica/pdf_comissoes.html', context)
    if pdf_content:
        response = HttpResponse(pdf_content, content_type='application/pdf')
        filename = f"Comissoes_Geral_{caminhao.placa}_{mes}_{ano}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    return HttpResponse("Erro ao gerar PDF", status=400)

@login_required
@user_passes_test(e_admin_empresa)
def gerar_pdf_comissao_individual(request, caminhao_id, mes, ano, motorista_nome):
    """ Gera e faz o download do PDF de um motorista específico """
    empresa_usuario = request.user.perfil.empresa
    caminhao = get_object_or_404(Caminhao, id=caminhao_id, empresa=empresa_usuario)
    
    comissoes = list(Despesa.objects.filter(
        caminhao=caminhao, 
        categoria__iexact='comissao', 
        data__month=mes, 
        data__year=ano,
        viagem_origem__motorista=motorista_nome
    ).select_related('viagem_origem').only('data', 'valor', 'descricao', 'viagem_origem'))
    
    soma_total = sum(item.valor for item in comissoes)
    extrato = [{'nome': motorista_nome, 'comissoes': comissoes, 'total': soma_total}]

    context = {
        'extrato': extrato,
        'total_geral': soma_total,
        'mes_nome': LISTA_MESES[int(mes)],
        'ano': ano,
        'caminhao': caminhao,
        'data_emissao': timezone.now(),
        'individual': True,
        'is_pdf': True
    }

    pdf_content = render_to_pdf('logistica/pdf_comissoes.html', context)
    if pdf_content:
        response = HttpResponse(pdf_content, content_type='application/pdf')
        filename = f"Comissao_{motorista_nome.replace(' ', '_')}_{mes}_{ano}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    return HttpResponse("Erro ao gerar PDF", status=400)

    pdf_content = render_to_pdf('logistica/pdf_comissoes.html', context)
    if pdf_content:
        response = HttpResponse(pdf_content, content_type='application/pdf')
        filename = f"Comissao_{motorista_nome.replace(' ', '_')}_{mes}_{ano}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    return HttpResponse("Erro ao gerar PDF", status=400)

@login_required
@user_passes_test(e_admin_empresa)
@check_assinatura
def relatorio_custos(request, caminhao_id, mes, ano):
    empresa_usuario = request.user.perfil.empresa
    caminhao = get_object_or_404(Caminhao, id=caminhao_id, empresa=empresa_usuario)
    caminhoes_selector = Caminhao.objects.filter(empresa=empresa_usuario)
    
    # --- 1. DADOS FINANCEIROS ---
    fin = obter_dados_financeiros(caminhao, mes, ano)
    total_frete_geral = float(fin['total_fretes'])

    # --- 2. TABELA DE IMPACTO E GRÁFICO ---
    labels_grafico = []
    valores_grafico = []
    tabela_impacto = []
    cores = ['#ffc107', '#0dcaf0', '#dc3545', '#6c757d', '#198754', '#0d6efd', '#6f42c1']
    
    for i, (cat, total) in enumerate(fin['dados_grafico'].items()):
        # Safeguard: ensure cat is not None before replace
        safe_cat = str(cat) if cat else "N/A"
        nome_cat = safe_cat.replace('_', ' ').capitalize()
        valor_cat = float(total or 0)
        labels_grafico.append(nome_cat)
        valores_grafico.append(valor_cat)
        perc = (valor_cat / total_frete_geral * 100) if total_frete_geral > 0 else 0
        tabela_impacto.append({
            'categoria': nome_cat, 
            'valor': valor_cat, 
            'percentual': perc, 
            'cor': cores[i % len(cores)]
        })
    
    if fin['sobra'] > 0:
        labels_grafico.append('Sobra Líquida')
        valores_grafico.append(float(fin['sobra']))
        perc_sobra = (float(fin['sobra']) / total_frete_geral * 100) if total_frete_geral > 0 else 0
        tabela_impacto.append({
            'categoria': 'Sobra Líquida', 
            'valor': float(fin['sobra']), 
            'percentual': perc_sobra, 
            'cor': '#198754'
        })

    # --- 3. RECEITA POR MOTORISTA ---
    viagens_mes = Viagem.objects.filter(caminhao=caminhao, data__month=mes, data__year=ano).distinct()
    nomes_motoristas = viagens_mes.order_by().values_list('motorista', flat=True).distinct()
    tabela_motoristas = []
    for m in nomes_motoristas:
        soma_frete = viagens_mes.filter(motorista=m).aggregate(Sum('valor_frete'))['valor_frete__sum'] or Decimal('0')
        perc_m = (float(soma_frete) / total_frete_geral * 100) if total_frete_geral > 0 else 0
        tabela_motoristas.append({'nome': m or "Não identificado", 'valor': float(soma_frete), 'percentual': perc_m})

    # --- 4. CÁLCULO DE CONSUMO (Corrigido para ignorar KM 0) ---
    # Pegamos todos para a soma de litros, mas filtramos para achar o KM inicial real
    abastecimentos = Despesa.objects.filter(
        caminhao=caminhao, 
        categoria__iexact='abastecimento', 
        data__month=mes, 
        data__year=ano
    ).order_by('km_atual')
    
    # Filtro específico para encontrar registros com KM válido
    abastecimentos_com_km = abastecimentos.filter(km_atual__gt=0)
    
    total_km, total_litros, media_geral = 0, 0, 0
    
    if abastecimentos_com_km.count() >= 2:
        primeiro = abastecimentos_com_km.first() # Menor KM acima de zero
        ultimo = abastecimentos_com_km.last()    # Maior KM
        
        total_km = ultimo.km_atual - primeiro.km_atual
        
        # Litros: Soma os litros de todos os abastecimentos do período, 
        # exceto os litros do primeiro abastecimento que tem KM válido.
        total_litros = abastecimentos_com_km.exclude(id=primeiro.id).aggregate(Sum('litros'))['litros__sum'] or Decimal('0')
        
        if total_litros > 0: 
            media_geral = total_km / total_litros

    context = {
        'caminhao': caminhao,
        'caminhoes_selector': caminhoes_selector,
        'labels': labels_grafico,
        'valores': valores_grafico,
        'tabela_impacto': tabela_impacto,
        'tabela_motoristas': tabela_motoristas,
        'total_frete': total_frete_geral,
        # Dados do novo card de consumo:
        'total_km': total_km,
        'total_litros': total_litros,
        'media_geral': media_geral,
        'mes_nome': LISTA_MESES[int(mes)],
        'mes_num': int(mes),
        'ano': int(ano),
    }
    return render(request, 'logistica/relatorio_custos.html', context)

@login_required
@user_passes_test(e_admin_empresa)
def gerar_pdf_custos(request, caminhao_id, mes, ano):
    """ Gera o PDF do Relatório de Custos, Faturamento e Consumo """
    empresa_usuario = request.user.perfil.empresa
    caminhao = get_object_or_404(Caminhao, id=caminhao_id, empresa=empresa_usuario)
    
    # --- 1. DADOS FINANCEIROS (Impacto) ---
    fin = obter_dados_financeiros(caminhao, mes, ano)
    total_frete_geral = float(fin['total_fretes'])
    tabela_impacto = []
    for cat, total in fin['dados_grafico'].items():
        valor_cat = float(total or 0)
        perc = (valor_cat / total_frete_geral * 100) if total_frete_geral > 0 else 0
        # Safeguard for string manipulation
        cat_str = str(cat) if cat else "N/A"
        tabela_impacto.append({
            'categoria': cat_str.replace('_', ' ').capitalize(),
            'valor': valor_cat,
            'percentual': perc
        })
    
    if fin['sobra'] > 0:
        perc_sobra = (float(fin['sobra']) / total_frete_geral * 100) if total_frete_geral > 0 else 0
        tabela_impacto.append({
            'categoria': 'Sobra Líquida',
            'valor': float(fin['sobra']),
            'percentual': perc_sobra
        })

    # --- 2. RECEITA POR MOTORISTA ---
    viagens_mes = Viagem.objects.filter(caminhao=caminhao, data__month=mes, data__year=ano)
    nomes_motoristas = viagens_mes.order_by().values_list('motorista', flat=True).distinct()
    tabela_motoristas = []
    for m in nomes_motoristas:
        soma_frete = viagens_mes.filter(motorista=m).aggregate(Sum('valor_frete'))['valor_frete__sum'] or Decimal('0')
        perc = (float(soma_frete) / total_frete_geral * 100) if total_frete_geral > 0 else 0
        tabela_motoristas.append({'nome': m or "Não identificado", 'valor': float(soma_frete), 'percentual': perc})

    # --- 3. LÓGICA DE CONSUMO (Copiada da sua função media_consumo) ---
    abastecimentos = Despesa.objects.filter(
        caminhao=caminhao, 
        categoria__iexact='abastecimento', 
        data__month=mes, 
        data__year=ano
    ).order_by('km_atual')
    
    total_km, total_litros, media_geral = 0, 0, 0
    if abastecimentos.count() >= 2:
        primeiro, ultimo = abastecimentos.first(), abastecimentos.last()
        total_km = ultimo.km_atual - primeiro.km_atual
        # Regra: soma litros excluindo o primeiro abastecimento
        total_litros = abastecimentos.exclude(id=primeiro.id).aggregate(Sum('litros'))['litros__sum'] or Decimal('0')
        if total_litros > 0: 
            media_geral = total_km / total_litros

    # --- 4. CONTEXTO E RENDERIZAÇÃO ---
    context = {
        'caminhao': caminhao,
        'tabela_impacto': tabela_impacto,
        'tabela_motoristas': tabela_motoristas,
        'total_frete': total_frete_geral,
        # Dados de consumo que o seu template PDF está esperando:
        'total_km': total_km,
        'total_litros': total_litros,
        'media_geral': media_geral,
        'mes_nome': LISTA_MESES[int(mes)],
        'ano': ano,
        'data_emissao': timezone.now(),
        'is_pdf': True
    }

    pdf_content = render_to_pdf('logistica/pdf_relatorio_custos.html', context)
    if pdf_content:
        response = HttpResponse(pdf_content, content_type='application/pdf')
        filename = f"Relatorio_Operacional_{caminhao.placa}_{mes}_{ano}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    return HttpResponse("Erro ao gerar PDF", status=400)