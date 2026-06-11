#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gráfico da evolução da métrica LOC ao longo das releases.
Deve ser executado no diretório que contém a pasta 'ck_archive'.
"""

import os
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(style="whitegrid", font_scale=1.2)

# ------------------------------------------------------------
# 1. Carregar e preparar os dados
# ------------------------------------------------------------
data_dir = 'ck_archive'
pattern = os.path.join(data_dir, 'class_*.csv')
files = sorted(glob.glob(pattern))

if not files:
    raise FileNotFoundError(f"Nenhum arquivo encontrado em {pattern}")

release_info = []

for fpath in files:
    basename = os.path.basename(fpath)
    parts = basename.split('_', 2)
    date_str = parts[1]              # '2018-11-28-20'
    version = parts[2][:-4]          # 'androidx-test-1.1.0-alpha01'
    dt = pd.to_datetime(date_str, format='%Y-%m-%d-%H')
    release_info.append((version, dt, fpath))

# Ordena por data
release_info.sort(key=lambda x: x[1])

dfs = []
release_names = []
for idx, (version, dt, fpath) in enumerate(release_info):
    df = pd.read_csv(fpath)
    df['release_order'] = idx
    df['release'] = version
    dfs.append(df)
    release_names.append(version)

full_df = pd.concat(dfs, ignore_index=True)

print(f"Total de classes: {full_df.shape[0]}")
print(f"Releases carregadas: {len(release_names)}")

# ------------------------------------------------------------
# 2. Agregar LOC por release
# ------------------------------------------------------------
loc_stats = full_df.groupby('release_order')['loc'].agg(['mean', 'std', 'count'])
loc_stats['ci95'] = 1.96 * loc_stats['std'] / np.sqrt(loc_stats['count'])

# ------------------------------------------------------------
# 3. Plotar gráfico de linha com faixa de confiança
# ------------------------------------------------------------
fig, ax = plt.subplots(figsize=(12, 6))

x = loc_stats.index
y = loc_stats['mean']
ci = loc_stats['ci95']

ax.plot(x, y, marker='o', color='darkgreen', linewidth=2, label='Média do LOC')
ax.fill_between(x, y - ci, y + ci, alpha=0.3, color='darkgreen', label='IC 95%')

# Eixo X com nomes das releases
ax.set_xticks(x)
ax.set_xticklabels(release_names, rotation=45, ha='right', fontsize=8)
ax.set_ylabel('LOC médio')
ax.set_title('Evolução da métrica LOC (Linhas de Código)')

# Linha de tendência linear
z = np.polyfit(x, y, 1)
p = np.poly1d(z)
ax.plot(x, p(x), linestyle='--', color='grey', alpha=0.7, label='Tendência linear')

ax.legend()
plt.tight_layout()

# Salvar gráfico
os.makedirs('ck_archive/plots', exist_ok=True)
output_file = 'ck_archive/plots/evolucao_loc.png'
plt.savefig(output_file, dpi=150)
print(f"Gráfico salvo em: {output_file}")
plt.show()