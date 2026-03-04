import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

load_dotenv() # Isso lê um arquivo chamado .env na raiz do projeto


MERCADO_PAGO_PUBLIC_KEY = os.getenv('MP_PUBLIC_KEY', 'chave-padrao-de-teste')
MERCADO_PAGO_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "token-padrao-de-teste")

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SEGURANÇA: Chave secreta em variável de ambiente (ou fallback para dev)
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-zy=ln6wdu_0_jddtmzzcsx)pbcexg@20)6odfbgf$jl5hl0^=$')

DEBUG = False

# No Railway, o ALLOWED_HOSTS precisa aceitar o domínio deles e o personalizado
ALLOWED_HOSTS = ['*', 'betimexpress.com.br', 'www.betimexpress.com.br', 'logisticabetim.up.railway.app'] 

PREPEND_WWW = False

CSRF_TRUSTED_ORIGINS = [
    'https://logisticabetim.up.railway.app', 
    'https://*.up.railway.app',
    'https://betimexpress.com.br',
    'https://www.betimexpress.com.br'
]

# Ajuste SSL: Railway gerencia o SSL, evitamos redirecionamentos internos para não dar conflito
SECURE_SSL_REDIRECT = False


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'logistica',
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'pagamentos',
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]


# Mude para False para que o formulário de "Empresa" apareça
SOCIALACCOUNT_AUTO_SIGNUP = False


SOCIALACCOUNT_ADAPTER = 'logistica.adapters.CustomSocialAccountAdapter'

# Configurações de Autenticação
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = True  # Ative se quiser que ele escolha um username
ACCOUNT_EMAIL_VERIFICATION = "none"

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'OAUTH_PKCE_ENABLED': True,
    }
}

# Isso resolve o erro de "unpack" (remova versões antigas dessa lista)
ACCOUNT_FORMS = {
    'signup': 'allauth.account.forms.SignupForm',
}

# Caminho para o seu formulário customizado que pede a Empresa
# Substitua 'seu_app' pelo nome da pasta do seu aplicativo Django
SOCIALACCOUNT_FORMS = {
    'signup': 'logistica.forms.CustomSocialSignupForm',
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Essencial para CSS em produção
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'


DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL') or f'sqlite:///{os.path.join(BASE_DIR, "db.sqlite3")}',
        conn_max_age=600
    )
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    #{'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    #{'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    #{'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    #{'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# Internationalization
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True
USE_L10N = True  

# Força o Django a usar o separador de milhar
USE_THOUSAND_SEPARATOR = True
THOUSAND_SEPARATOR = '.'
DECIMAL_SEPARATOR = ','

# Login / Logout
LOGIN_URL = 'login' 
LOGIN_REDIRECT_URL = 'checar_perfil'
LOGOUT_REDIRECT_URL = 'login'
SITE_ID = 1

ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https'

# ARQUIVOS ESTÁTICOS (CSS, JS)
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Versão segura: não crasha o site se faltar um arquivo
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'


SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# EMAIL CONFIGURATION (Resend API via Anymail)
EMAIL_BACKEND = "anymail.backends.resend.EmailBackend"
RESEND_API_KEY = os.getenv('RESEND_API_KEY')
DEFAULT_FROM_EMAIL = 'suporte@betimexpress.com.br'

ANYMAIL = {
    "RESEND_API_KEY": RESEND_API_KEY,
}