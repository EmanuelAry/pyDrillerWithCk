import subprocess, csv, shutil, re
from pathlib import Path
from datetime import datetime
from git import Repo

repo_path = Path(r'C:\Users\Emanuel\Desktop\android_test\android-test')
ck_jar_path = Path(r'C:\Users\Emanuel\Documents\pt-BR\pyDriller\ck\ck\target\ck-0.7.1-SNAPSHOT-jar-with-dependencies.jar')
output_dir = Path(r'C:\Users\Emanuel\Documents\pt-BR\pyDriller\output_ck')      # diretório temporário do CK
archive_dir = Path(r'C:\Users\Emanuel\Documents\pt-BR\pyDriller\ck_archive')    # onde serão guardados os CSVs por release

repo = Repo(repo_path)
tags = sorted(repo.tags, key=lambda t: t.commit.committed_date)[:20]
original_commit = repo.head.commit

archive_dir.mkdir(parents=True, exist_ok=True)

for tag in tags:
    # Obtém a data do commit da tag e formata como ano-mes-dia-hora (UTC)
    commit_date = datetime.utcfromtimestamp(tag.commit.committed_date)
    date_str = commit_date.strftime('%Y-%m-%d-%H')   # ex: 2018-12-12-22

    print(f"\n=== Processando tag: {tag.name} (data: {date_str}) ===")

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

        # --- Salva class.csv ---
        class_csv = output_dir / 'class.csv'
        if class_csv.exists():
            archive_class = archive_dir / f"class_{date_str}.csv"
            shutil.copy2(class_csv, archive_class)
            print(f"Salvo: {archive_class}")

            # Exibe as métricas no console (opcional)
            with open(class_csv, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                print(f"{'Classe':<50} {'WMC':>6} {'DIT':>6} {'NOC':>6} {'CBO':>6} {'LCOM':>6} {'RFC':>6} {'LOC':>6}")
                for row in reader:
                    print(f"{row['class']:<50} {row.get('wmc','?'):>6} {row.get('dit','?'):>6} "
                          f"{row.get('noc','?'):>6} {row.get('cbo','?'):>6} "
                          f"{row.get('lcom','?'):>6} {row.get('rfc','?'):>6} {row.get('loc','?'):>6}")
        else:
            print("Aviso: class.csv não encontrado")

        # --- Salva method.csv (caso exista) ---
        method_csv = output_dir / 'method.csv'
        if method_csv.exists():
            archive_method = archive_dir / f"method_{date_str}.csv"
            shutil.copy2(method_csv, archive_method)
            print(f"Salvo: {archive_method}")
        else:
            print("Aviso: method.csv não encontrado (pode ser normal)")

    finally:
        # Volta ao commit original
        repo.git.checkout(original_commit.hexsha)

print(f"\nProcessamento concluído. Arquivos salvos em: {archive_dir}")