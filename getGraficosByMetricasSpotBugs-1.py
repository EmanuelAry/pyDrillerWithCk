import os
import re   
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime

# ========= CONFIGURAÇÕES =========
CSV_DIR = Path(r'C:\Users\Emanuel\documents\pt-BR\pyDriller\bugs_archive\release_csvs')
OUTPUT_DIR = Path(r'C:\Users\Emanuel\documents\pt-BR\pyDriller\bugs_archive\spotbugs_plots')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ========= CARREGAR TODOS OS CSVs =========
all_data = []

for csv_file in CSV_DIR.glob('*.csv'):
    try:
        df = pd.read_csv(csv_file)
        if 'release_tag' not in df.columns:
            tag = csv_file.stem
            df['release_tag'] = tag
        all_data.append(df)
    except Exception as e:
        print(f"Erro ao ler {csv_file.name}: {e}")

if not all_data:
    raise FileNotFoundError("Nenhum CSV encontrado em " + str(CSV_DIR))

df = pd.concat(all_data, ignore_index=True)

# ========= LIMPEZA E PREPARAÇÃO =========
df['release_date'] = pd.to_datetime(df['release_date'].str.extract(r'(\d{4}-\d{2}-\d{2})')[0])

def parse_version(v):
    m = re.match(r'(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)(\d+))?', v)
    if m:
        major, minor, patch, pre_type, pre_num = m.groups()
        pre_order = {'alpha':0, 'beta':1, 'rc':2}.get(pre_type, 3) if pre_type else 3
        pre_num = int(pre_num) if pre_num else 0
        return (int(major), int(minor), int(patch), pre_order, pre_num)
    return (0,0,0,0,0)

df['version_tuple'] = df['version'].apply(parse_version)
df = df.sort_values('version_tuple')

# ========= GRÁFICO 1: TOTAL DE ISSUES POR RELEASE =========
total_por_release = df.groupby('release_tag').size().reset_index(name='total')
total_por_release = total_por_release.merge(
    df[['release_tag','release_date']].drop_duplicates(), on='release_tag'
)
total_por_release = total_por_release.sort_values('release_date')

plt.figure(figsize=(12, 5))
plt.plot(total_por_release['release_date'], total_por_release['total'], marker='o', linestyle='-')
plt.title('Total de Bugs SpotBugs por Release')
plt.xlabel('Data da Release')
plt.ylabel('Número de Bugs')
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / '01_total_bugs_por_release.png')
plt.close()

# ========= GRÁFICO 2: ISSUES POR CATEGORIA AO LONGO DO TEMPO =========
cat_pivot = df.pivot_table(
    index='release_date', columns='category', aggfunc='size', fill_value=0
).sort_index()

cat_pivot.plot(kind='line', marker='o', figsize=(12, 6))
plt.title('Bugs por Categoria ao Longo das Releases')
plt.ylabel('Número de Bugs')
plt.xlabel('Data da Release')
plt.legend(title='Categoria', bbox_to_anchor=(1.05, 1), loc='upper left')
plt.tight_layout()
plt.savefig(OUTPUT_DIR / '02_bugs_por_categoria.png')
plt.close()

cat_pivot.plot(kind='bar', stacked=True, figsize=(14, 6))
plt.title('Distribuição de Categorias por Release (Empilhado)')
plt.ylabel('Número de Bugs')
plt.xlabel('Release')
plt.xticks(rotation=45, ha='right')
plt.legend(title='Categoria', bbox_to_anchor=(1.05, 1), loc='upper left')
plt.tight_layout()
plt.savefig(OUTPUT_DIR / '02b_bugs_categoria_empilhado.png')
plt.close()

# ========= GRÁFICO 3: ISSUES POR PRIORIDADE =========
prio_pivot = df.pivot_table(
    index='release_date', columns='priority', aggfunc='size', fill_value=0
).sort_index()

prio_pivot.plot(kind='line', marker='o', figsize=(12, 5))
plt.title('Bugs por Prioridade ao Longo das Releases')
plt.ylabel('Número de Bugs')
plt.xlabel('Data da Release')
plt.legend(title='Prioridade')
plt.tight_layout()
plt.savefig(OUTPUT_DIR / '03_bugs_por_prioridade.png')
plt.close()

# ========= GRÁFICO 4: ISSUES POR ARTEFATO (MÓDULO) =========
art_pivot = df.pivot_table(
    index='release_date', columns='artifact', aggfunc='size', fill_value=0
).sort_index()

art_pivot.plot(kind='line', marker='o', figsize=(12, 6))
plt.title('Bugs por Artefato/Módulo ao Longo das Releases')
plt.ylabel('Número de Bugs')
plt.xlabel('Data da Release')
plt.legend(title='Artefato', bbox_to_anchor=(1.05, 1), loc='upper left')
plt.tight_layout()
plt.savefig(OUTPUT_DIR / '04_bugs_por_artefato.png')
plt.close()

# ========= GRÁFICO 5: TOP 10 TIPOS DE BUG =========
top_types = df['type'].value_counts().head(10)
plt.figure(figsize=(10, 5))
sns.barplot(x=top_types.values, y=top_types.index, palette='viridis')
plt.title('Top 10 Tipos de Bug (SpotBugs)')
plt.xlabel('Ocorrências Totais')
plt.tight_layout()
plt.savefig(OUTPUT_DIR / '05_top10_tipos.png')
plt.close()

# ========= GRÁFICO 6: HEATMAP DE TIPOS POR RELEASE (TOP 15) =========
top15_types = df['type'].value_counts().head(15).index
heat_data = df[df['type'].isin(top15_types)].pivot_table(
    index='type', columns='release_tag', aggfunc='size', fill_value=0
)
ordered_tags = df[['release_tag','release_date']].drop_duplicates().sort_values('release_date')['release_tag']
heat_data = heat_data.reindex(columns=ordered_tags, fill_value=0)

plt.figure(figsize=(14, 8))
sns.heatmap(heat_data, cmap='YlOrRd', annot=True, fmt='d', linewidths=.5)
plt.title('Heatmap dos 15 Tipos Mais Frequentes por Release')
plt.xlabel('Release')
plt.ylabel('Tipo de Bug')
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.savefig(OUTPUT_DIR / '06_heatmap_tipos.png')
plt.close()

print(f"Gráficos salvos em: {OUTPUT_DIR}")