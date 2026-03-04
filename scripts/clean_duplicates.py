from logistica.models import Despesa, Viagem
from django.db.models import Count

def limpar_duplicatas():
    # 1. Identificar comissões duplicadas (mesma viagem)
    duplicatas = Despesa.objects.filter(categoria='comissao')\
        .values('viagem_origem')\
        .annotate(qtd=Count('id'))\
        .filter(qtd__gt=1)

    count_removidos = 0
    
    for item in duplicatas:
        viagem_id = item['viagem_origem']
        # Busca todas as despesas dessa viagem
        despesas = Despesa.objects.filter(viagem_origem_id=viagem_id, categoria='comissao').order_by('id')
        
        # Mantém a primeira (ou última, tanto faz pois são iguais) e deleta o resto
        primeira = despesas.first()
        despesas_para_deletar = despesas.exclude(id=primeira.id)
        
        qtd = despesas_para_deletar.count()
        despesas_para_deletar.delete()
        count_removidos += qtd
        print(f"Viagem {viagem_id}: {qtd} duplicatas removidas. Mantido ID {primeira.id}")

    print(f"Total removido: {count_removidos}")

if __name__ == '__main__':
    # Setup Django (se rodar como script standalone)
    import os
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
    django.setup()
    limpar_duplicatas()
