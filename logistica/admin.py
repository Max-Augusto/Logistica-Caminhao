from django.contrib import admin
from .models import Viagem, Despesa, Caminhao, Empresa, PerfilUsuario

admin.site.register(Viagem)
admin.site.register(Despesa)
admin.site.register(Empresa)
admin.site.register(PerfilUsuario)

@admin.register(Caminhao)
class CaminhaoAdmin(admin.ModelAdmin):
    # 'comissao_percentual' adicionada aqui para aparecer no Admin
    list_display = ('placa', 'modelo', 'empresa', 'motorista_responsavel', 'comissao_percentual')
    list_filter = ('empresa',)
    search_fields = ('placa', 'modelo')