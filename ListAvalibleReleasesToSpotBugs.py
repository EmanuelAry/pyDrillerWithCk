import subprocess
import csv
import requests
import shutil
import re
from pathlib import Path
from datetime import datetime, timezone
from git import Repo
import zipfile

# ================= CONFIGURAÇÕES =================
repo_path = Path(r'C:\Users\Emanuel\Desktop\android_test\android-test')
output_dir = Path(r'C:\Users\Emanuel\Documents\pt-BR\pyDriller\bugs_archive')
output_dir.mkdir(parents=True, exist_ok=True)

# Módulos conhecidos do AndroidX Test (nomes como aparecem nas tags)
KNOWN_MODULES = [
    'runner', 'core', 'monitor', 'orchestrator',
    'ext.junit', 'services', 'ext.truth'
]

# Mapeamento do nome do módulo (tag) -> (groupId, artifactId)
MODULE_TO_MAVEN = {
    'runner':        ('androidx.test',           'runner'),
    'core':          ('androidx.test',           'core'),
    'monitor':       ('androidx.test',           'monitor'),
    'orchestrator':  ('androidx.test',           'orchestrator'),
    'ext.junit':     ('androidx.test.ext',       'junit'),
    'ext.truth':     ('androidx.test.ext',       'truth'),
    'services':      ('androidx.test.services',  'test-services'),
}

repo = Repo(repo_path)
tags = sorted(repo.tags, key=lambda t: t.commit.committed_date)
print(f"Total de tags no repositório: {len(tags)}")

# ================= FUNÇÕES AUXILIARES =================
def extract_modules_versions(tag_name):
    """
    Retorna uma lista de tuplas (artifactId, version) a partir do nome da tag.
    - Se tag casa com '<modulo>-<versao>' → apenas esse módulo.
    - Se tag começa com 'androidx-test-' → todos os módulos com essa versão.
    - Caso contrário → None (ignorar).
    """
    # Regex para tags por módulo: ex: runner-1.0.0, ext.junit-1.0.0
    pattern = r'^(' + '|'.join(re.escape(m) for m in KNOWN_MODULES) + r')-(.+)$'
    match = re.match(pattern, tag_name)
    if match:
        module = match.group(1)
        version = match.group(2)
        return [(module, version)]

    # Regex para tags unificadas: androidx-test-<versao>
    match = re.match(r'^androidx-test-(.+)$', tag_name)
    if match:
        version = match.group(1)
        return [(m, version) for m in KNOWN_MODULES]

    return None

def check_aar_exists(group_id, artifact_id, version):
    """Verifica se o AAR está disponível no Google Maven ou Maven Central."""
    group_path = group_id.replace('.', '/')
    filename = f"{artifact_id}-{version}.aar"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    urls = [
        f"https://dl.google.com/dl/android/maven2/{group_path}/{artifact_id}/{version}/{filename}",
        f"https://repo1.maven.org/maven2/{group_path}/{artifact_id}/{version}/{filename}"
    ]
    for url in urls:
        try:
            resp = requests.get(url, stream=True, timeout=10, headers=headers)
            if resp.status_code == 200:
                return url
        except requests.RequestException:
            continue
    return None

def check_jar_exists(group_id, artifact_id, version):
    group_path = group_id.replace('.', '/')
    filename = f"{artifact_id}-{version}.jar"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    urls = [
        f"https://dl.google.com/dl/android/maven2/{group_path}/{artifact_id}/{version}/{filename}",
        f"https://repo1.maven.org/maven2/{group_path}/{artifact_id}/{version}/{filename}"
    ]
    
    for url in urls:
        try:
            resp = requests.get(url, stream=True, timeout=10, headers=headers)
            if resp.status_code == 200:
                return url
        except requests.RequestException:
            continue
    return None

def download_aar_and_extract_jar(url, artifact_id, version, dest_dir):
    """Baixa o AAR, extrai o classes.jar e retorna o caminho do JAR."""
    local_aar = dest_dir / f"{artifact_id}-{version}.aar"
    # Baixa o AAR
    with requests.get(url, stream=True, headers={'User-Agent': '...'}) as r:
        r.raise_for_status()
        with open(local_aar, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

    # Extrai o classes.jar de dentro do AAR
    jar_name = f"{artifact_id}-{version}.jar"
    jar_path = dest_dir / jar_name
    with zipfile.ZipFile(local_aar, 'r') as zf:
        if 'classes.jar' in zf.namelist():
            with zf.open('classes.jar') as source, open(jar_path, 'wb') as target:
                target.write(source.read())
        else:
            raise FileNotFoundError(f"'classes.jar' não encontrado dentro do AAR {local_aar}")

    # Remove o AAR para economizar espaço (opcional)
    local_aar.unlink()
    return jar_path

# ================= ETAPA 1: VARREDURA DE DISPONIBILIDADE =================
available_releases = []  # (tag, date_str, [(artifact, version, url)])

for tag in tags:
    commit_date = datetime.fromtimestamp(tag.commit.committed_date, tz=timezone.utc)
    date_str = commit_date.strftime('%Y-%m-%d-%H')
    
    modules_versions = extract_modules_versions(tag.name)
    if not modules_versions:
        continue

    found_jars = []
    for module_name, version in modules_versions:
        if module_name not in MODULE_TO_MAVEN:
            print(f"[{tag.name}] Módulo '{module_name}' não mapeado para coordenadas Maven, pulando.")
            continue

        group_id, artifact_id = MODULE_TO_MAVEN[module_name]
        url = check_aar_exists(group_id, artifact_id, version)
        if url:
            found_jars.append((artifact_id, version, url))
            print(f"[{tag.name}] Encontrado: {artifact_id}-{version}.jar")
        else:
            print(f"[{tag.name}] Não encontrado: {artifact_id}-{version}.jar")

    if found_jars:
        available_releases.append((tag, date_str, found_jars))

print(f"\nTotal de tags com pelo menos um artefato disponível: {len(available_releases)}")

# Salvar lista das releases disponíveis
summary_csv = output_dir / 'available_releases.csv'
with open(summary_csv, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['tag', 'date', 'artifacts'])
    for tag, date_str, found in available_releases:
        artifacts_str = "; ".join(f"{a}-{v}" for a, v, _ in found)
        writer.writerow([tag.name, date_str, artifacts_str])
print(f"Resumo salvo em: {summary_csv}")
print("\nProcessamento concluído. Dados em:", output_dir)