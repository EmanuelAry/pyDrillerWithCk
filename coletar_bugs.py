import subprocess
import csv
import requests
import shutil
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
import zipfile
import sys

# ================= CONFIGURAÇÕES =================
# Caminho para o CSV de resumo gerado na etapa anterior
SUMMARY_CSV = Path(r'C:\Users\Emanuel\Documents\pt-BR\pyDriller\bugs_archive\available_releases.csv')
# Diretório de saída (pode ser o mesmo onde está o summary)
OUTPUT_DIR = Path(r'C:\Users\Emanuel\Documents\pt-BR\pyDriller\bugs_archive')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Caminhos do SpotBugs e do plugin FindSecBugs
SPOTBUGS_HOME = Path(r'C:\spotbugs\spotbugs-4.9.8')
FINDSECBUGS_JAR = Path(r'C:\spotbugs\findsecbugs-plugin-1.14.0.jar')
SPOTBUGS_BIN = SPOTBUGS_HOME / 'bin' / 'spotbugs'
if (SPOTBUGS_BIN.with_suffix('.bat')).exists():
    SPOTBUGS_EXEC = str(SPOTBUGS_BIN.with_suffix('.bat'))
else:
    SPOTBUGS_EXEC = str(SPOTBUGS_BIN)

# Diretório de cache para downloads
DOWNLOAD_DIR = OUTPUT_DIR / 'downloads'
DOWNLOAD_DIR.mkdir(exist_ok=True)

# Diretório para os resultados XML do SpotBugs
XML_RESULTS_DIR = OUTPUT_DIR / 'spotbugs_results'
XML_RESULTS_DIR.mkdir(exist_ok=True)

# Diretório para os CSVs finais por release
RELEASE_CSV_DIR = OUTPUT_DIR / 'release_csvs'
RELEASE_CSV_DIR.mkdir(exist_ok=True)

# Mapeamento reverso: artifactId -> groupId (necessário para download)
# Baseado no mapeamento MODULE_TO_MAVEN do script anterior
MODULE_TO_MAVEN = {
    'runner':        ('androidx.test',           'runner'),
    'core':          ('androidx.test',           'core'),
    'monitor':       ('androidx.test',           'monitor'),
    'orchestrator':  ('androidx.test',           'orchestrator'),
    'ext.junit':     ('androidx.test.ext',       'junit'),
    'ext.truth':     ('androidx.test.ext',       'truth'),
    'services':      ('androidx.test.services',  'test-services'),
}
# Inverte para: artifact_id -> group_id
ARTIFACT_TO_GROUP = {v[1]: v[0] for v in MODULE_TO_MAVEN.values()}

# ================= FUNÇÕES AUXILIARES =================

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
    """Verifica se o JAR está disponível diretamente."""
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
    with requests.get(url, stream=True, headers={'User-Agent': 'Mozilla/5.0'}) as r:
        r.raise_for_status()
        with open(local_aar, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

    jar_name = f"{artifact_id}-{version}.jar"
    jar_path = dest_dir / jar_name
    with zipfile.ZipFile(local_aar, 'r') as zf:
        if 'classes.jar' in zf.namelist():
            with zf.open('classes.jar') as source, open(jar_path, 'wb') as target:
                target.write(source.read())
        else:
            raise FileNotFoundError(f"'classes.jar' não encontrado dentro do AAR {local_aar}")

    local_aar.unlink()  # remove o AAR
    return jar_path

def get_or_download_jar(artifact_id, version):
    """
    Garante que o JAR do artefato esteja disponível no cache de downloads.
    Retorna o caminho para o JAR ou None se não encontrado.
    """
    jar_filename = f"{artifact_id}-{version}.jar"
    jar_path = DOWNLOAD_DIR / jar_filename
    if jar_path.exists():
        return jar_path

    # Identifica o groupId
    group_id = ARTIFACT_TO_GROUP.get(artifact_id)
    if not group_id:
        print(f"  [!] artifactId '{artifact_id}' não mapeado para groupId. Pulando.")
        return None

    # Tenta baixar o AAR primeiro
    aar_url = check_aar_exists(group_id, artifact_id, version)
    if aar_url:
        print(f"  Baixando AAR de {aar_url} ...")
        try:
            return download_aar_and_extract_jar(aar_url, artifact_id, version, DOWNLOAD_DIR)
        except Exception as e:
            print(f"  Erro ao extrair AAR: {e}")

    # Tenta baixar o JAR diretamente
    jar_url = check_jar_exists(group_id, artifact_id, version)
    if jar_url:
        print(f"  Baixando JAR de {jar_url} ...")
        try:
            with requests.get(jar_url, stream=True, headers={'User-Agent': 'Mozilla/5.0'}) as r:
                r.raise_for_status()
                with open(jar_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            return jar_path
        except Exception as e:
            print(f"  Erro ao baixar JAR: {e}")

    print(f"  [!] Não foi possível obter {artifact_id}-{version}.jar")
    return None

def run_spotbugs(jar_path, output_xml):
    """Executa o SpotBugs sobre um JAR e gera o relatório XML."""
    cmd = [
        SPOTBUGS_EXEC,
        '-textui',
        '-effort:max',
        '-low',
        '-pluginList', str(FINDSECBUGS_JAR),
        '-xml:withMessages',
        '-output', str(output_xml),
        str(jar_path)
    ]
    print(f"  Executando SpotBugs: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"  [!] SpotBugs falhou para {jar_path.name}: {e.stderr}")
        return False

def parse_spotbugs_xml(xml_path):
    """Extrai lista de defeitos (tipo, categoria, prioridade, mensagem) do XML."""
    bugs = []
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for bug in root.findall('BugInstance'):
            bug_type = bug.get('type', '')
            category = bug.get('category', '')
            priority = bug.get('priority', '')
            # Mensagem curta (dentro de ShortMessage) ou LongMessage
            short_msg_elem = bug.find('ShortMessage')
            long_msg_elem = bug.find('LongMessage')
            message = ''
            if short_msg_elem is not None and short_msg_elem.text:
                message = short_msg_elem.text.strip()
            elif long_msg_elem is not None and long_msg_elem.text:
                message = long_msg_elem.text.strip()
            bugs.append({
                'type': bug_type,
                'category': category,
                'priority': priority,
                'message': message,
            })
    except Exception as e:
        print(f"  [!] Erro ao parsear XML {xml_path}: {e}")
    return bugs

# ================= PROCESSAMENTO PRINCIPAL =================

def process_release(release_tag, release_date, artifacts_str):
    """
    Processa uma release: baixa JARs, roda SpotBugs, coleta defeitos.
    Retorna lista de dicionários com todos os bugs encontrados.
    """
    # Parsing dos artefatos: "core-1.1.0-alpha01; junit-1.1.0-alpha01; truth-1.1.0-alpha01"
    artifacts = []
    for art_ver in artifacts_str.split(';'):
        art_ver = art_ver.strip()
        if '-' not in art_ver:
            continue
        # Separa na última ocorrência de '-' pois versão pode conter '-' (alpha, beta, rc)
        # Mas os artefatos são como 'core-1.1.0-alpha01' – artifactId é 'core', versão é '1.1.0-alpha01'
        # Podemos usar split('-', 1) apenas se artifactId não tiver '-', mas eles não têm.
        # Melhor: separar no primeiro '-' após o artifactId conhecido.
        # Vamos usar partição na primeira ocorrência de '-' após o nome base?
        # Simples: usar regex: ^([a-zA-Z.]+)-(.+)$
        match = re.match(r'^([a-zA-Z.]+?)-(.+)$', art_ver)
        if match:
            artifact = match.group(1)
            version = match.group(2)
            artifacts.append((artifact, version))
        else:
            print(f"  [!] Formato inesperado: {art_ver}")

    # Cria diretório para XMLs desta release
    release_xml_dir = XML_RESULTS_DIR / release_tag
    release_xml_dir.mkdir(exist_ok=True)

    all_bugs = []

    for artifact, version in artifacts:
        print(f"\n  Processando {artifact}-{version} ...")
        jar_path = get_or_download_jar(artifact, version)
        if not jar_path:
            continue

        xml_file = release_xml_dir / f"{artifact}-{version}.xml"
        if not xml_file.exists():
            if not run_spotbugs(jar_path, xml_file):
                continue
        else:
            print(f"  XML já existe, reutilizando {xml_file}")

        bugs = parse_spotbugs_xml(xml_file)
        print(f"  Encontrados {len(bugs)} defeitos.")
        for bug in bugs:
            all_bugs.append({
                'release_tag': release_tag,
                'release_date': release_date,
                'artifact': artifact,
                'version': version,
                **bug
            })
    return all_bugs

def main():
    # Lê o CSV de releases disponíveis
    if not SUMMARY_CSV.exists():
        print(f"Arquivo {SUMMARY_CSV} não encontrado. Execute a etapa anterior primeiro.")
        sys.exit(1)

    with open(SUMMARY_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Carregadas {len(rows)} releases para processamento.\n")

    # Para combinar todos os bugs em um CSV geral (opcional)
    all_bugs_combined = []

    for row in rows:
        release_tag = row['tag']
        release_date = row['date']
        artifacts_str = row['artifacts']
        print(f"=== Processando release: {release_tag} ===")
        bugs = process_release(release_tag, release_date, artifacts_str)
        print(f"Total de defeitos na release: {len(bugs)}")

        # Salva CSV individual da release
        release_csv = RELEASE_CSV_DIR / f"{release_tag}.csv"
        with open(release_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'release_tag', 'release_date', 'artifact', 'version',
                'type', 'category', 'priority', 'message'
            ])
            writer.writeheader()
            writer.writerows(bugs)
        print(f"CSV salvo em: {release_csv}")

        # Acumula para o CSV geral (opcional)
        all_bugs_combined.extend(bugs)

    # Salva um CSV consolidado com todos os defeitos de todas as releases
    if all_bugs_combined:
        combined_csv = OUTPUT_DIR / 'all_releases_bugs.csv'
        with open(combined_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'release_tag', 'release_date', 'artifact', 'version',
                'type', 'category', 'priority', 'message'
            ])
            writer.writeheader()
            writer.writerows(all_bugs_combined)
        print(f"\nCSV consolidado com todos os defeitos salvo em: {combined_csv}")

    print("\nProcessamento concluído.")

if __name__ == '__main__':
    main()