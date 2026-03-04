# logistica/adapters.py
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.shortcuts import render

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_auto_signup_allowed(self, request, sociallogin):
        # Isso diz ao Allauth: "Mesmo que você tenha os dados, NÃO faça o cadastro automático"
        return False