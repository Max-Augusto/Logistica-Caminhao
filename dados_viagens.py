import os
import django
import csv
from decimal import Decimal
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from logistica.models import Viagem, Caminhao

def importar():
    file_path = 'dados_viagens.csv' 
    PLACA_CAMINHAO = 'TDN-6G58' 
    
    try:
        caminhao = Caminhao.objects.get(placa=PLACA_CAMINHAO)
    except Caminhao.DoesNotExist:
        print(f"Erro: Caminhao {PLACA_CAMINHAO} nao encontrado.")
        return

    # Tenta UTF-8 com suporte a BOM (Excel), se falhar usa latin-1
    encoding_to_try = 'utf-8-sig'
    try:
        with open(file_path, mode='r', encoding=encoding_to_try) as f:
            f.read(1)
    except UnicodeDecodeError:
        encoding_to_try = 'latin-1'

    print(f"Usando encoding: {encoding_to_try}")

    with open(file_path, mode='r', encoding=encoding_to_try) as f:
        # Detecta automaticamente se o separador e ';' ou ','
        sample = f.readline()
        f.seek(0)
        dialect = ';' if ';' in sample else ','
        reader = csv.DictReader(f, delimiter=dialect) 
        
        count = 0
        for row in reader:
            try:
                # Trata chaves que podem vir com espaços ou caracteres estranhos
                row = {k.strip(): v for k, v in row.items() if k}
                
                data_str = row['Data'].strip()
                desc_str = row['Descricao'].strip()
                valor_str = row['Valor'].strip()
                motorista_str = row['Motorista'].strip()

                data_formatada = datetime.strptime(data_str, '%d/%m/%Y').date()
                # Remove R$, pontos de milhar e troca virgula por ponto
                valor_limpo = valor_str.replace('R$', '').replace('.', '').replace(',', '.').strip()
                valor = Decimal(valor_limpo)
                
                Viagem.objects.create(
                    caminhao=caminhao,
                    data=data_formatada,
                    rota=desc_str,
                    valor_frete=valor,
                    motorista=motorista_str if motorista_str != '//' else 'Motorista Padrao'
                )
                count += 1
                print(f"Importado: {desc_str}")
            except Exception as e:
                print(f"Erro na linha {row}: {e}")

    print(f"--- FIM: {count} viagens importadas! ---")

if __name__ == '__main__':
    importar()