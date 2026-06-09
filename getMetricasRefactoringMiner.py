import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ================= CONFIGURAÇÕES =================
SUMMARY_CSV = Path(r'C:\Users\Emanuel\Documents\pt-BR\pyDriller\bugs_archive\available_releases.csv')

MINER_HOME = Path(r'C:\RefactoringMiner')
MINER_JAR = MINER_HOME / 'refactoring-miner-3.0.12.jar'
LIBS_DIR = MINER_HOME / 'lib'

REPO_PATH = Path(r'C:\Users\Emanuel\Desktop\android_test\android-test')

OUTPUT_DIR = Path(r'C:\Users\Emanuel\Documents\pt-BR\pyDriller\bugs_archive')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MINER_JSON_DIR = OUTPUT_DIR / 'refactoring_miner_jsons'
MINER_JSON_DIR.mkdir(exist_ok=True)
OUTPUT_CSV = OUTPUT_DIR / 'release_refactorings.csv'

MAIN_CLASS = 'org.refactoringminer.RefactoringMiner'

# ================= FUNÇÕES =================
def parse_date(date_str):
    return datetime.strptime(date_str, '%Y-%m-%d-%H')

def build_classpath():
    cp = str(MINER_JAR)
    if LIBS_DIR.exists() and any(LIBS_DIR.glob('*.jar')):
        cp += ';' + str(LIBS_DIR / '*')
    return cp

def run_refactoring_miner(prev_tag, curr_tag, output_json):
    """
    Usa -bt para comparar duas tags.
    Sintaxe: RefactoringMiner -bt <repo> <start-tag> <end-tag> -json <output>
    """
    cmd = [
        'java', '-cp', build_classpath(),
        MAIN_CLASS,
        '-bt', str(REPO_PATH),   # opção correta para entre tags
        prev_tag,                # start-tag
        curr_tag,                # end-tag
        '-json', str(output_json)
    ]
    print(f"  Executando: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"  [!] Falhou para {prev_tag}..{curr_tag}:\n{e.stderr}")
        return False

def extract_refactorings(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    refs = []
    for commit in data.get('commits', []):
        refs.extend(commit.get('refactorings', []))
    return refs

def format_location_list(locations):
    parts = []
    for loc in locations:
        fp = loc.get('filePath', '')
        s = loc.get('startLine')
        e = loc.get('endLine')
        if fp:
            if s and e and s != e:
                parts.append(f"{fp}#L{s}-L{e}")
            elif s:
                parts.append(f"{fp}#L{s}")
            else:
                parts.append(fp)
    return ';'.join(parts) if parts else ''

def process_release_pair(prev_tag, curr_tag, release_date):
    json_file = MINER_JSON_DIR / f"{curr_tag}_from_{prev_tag}.json"
    if json_file.exists():
        print(f"  JSON já existe, reutilizando {json_file}")
    else:
        if not run_refactoring_miner(prev_tag, curr_tag, json_file):
            return []

    refs = extract_refactorings(json_file)
    print(f"  Refatorações encontradas: {len(refs)}")
    rows = []
    for ref in refs:
        rows.append({
            'release_tag': curr_tag,
            'release_date': release_date,
            'refactoring_type': ref.get('type', ''),
            'description': ref.get('description', ''),
            'left_files': format_location_list(ref.get('leftSideLocations', [])),
            'right_files': format_location_list(ref.get('rightSideLocations', []))
        })
    return rows

def main():
    if not SUMMARY_CSV.exists():
        print(f"Arquivo {SUMMARY_CSV} não encontrado.")
        sys.exit(1)

    with open(SUMMARY_CSV, 'r', encoding='utf-8') as f:
        releases = list(csv.DictReader(f))

    print(f"Carregadas {len(releases)} releases.")
    releases.sort(key=lambda r: (parse_date(r['date']), r['tag']))

    all_refs = []
    for i in range(1, len(releases)):
        prev = releases[i-1]
        curr = releases[i]
        print(f"\n=== {prev['tag']} -> {curr['tag']} (data {curr['date']}) ===")
        refs = process_release_pair(prev['tag'], curr['tag'], curr['date'])
        all_refs.extend(refs)

    if all_refs:
        fieldnames = ['release_tag', 'release_date', 'refactoring_type',
                      'description', 'left_files', 'right_files']
        with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_refs)
        print(f"\nCSV consolidado salvo em: {OUTPUT_CSV} ({len(all_refs)} refatorações)")
    else:
        print("\nNenhuma refatoração encontrada.")

if __name__ == '__main__':
    main()