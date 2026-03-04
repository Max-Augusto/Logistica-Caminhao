from django import forms
from django.contrib.auth.models import User
from .models import Viagem, Despesa, Caminhao, PerfilUsuario, Empresa
from allauth.socialaccount.forms import SignupForm

class CustomSocialSignupForm(SignupForm):
    # Campo para o usuário escolher o login dele
    username = forms.CharField(
        max_length=30,
        label='Nome de Usuário',
        widget=forms.TextInput(attrs={'placeholder': 'Seu nome no sistema'})
    )
    
    nome_empresa = forms.CharField(
        max_length=100, 
        label='Nome da Empresa',
        widget=forms.TextInput(attrs={'placeholder': 'Ex: Minha Logística LTDA'})
    )
    
    password = forms.CharField(
        label="Crie uma Senha",
        widget=forms.PasswordInput(attrs={'placeholder': 'Mínimo 8 caracteres'})
    )

    def save(self, request):
        # 1. Deixa o Allauth criar o objeto User básico
        user = super(CustomSocialSignupForm, self).save(request)
        
        # 2. Pega os dados validados do seu formulário
        escolha_username = self.cleaned_data.get('username')
        escolha_senha = self.cleaned_data.get('password')
        escolha_empresa = self.cleaned_data.get('nome_empresa')

        # 3. Atualiza o User com o que foi digitado
        user.username = escolha_username
        user.set_password(escolha_senha) # Criptografa a senha
        user.save()

        # 4. Criamos a Empresa (EXCEÇÃO: Dono via Google)
        nova_empresa, _ = Empresa.objects.get_or_create(nome=escolha_empresa)

        # 5. Criamos o Perfil como Administrador
        PerfilUsuario.objects.update_or_create(
            user=user,
            defaults={
                'empresa': nova_empresa,
                'e_administrador': True
            }
        )
        return user

# Formulário para usuários que não usam Redes Sociais (opcional)
class SignupForm(forms.Form):
    nome_empresa = forms.CharField(max_length=100, label='Nome da Empresa', 
                                   widget=forms.TextInput(attrs={'placeholder': 'Ex: Logística Express'}))

    def signup(self, request, user):
        nome_empresa = self.cleaned_data['nome_empresa']
        # Tenta buscar a empresa
        try:
            nova_empresa = Empresa.objects.get(nome=nome_empresa)
        except Empresa.DoesNotExist:
            nova_empresa = None
        # Cria o perfil
        PerfilUsuario.objects.create(user=user, empresa=nova_empresa, e_administrador=True)
    
class AdicionarCaminhaoForm(forms.ModelForm):
    username_motorista = forms.CharField(label="Login do Motorista", widget=forms.TextInput(attrs={'class': 'form-control'}))
    senha_motorista = forms.CharField(label="Senha Inicial", widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    class Meta:
        model = Caminhao
        fields = ['placa', 'modelo', 'comissao_percentual'] 
        widgets = {
            'placa': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ABC-1234'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Scania Azul'}),
            'comissao_percentual': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class EditarCaminhaoForm(forms.ModelForm):
    class Meta:
        model = Caminhao
        fields = ['placa', 'modelo', 'comissao_percentual']
        widgets = {
            'placa': forms.TextInput(attrs={'class': 'form-control'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control'}),
            'comissao_percentual': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class ViagemForm(forms.ModelForm):
    class Meta:
        model = Viagem
        fields = ['caminhao', 'data', 'motorista', 'rota', 'valor_frete']
        widgets = {
            'data': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'caminhao': forms.Select(attrs={'class': 'form-select'}),
            'motorista': forms.TextInput(attrs={'class': 'form-control'}),
            'rota': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Betim x SP'}),
            'valor_frete': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # 1. Aplicar estilo Bootstrap
        self.fields['caminhao'].widget.attrs.update({'class': 'form-select'})
        
        # 2. Lógica de Filtro ÚNICA (Sem repetições)
        if user:
            if user.is_superuser:
                self.fields['caminhao'].queryset = Caminhao.objects.all()
            elif hasattr(user, 'perfil') and user.perfil.e_administrador:
                # Filtra pela empresa do perfil (APENAS SE FOR ADMIN)
                self.fields['caminhao'].queryset = Caminhao.objects.filter(empresa=user.perfil.empresa)
            else:
                # Filtra pelo motorista direto (SE FOR MOTORISTA COMUM, MESMO COM PERFIL)
                qs = Caminhao.objects.filter(motorista_responsavel=user)
                self.fields['caminhao'].queryset = qs
                if qs.count() == 1:
                    self.fields['caminhao'].initial = qs.first()
                self.fields['motorista'].initial = user.username

class DespesaForm(forms.ModelForm):
    class Meta:
        model = Despesa
        fields = ['caminhao', 'data', 'descricao', 'valor', 'km_atual', 'litros']
        widgets = {
            'data': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'caminhao': forms.Select(attrs={'class': 'form-select'}),
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'km_atual': forms.NumberInput(attrs={'class': 'form-control'}),
            'litros': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Define campos como opcionais
        self.fields['descricao'].required = False
        self.fields['km_atual'].required = False
        self.fields['litros'].required = False
        
        # Estilo Bootstrap
        self.fields['caminhao'].widget.attrs.update({'class': 'form-select'})
        
        if user:
            if user.is_superuser:
                self.fields['caminhao'].queryset = Caminhao.objects.all()
            # Correção aqui: Verifica se é admin explicitamente
            elif hasattr(user, 'perfil') and user.perfil.e_administrador:
                self.fields['caminhao'].queryset = Caminhao.objects.filter(empresa=user.perfil.empresa)
            else:
                # Caso seja um motorista comum (vínculo direto), restringimos ao dele
                qs = Caminhao.objects.filter(motorista_responsavel=user)
                self.fields['caminhao'].queryset = qs
                
                # Seleção automática OBRIGATÓRIA para motorista
                if qs.count() == 1:
                    self.fields['caminhao'].initial = qs.first()

    def clean_km_atual(self):
        km_atual = self.cleaned_data.get('km_atual')
        caminhao = self.cleaned_data.get('caminhao')
        data_digitada = self.cleaned_data.get('data')

        if not km_atual or km_atual == 0:
            return 0

        if km_atual > 0 and caminhao and data_digitada:
            anterior = Despesa.objects.filter(
                caminhao=caminhao,
                categoria__iexact='abastecimento',
                data__lt=data_digitada, 
                km_atual__gt=0
            ).exclude(pk=self.instance.pk).order_by('-data', '-km_atual').first()

            if anterior and km_atual < anterior.km_atual:
                raise forms.ValidationError(
                    f"KM inválido! No dia {anterior.data.strftime('%d/%m/%Y')} já existe um registro "
                    f"com KM {anterior.km_atual:g}."
                )

            proximo = Despesa.objects.filter(
                caminhao=caminhao,
                categoria__iexact='abastecimento',
                data__gt=data_digitada,
                km_atual__gt=0
            ).exclude(pk=self.instance.pk).order_by('data', 'km_atual').first()

            if proximo and km_atual > proximo.km_atual:
                raise forms.ValidationError(
                    f"KM alto demais! Já existe um registro futuro de {proximo.km_atual:g} "
                    f"na data {proximo.data.strftime('%d/%m/%Y')}."
                )

        return km_atual