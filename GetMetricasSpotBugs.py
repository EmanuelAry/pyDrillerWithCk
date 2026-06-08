import requests
import csv
from pathlib import Path
from datetime import datetime, timezone
from git import Repo
import re

# ================= CONFIGURAÇÕES =================
repo_path = Path(r'C:\Users\Emanuel\Desktop\android_test\android-test')
output_dir = Path(r'C:\Users\Emanuel\Documents\pt-BR\pyDriller\bugs_archive')
jars_dir = output_dir / 'jars'
disponivel_csv = output_dir / 'releases_disponiveis.csv'

# Mapeamento corrigido: nome do módulo -> (groupId, artifactId)
MODULOS_MAP = {
    'runner':        ('androidx.test',         'runner'),
    'core':          ('androidx.test',         'core'),
    'monitor':       ('androidx.test',         'monitor'),
    'orchestrator':  ('androidx.test',         'orchestrator'),
    'ext.junit':     ('androidx.test.ext',     'junit'),
    'services':      ('androidx.test.services','test-services'),
    'ext.truth':     ('androidx.test.ext',     'truth'),
}

# URLs dos repositórios
GOOGLE_MAVEN = 'https://dl.google.com/dl/android/maven2'
CENTRAL      = 'https://repo1.maven.org/maven2'

# ================= FUNÇÕES AUXILIARES =================
def extrair_versao(tag_name):
    """Extrai a versão sem prefixos (ex: 'androidx-test-1.0.0' → '1.0.0')"""
    if '/' in tag_name:
        tag_name = tag_name.split('/')[-1]
    match = re.match(r'^androidx-test-(.+)$', tag_name)
    if match:
        return match.group(1)
    match = re.match(r'^[a-z.]+-(.+)$', tag_name)  # runner-1.0.0, etc.
    if match:
        return match.group(1)
    return tag_name

def jar_url(base, group, artifact, version):
    """Constrói a URL completa do JAR no repositório Maven"""
    group_path = group.replace('.', '/')
    return f"{base}/{group_path}/{artifact}/{version}/{artifact}-{version}.jar"

# ================= PREPARAÇÃO =================
repo = Repo(repo_path)
tags = sorted(repo.tags, key=lambda t: t.commit.committed_date)[:20]

output_dir.mkdir(parents=True, exist_ok=True)
jars_dir.mkdir(exist_ok=True)

releases_disponiveis = []

# ================= CHECAGEM DE DISPONIBILIDADE =================
for tag in tags:
    commit_date = datetime.fromtimestamp(tag.commit.committed_date, tz=timezone.utc)
    date_str = commit_date.strftime('%Y-%m-%d-%H')
    version = extrair_versao(tag.name)
    print(f"\n=== Verificando {tag.name} (v{version}, {date_str}) ===")

    release_jars_dir = jars_dir / version
    release_jars_dir.mkdir(exist_ok=True)

    download_ok = False
    jars_baixados = []

    for nome_mod, (group, artifact) in MODULOS_MAP.items():
        # Tenta Google Maven primeiro
        url = jar_url(GOOGLE_MAVEN, group, artifact, version)
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                jar_path = release_jars_dir / f"{artifact}-{version}.jar"
                with open(jar_path, 'wb') as f:
                    f.write(resp.content)
                jars_baixados.append(jar_path)
                print(f"  [OK] Google: {artifact}-{version}.jar")
                continue
        except Exception:
            pass

        # Fallback Maven Central
        url = jar_url(CENTRAL, group, artifact, version)
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                jar_path = release_jars_dir / f"{artifact}-{version}.jar"
                with open(jar_path, 'wb') as f:
                    f.write(resp.content)
                jars_baixados.append(jar_path)
                print(f"  [OK] Central: {artifact}-{version}.jar")
        except Exception:
            pass

    if jars_baixados:
        releases_disponiveis.append((tag.name, version, date_str, len(jars_baixados)))
        print(f"  ✅ Release disponível ({len(jars_baixados)} JARs baixados)")
    else:
        print("  ❌ Nenhum JAR encontrado")

# ================= SALVA LISTA DE DISPONÍVEIS =================
with open(disponivel_csv, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['tag', 'version', 'date', 'num_jars'])
    writer.writerows(releases_disponiveis)

print(f"\n\nVerificação concluída. {len(releases_disponiveis)} releases disponíveis.")
if releases_disponiveis:
    print("Arquivos salvos em:", disponivel_csv)
else:
    print("Nenhuma release pública encontrada. Será necessário compilar o código fonte.")