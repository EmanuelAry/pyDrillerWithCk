import subprocess
import csv
import shutil
import re
from pathlib import Path
from datetime import datetime
from git import Repo

# Caminhos (ajuste conforme necessário)
repo_path = Path(r'C:\Users\Emanuel\Desktop\android_test\android-test')
ck_jar_path = Path(r'C:\Users\Emanuel\Documents\pt-BR\pyDriller\ck\ck\target\ck-0.7.1-SNAPSHOT-jar-with-dependencies.jar')
output_dir = Path(r'C:\Users\Emanuel\Documents\pt-BR\pyDriller\output_ck')      # diretório temporário do CK
archive_dir = Path(r'C:\Users\Emanuel\Documents\pt-BR\pyDriller\ck_archive')    # onde serão guardados os CSVs por release
bugs_archive_dir = Path(r'C:\Users\Emanuel\Documents\pt-BR\pyDriller\bugs_archive')    # onde serão guardados os CSVs por release
available_csv = bugs_archive_dir / 'available_releases.csv'                          # arquivo com as releases válidas

repo = Repo(repo_path)
original_commit = repo.head.commit

# Cria diretório de arquivo se não existir
archive_dir.mkdir(parents=True, exist_ok=True)

# Mapa de nome de tag para objeto tag (para consulta rápida)
tag_map = {tag.name: tag for tag in repo.tags}
print(f"Total de tags no repositório: {len(tag_map)}")

# Lê o arquivo available_releases.csv
releases_to_process = []
with open(available_csv, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        tag_name = row['tag'].strip()
        date_str = row['date'].strip()
        releases_to_process.append((tag_name, date_str))

print(f"Releases a processar (segundo o CSV): {len(releases_to_process)}")

for tag_name, date_str in releases_to_process:
    if tag_name not in tag_map:
        print(f"[AVISO] Tag '{tag_name}' não encontrada no repositório. Ignorada.")
        continue

    tag = tag_map[tag_name]
    print(f"\n=== Processando tag: {tag_name} (data: {date_str}) ===")

    # Checkout do commit da tag (detached HEAD)
    repo.git.checkout(tag.commit.hexsha)

    try:
        # Prepara diretório temporário limpo
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Executa o CK
        cmd = [
            'java', '-jar', str(ck_jar_path),
            str(repo_path),
            'true', '0', 'false',
            str(output_dir),
            'csv'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print("Falha ao executar o CK:")
            print(result.stderr)
            continue   # pula para a próxima release se der erro

        # --- Salva class.csv com o novo padrão de nome ---
        class_csv = output_dir / 'class.csv'
        if class_csv.exists():
            archive_class = archive_dir / f"class_{date_str}_{tag_name}.csv"
            shutil.copy2(class_csv, archive_class)
            print(f"Salvo: {archive_class}")

            # Exibe as métricas no console (opcional)
            with open(class_csv, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                # Cabeçalho (mostra as primeiras colunas relevantes)
                print(f"{'Classe':<50} {'WMC':>6} {'DIT':>6} {'NOC':>6} {'CBO':>6} {'LCOM':>6} {'RFC':>6} {'LOC':>6}")
                for row in reader:
                    print(f"{row['class']:<50} {row.get('wmc','?'):>6} {row.get('dit','?'):>6} "
                          f"{row.get('noc','?'):>6} {row.get('cbo','?'):>6} "
                          f"{row.get('lcom','?'):>6} {row.get('rfc','?'):>6} {row.get('loc','?'):>6}")
        else:
            print("Aviso: class.csv não encontrado")

        # --- Salva method.csv com o novo padrão de nome ---
        method_csv = output_dir / 'method.csv'
        if method_csv.exists():
            archive_method = archive_dir / f"method_{date_str}_{tag_name}.csv"
            shutil.copy2(method_csv, archive_method)
            print(f"Salvo: {archive_method}")
        else:
            print("Aviso: method.csv não encontrado (pode ser normal)")

    finally:
        # Volta ao commit original
        repo.git.checkout(original_commit.hexsha)

print(f"\nProcessamento concluído. Arquivos salvos em: {archive_dir}")