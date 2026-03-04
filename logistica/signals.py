from django.db.models.signals import post_save
from django.dispatch import receiver
from allauth.socialaccount.models import SocialAccount
from .models import Empresa, PerfilUsuario

@receiver(post_save, sender=SocialAccount)
def criar_perfil_novo_usuario_google(sender, instance, created, **kwargs):
    if created:
        user = instance.user
        if not hasattr(user, 'perfil'):
            # Criamos o perfil, mas deixamos a empresa vazia (None)
            # para que a View configurar_empresa preencha depois.
            PerfilUsuario.objects.create(
                user=user,
                empresa=None, 
                e_administrador=True
            )