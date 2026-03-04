from django.apps import AppConfig

class LogisticaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'logistica'

    def ready(self):
        import logistica.signals # Carrega os gatilhos de atualização de preço