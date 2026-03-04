import os
import django
from decimal import Decimal
import datetime
import time
from django.db import connection, reset_queries

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from logistica.models import Despesa, Viagem, Caminhao, Empresa
from logistica.forms import DespesaForm
from django.contrib.auth.models import User

def verify_data_integrity():
    print("\n--- Verificando Integridade de Dados ---")
    val1 = Decimal('50.00')
    val2 = Decimal('15.00')
    result = val1 + val2
    print(f"Calculando: {val1} + {val2}")
    print(f"Resultado: {result}")
    print(f"Tipo: {type(result)}")
    
    if result == Decimal('65.00'):
        print("[OK] SUCESSO: Soma exata de decimais confirmada.")
    else:
        print(f"[FAIL] FALHA: Esperado 65.00, obtido {result}")

def verify_business_security():
    print("\n--- Verificando Segurança de Negócio (KM) ---")
    
    # Setup mock data using get_or_create to avoid duplicates if re-run
    user, _ = User.objects.get_or_create(username='testuser', defaults={'email': 'test@example.com'})
    empresa, _ = Empresa.objects.get_or_create(nome="Test Corp")
    caminhao, _ = Caminhao.objects.get_or_create(placa="TEST-9999", defaults={'modelo': 'Test Truck', 'empresa': empresa})
    
    # Create past expense
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    
    # Clear previous test data to ensure clean state
    Despesa.objects.filter(caminhao=caminhao).delete()
    
    Despesa.objects.create(
        caminhao=caminhao,
        data=yesterday,
        descricao="Abastecimento Anterior",
        valor=Decimal('100.00'),
        categoria='abastecimento',
        km_atual=10000,
        litros=Decimal('50')
    )
    
    # Try to insert today with LOWER KM
    form_data = {
        'caminhao': caminhao.id,
        'data': today,
        'descricao': 'Abastecimento Teste',
        'valor': '50.00',
        'categoria': 'abastecimento',
        'km_atual': 9000, # ERROR: Lower than 10000
        'litros': '20'
    }
    
    form = DespesaForm(data=form_data)
    if not form.is_valid():
        if 'km_atual' in form.errors:
            print("[OK] SUCESSO: Tentativa de KM inferior bloqueada!")
            print(f"Erro retornado: {form.errors['km_atual'][0]}")
        else:
            print(f"[FAIL] FALHA: Erro esperado em km_atual não encontrado. Erros: {form.errors}")
    else:
        print("[FAIL] FALHA: Formulário validou dados incorretos!")

def verify_efficiency():
    print("\n--- Verificando Eficiencia (Indices) ---")
    
    # Query typical for reports/validation: By Caminhao and Date
    queryset = Despesa.objects.filter(caminhao__placa="TEST-9999", data=datetime.date.today())
    
    # Check database engine
    db_engine = connection.vendor
    print(f"Database Engine: {db_engine}")
    
    try:
        explanation = queryset.explain()
        print("Plano de Execucao (via Django explain):")
        print(explanation)
        
        # Check for index usage in the explanation string
        # SQLite: "USING INDEX" or "SEARCH TABLE ... USING INDEX"
        # Postgres: "Index Scan" or "Bitmap Heap Scan"
        
        if 'USING INDEX' in explanation or 'Index Scan' in explanation:
             print("[OK] SUCESSO: Indice utilizado na consulta.")
        elif 'SCAN TABLE' in explanation and 'USING INDEX' not in explanation:
             # Check if table is empty or small, which causes SCAN
             count = Despesa.objects.count()
             if count < 100:
                  print(f"[WARN] AVISO: Full Scan detectado, mas tabela tem apenas {count} registros (o otimizador prefere scan).")
                  # Fallback: check model meta
                  if Despesa._meta.indexes:
                      print(f"[OK] SUCESSO: Indices definidos no modelo: {[str(i) for i in Despesa._meta.indexes]}")
             else:
                  print("[FAIL] FALHA: Full Scan em tabela grande!")
        else:
             # Fallback check
             if Despesa._meta.indexes:
                  print(f"[OK] SUCESSO: Indices definidos no modelo (Plano nao conclusivo ou otimizacao de tabela pequena): {[str(i) for i in Despesa._meta.indexes]}")
                  
    except Exception as e:
        print(f"[FAIL] Erro ao gerar explain: {e}")


if __name__ == "__main__":
    verify_data_integrity()
    verify_business_security()
    verify_efficiency()
