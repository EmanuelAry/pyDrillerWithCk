#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Análise descritiva e gráfica da evolução das métricas CK ao longo das releases.
Gera todos os gráficos sugeridos para classes e métodos.
"""

import os
import glob
import re
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import Patch
import seaborn as sns
from scipy import stats

os.chdir('ck_archive')
warnings.filterwarnings('ignore')
sns.set_theme(style="whitegrid", palette="Set2", font_scale=1.1)

# ------------------------------------------------------------
# 1. Carregamento e preparação dos dados
# ------------------------------------------------------------
def parse_release_filename(filename):
    """Extrai a versão e a data do nome do arquivo."""
    base = os.path.basename(filename)
    # Exemplo: class_2018-11-28-20_androidx-test-1.1.0-alpha01.csv
    parts = base.split('_', 2)          # ['class', '2018-11-28-20', 'androidx-test-1.1.0-alpha01.csv']
    date_part = parts[1]                # '2018-11-28-20'
    version_part = parts[2][:-4]        # remove '.csv'
    # Extrai data ordenável: YYYY-MM-DD-HH
    date_sort = pd.to_datetime(date_part, format='%Y-%m-%d-%H')
    return version_part, date_sort

def load_all_csv(pattern, metric_type='class'):
    """
    Carrega todos os CSVs que seguem o padrão, adiciona colunas
    de release, release_order e filtra se necessário.
    """
    files = sorted(glob.glob(pattern))  # ordena lexicograficamente
    records = []
    release_info = []
    for fpath in files:
        version, date_sort = parse_release_filename(fpath)
        release_info.append((version, date_sort, fpath))
    # Ordena pela data
    release_info.sort(key=lambda x: x[1])
    
    dfs = []
    for idx, (version, dt, fpath) in enumerate(release_info):
        df = pd.read_csv(fpath)
        df['release'] = version
        df['release_order'] = idx   # 0 a N-1
        dfs.append(df)
    full_df = pd.concat(dfs, ignore_index=True)
    # Converte algumas colunas que podem ter '*' no nome (lcom*)
    # Já são lidas normalmente; renomeamos para facilitar acesso
    full_df.rename(columns={'lcom*': 'lcom_star'}, inplace=True)
    return full_df, [v for v, _, _ in release_info]

print("Carregando classes...")
class_df, class_releases = load_all_csv('class_*.csv', 'class')
print(f"Classes: {class_df.shape[0]} registros, {len(class_releases)} releases")
print("Carregando métodos...")
method_df, method_releases = load_all_csv('method_*.csv', 'method')
print(f"Métodos: {method_df.shape[0]} registros, {len(method_releases)} releases")

# Listas de releases ordenadas (usaremos nos gráficos)
class_releases_list = class_releases
method_releases_list = method_releases

# ------------------------------------------------------------
# Funções auxiliares de plotagem
# ------------------------------------------------------------
def savefig(name, dpi=150):
    """Salva a figura atual na pasta plots/ com o nome dado."""
    os.makedirs('plots', exist_ok=True)
    plt.tight_layout()
    plt.savefig(f'plots/{name}', dpi=dpi)
    plt.close()

def set_release_xticks(ax, releases, rotation=45):
    """Configura o eixo x com os nomes das releases."""
    ax.set_xticks(range(len(releases)))
    ax.set_xticklabels(releases, rotation=rotation, ha='right', fontsize=8)
    ax.set_xlim(-0.5, len(releases)-0.5)

# ------------------------------------------------------------
# 2. Gráficos comuns para uma métrica (classe ou método)
# ------------------------------------------------------------
def plot_metric_evolution(df, metric, ylabel, releases, prefix, kind='class'):
    """
    Gera múltiplos gráficos para uma métrica específica:
    - Linha com média e IC 95%
    - Boxplot por release
    - Violin plot
    - Ridgeline (densidade)
    - ECDF por release (sobrepostas)
    """
    data = df[[metric, 'release_order', 'release']].dropna()
    if data.empty:
        return
    
    # --- Linha da média com IC ---
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.lineplot(data=data, x='release_order', y=metric, estimator='mean',
                 errorbar=('ci', 95), marker='o', ax=ax)
    set_release_xticks(ax, releases)
    ax.set_ylabel(ylabel)
    ax.set_title(f'Evolução da média de {metric} ({kind})')
    savefig(f'{prefix}_mean_ci_{metric}.png')
    
    # --- Boxplot ---
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.boxplot(data=data, x='release_order', y=metric, ax=ax)
    set_release_xticks(ax, releases)
    ax.set_ylabel(ylabel)
    ax.set_title(f'Boxplot de {metric} por release ({kind})')
    savefig(f'{prefix}_boxplot_{metric}.png')
    
    # --- Violin plot ---
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.violinplot(data=data, x='release_order', y=metric, inner='quartile', ax=ax)
    set_release_xticks(ax, releases)
    ax.set_ylabel(ylabel)
    ax.set_title(f'Violin plot de {metric} por release ({kind})')
    savefig(f'{prefix}_violin_{metric}.png')
    
    # --- Ridgeline (densidade por release) ---
    releases_unique = sorted(data['release_order'].unique())
    n_releases = len(releases_unique)
    if n_releases > 1:
        fig, axes = plt.subplots(n_releases, 1, figsize=(10, 1.2 * n_releases), sharex=True)
        if n_releases == 1:
            axes = [axes]
        for i, rel in enumerate(releases_unique):
            subset = data[data['release_order'] == rel][metric].dropna()
            # Usamos KDE
            if len(subset) > 1:
                kde = stats.gaussian_kde(subset)
                x_range = np.linspace(data[metric].min(), data[metric].max(), 200)
                axes[i].plot(x_range, kde(x_range), color='steelblue')
                axes[i].fill_between(x_range, kde(x_range), alpha=0.3, color='steelblue')
            axes[i].set_ylabel(releases[rel], rotation=0, ha='right', fontsize=8)
            axes[i].set_yticks([])
            axes[i].spines[['top', 'right', 'left']].set_visible(False)
        axes[-1].set_xlabel(ylabel)
        fig.suptitle(f'Densidades por release - {metric} ({kind})', y=1.02)
        plt.subplots_adjust(hspace=0.1)
        savefig(f'{prefix}_ridgeline_{metric}.png')
    
    # --- ECDF sobrepostas (seleciona primeiras e últimas para não poluir) ---
    step = max(1, n_releases // 5)
    selected_releases = releases_unique[::step]
    fig, ax = plt.subplots(figsize=(10, 5))
    for rel in selected_releases:
        subset = data[data['release_order'] == rel][metric].dropna()
        sns.ecdfplot(subset, label=releases[rel], ax=ax)
    ax.legend(title='Release', fontsize=8)
    ax.set_xlabel(ylabel)
    ax.set_title(f'ECDFs selecionadas de {metric} ({kind})')
    savefig(f'{prefix}_ecdf_{metric}.png')

# ------------------------------------------------------------
# 3. Gráficos de distribuição geral (histogramas sobrepostos)
# ------------------------------------------------------------
def plot_histogram_overlay(df, metric, ylabel, releases, prefix, kind='class'):
    """Histograma sobreposto de algumas releases selecionadas."""
    data = df[[metric, 'release_order', 'release']].dropna()
    # Seleciona a primeira, do meio e a última para comparação
    indices = [0, len(releases)//2, len(releases)-1]
    selected = [i for i in indices if i < len(releases)]
    fig, ax = plt.subplots(figsize=(10, 6))
    for idx, rel_idx in enumerate(selected):
        subset = data[data['release_order'] == rel_idx][metric]
        ax.hist(subset, bins=30, alpha=0.5, label=releases[rel_idx])
    ax.legend()
    ax.set_xlabel(ylabel)
    ax.set_ylabel('Frequência')
    ax.set_title(f'Histograma sobreposto de {metric} ({kind})')
    savefig(f'{prefix}_histogram_overlay_{metric}.png')

# ------------------------------------------------------------
# 4. Heatmap da evolução (métricas médias por release)
# ------------------------------------------------------------
def plot_heatmap_metric_means(df, metrics, releases, prefix, kind='class'):
    """Heatmap com as médias normalizadas das métricas por release."""
    if len(metrics) < 2:
        return
    means = df.groupby('release_order')[metrics].mean()
    # Normaliza por coluna (min-max)
    means_norm = (means - means.min()) / (means.max() - means.min() + 1e-10)
    fig, ax = plt.subplots(figsize=(max(8, len(releases)*0.5), len(metrics)*0.5))
    sns.heatmap(means_norm.T, annot=True, fmt='.2f', cmap='YlOrRd',
                xticklabels=releases, yticklabels=metrics, ax=ax)
    ax.set_title(f'Heatmap das médias normalizadas ({kind})')
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    savefig(f'{prefix}_heatmap_means.png')

# ------------------------------------------------------------
# 5. Matriz de correlação para a última release (ou por release)
# ------------------------------------------------------------
def plot_correlation_heatmap(df, metrics, releases, prefix, kind='class'):
    """Matriz de correlação de Pearson para a release mais recente."""
    last_release = max(df['release_order'])
    subset = df[df['release_order'] == last_release][metrics].dropna()
    if subset.shape[0] < 10:
        return
    corr = subset.corr()
    fig, ax = plt.subplots(figsize=(len(metrics)*0.8, len(metrics)*0.7))
    sns.heatmap(corr, annot=True, fmt='.2f', cmap='coolwarm', center=0,
                square=True, ax=ax, vmin=-1, vmax=1)
    ax.set_title(f'Correlação entre métricas ({kind}) - {releases[last_release]}')
    savefig(f'{prefix}_correlation_heatmap.png')

# ------------------------------------------------------------
# 6. Evolução da correlação entre pares chave
# ------------------------------------------------------------
def plot_correlation_evolution(df, metric_pairs, releases, prefix, kind='class'):
    """Linha mostrando a correlação entre pares de métricas ao longo das releases."""
    for m1, m2 in metric_pairs:
        corrs = []
        for rel in sorted(df['release_order'].unique()):
            subset = df[df['release_order'] == rel][[m1, m2]].dropna()
            if len(subset) > 5:
                corr = subset.corr().iloc[0,1]
            else:
                corr = np.nan
            corrs.append(corr)
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(range(len(corrs)), corrs, marker='o')
        set_release_xticks(ax, releases)
        ax.set_ylabel(f'Correlação ({m1} × {m2})')
        ax.set_title(f'Evolução da correlação {m1} vs {m2} ({kind})')
        ax.axhline(0, linestyle='--', color='grey')
        savefig(f'{prefix}_corr_evolution_{m1}_{m2}.png')

# ------------------------------------------------------------
# 7. Scatter com cor por release
# ------------------------------------------------------------
def plot_scatter_by_release(df, x_metric, y_metric, xlabel, ylabel, releases, prefix, kind='class'):
    """Scatter plot de duas métricas, colorido pela release."""
    data = df[[x_metric, y_metric, 'release_order']].dropna()
    fig, ax = plt.subplots(figsize=(10, 6))
    sc = ax.scatter(data[x_metric], data[y_metric], c=data['release_order'],
                    cmap='viridis', alpha=0.6, s=10)
    cbar = plt.colorbar(sc, ax=ax, ticks=range(len(releases)))
    cbar.ax.set_yticklabels(releases)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(f'{xlabel} vs {ylabel} colorido por release ({kind})')
    savefig(f'{prefix}_scatter_{x_metric}_vs_{y_metric}.png')

# ------------------------------------------------------------
# 8. Proporções de modificadores e visibilidade (stacked bar)
# ------------------------------------------------------------
def plot_modifiers_proportions(df, releases, prefix, kind='class'):
    """Gráfico de barras empilhadas das proporções de métodos/campos por visibilidade."""
    if kind == 'class':
        vis_cols = ['publicMethodsQty', 'privateMethodsQty', 'protectedMethodsQty', 'defaultMethodsQty']
        total_col = 'totalMethodsQty'
    else:
        vis_cols = []   # para métodos não há esse agrupamento
        total_col = None
    if not vis_cols or total_col not in df.columns:
        return
    # Agrega total por release
    agg = df.groupby('release_order')[vis_cols + [total_col]].sum()
    # Calcula proporções
    props = agg[vis_cols].div(agg[total_col], axis=0)
    props = props.fillna(0)
    fig, ax = plt.subplots(figsize=(10, 6))
    props.plot(kind='bar', stacked=True, ax=ax, colormap='Accent')
    set_release_xticks(ax, releases)
    ax.set_ylabel('Proporção')
    ax.set_title(f'Proporção de visibilidade dos métodos ({kind})')
    ax.legend(loc='upper right', bbox_to_anchor=(1.15, 1))
    savefig(f'{prefix}_method_visibility_stacked.png')

    # Para campos
    field_cols = ['publicFieldsQty', 'privateFieldsQty', 'protectedFieldsQty', 'defaultFieldsQty']
    total_fields = 'totalFieldsQty'
    if total_fields in df.columns:
        agg_f = df.groupby('release_order')[field_cols + [total_fields]].sum()
        props_f = agg_f[field_cols].div(agg_f[total_fields], axis=0).fillna(0)
        fig, ax = plt.subplots(figsize=(10, 6))
        props_f.plot(kind='bar', stacked=True, ax=ax, colormap='Set2')
        set_release_xticks(ax, releases)
        ax.set_ylabel('Proporção')
        ax.set_title(f'Proporção de visibilidade dos campos ({kind})')
        ax.legend(loc='upper right', bbox_to_anchor=(1.15, 1))
        savefig(f'{prefix}_field_visibility_stacked.png')

# ------------------------------------------------------------
# 9. Radar chart do perfil médio por release
# ------------------------------------------------------------
def plot_radar_metric_profile(df, metrics, releases, prefix, kind='class'):
    """Radar com a mediana normalizada de várias métricas."""
    # Calcula mediana por release
    medians = df.groupby('release_order')[metrics].median()
    # Normaliza cada métrica pelo máximo absoluto
    norm = medians / medians.max()
    norm = norm.fillna(0)
    
    # Seleciona algumas releases representativas (primeira, meio, última)
    indices = [0, len(releases)//2, len(releases)-1]
    selected = [i for i in indices if i < len(releases)]
    
    # Número de métricas
    N = len(metrics)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]  # fechar
    
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    for idx in selected:
        values = norm.loc[idx].tolist()
        values += values[:1]
        ax.plot(angles, values, 'o-', linewidth=2, label=releases[idx])
        ax.fill(angles, values, alpha=0.1)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metrics)
    ax.set_yticklabels([])
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
    ax.set_title(f'Perfil mediano normalizado ({kind})')
    savefig(f'{prefix}_radar_profile.png')

# ------------------------------------------------------------
# 10. Waterfall chart (variação entre releases consecutivas)
# ------------------------------------------------------------
def plot_waterfall_metric(df, metric, ylabel, releases, prefix, kind='class'):
    """Waterfall das medianas mostrando acréscimos/decréscimos entre releases consecutivas."""
    medians = df.groupby('release_order')[metric].median()
    if len(medians) < 2:
        return
    diffs = medians.diff()
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(medians))
    colors = ['green' if v > 0 else 'red' for v in diffs[1:]]
    # Barra da primeira release (base)
    ax.bar(0, medians.iloc[0], color='blue', alpha=0.7)
    # Barras de diferença
    for i in range(1, len(medians)):
        ax.bar(i, diffs.iloc[i], bottom=medians.iloc[i-1], color=colors[i-1], alpha=0.7)
    # Conecta os valores medianos com linha
    ax.plot(x, medians.values, 'k-o', linewidth=2)
    set_release_xticks(ax, releases)
    ax.set_ylabel(ylabel)
    ax.set_title(f'Waterfall da mediana de {metric} ({kind})')
    savefig(f'{prefix}_waterfall_{metric}.png')

# ------------------------------------------------------------
# 11. Density 2D (hexbin) para pares importantes
# ------------------------------------------------------------
def plot_hexbin_by_release(df, x_metric, y_metric, xlabel, ylabel, releases, prefix, kind='class'):
    """Hexbin plot com faceta por release (seleciona primeiras e última)."""
    data = df[[x_metric, y_metric, 'release_order']].dropna()
    if data.empty:
        return
    releases_sel = [0, len(releases)//2, len(releases)-1]
    # Remove duplicatas e garante que existem
    releases_sel = sorted(set([r for r in releases_sel if r < len(releases)]))
    n = len(releases_sel)
    if n == 0:
        return
    fig, axes = plt.subplots(1, n, figsize=(5*n, 5), sharex=True, sharey=True)
    if n == 1:
        axes = [axes]
    for ax, rel in zip(axes, releases_sel):
        subset = data[data['release_order'] == rel]
        hb = ax.hexbin(subset[x_metric], subset[y_metric], gridsize=20, cmap='YlOrRd', mincnt=1)
        ax.set_title(releases[rel])
        ax.set_xlabel(xlabel)
        if ax is axes[0]:
            ax.set_ylabel(ylabel)
        plt.colorbar(hb, ax=ax)
    fig.suptitle(f'Densidade 2D: {xlabel} × {ylabel} ({kind})')
    savefig(f'{prefix}_hexbin_{x_metric}_{y_metric}.png')

# ------------------------------------------------------------
# 12. Gráficos específicos para métricas de método
# ------------------------------------------------------------
def plot_method_specific(df, releases):
    """Métodos: proporção de JavaDoc, logs, etc."""
    # Proporção de hasJavaDoc (true/false) por release
    if 'hasJavaDoc' in df.columns:
        prop_javadoc = df.groupby('release_order')['hasJavaDoc'].mean() * 100
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(range(len(prop_javadoc)), prop_javadoc, marker='o')
        set_release_xticks(ax, releases)
        ax.set_ylabel('% métodos com JavaDoc')
        ax.set_title('Proporção de métodos com JavaDoc')
        savefig('method_javadoc_proportion.png')
    
    # Log statements médios
    if 'logStatementsQty' in df.columns:
        mean_log = df.groupby('release_order')['logStatementsQty'].mean()
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(range(len(mean_log)), mean_log, marker='o')
        set_release_xticks(ax, releases)
        ax.set_ylabel('Média de logStatementsQty')
        ax.set_title('Média de declarações de log por método')
        savefig('method_log_statements.png')

# ------------------------------------------------------------
# Execução principal
# ------------------------------------------------------------
if __name__ == "__main__":
    # ========== CLASSES ==========
    print("Gerando gráficos para CLASSES...")
    # Lista de métricas numéricas principais (excluindo as de contagem de modificadores, que têm gráfico separado)
    class_metrics_main = [
        'cbo', 'cboModified', 'fanin', 'fanout', 'wmc', 'dit', 'noc', 'rfc',
        'lcom', 'lcom_star', 'tcc', 'lcc',
        'totalMethodsQty', 'totalFieldsQty', 'loc', 'returnQty',
        'loopQty', 'comparisonsQty', 'tryCatchQty', 'parenthesizedExpsQty',
        'stringLiteralsQty', 'numbersQty', 'assignmentsQty', 'mathOperationsQty',
        'variablesQty', 'maxNestedBlocksQty', 'uniqueWordsQty'
    ]
    # Remove métricas que podem não existir
    class_metrics_main = [m for m in class_metrics_main if m in class_df.columns]
    
    # Gera gráficos individuais para as 5 métricas mais importantes
    priority_class = ['cbo', 'cboModified', 'wmc', 'rfc', 'loc', 'lcom', 'lcom_star', 'tcc', 'lcc']
    for metric in [m for m in priority_class if m in class_df.columns]:
        print(f"  Processando {metric}...")
        plot_metric_evolution(class_df, metric, metric, class_releases_list, 'class', 'class')
        plot_histogram_overlay(class_df, metric, metric, class_releases_list, 'class', 'class')
    
    # Heatmap de médias
    plot_heatmap_metric_means(class_df, class_metrics_main, class_releases_list, 'class', 'class')
    
    # Matriz de correlação (última release)
    plot_correlation_heatmap(class_df, class_metrics_main, class_releases_list, 'class', 'class')
    
    # Evolução da correlação para pares chave
    key_pairs_class = [('cbo', 'wmc'), ('rfc', 'wmc'), ('loc', 'wmc'), ('cbo', 'loc'),
                       ('lcom', 'wmc'), ('lcom_star', 'wmc'), ('tcc', 'lcc')]
    key_pairs_class = [(m1, m2) for (m1, m2) in key_pairs_class if m1 in class_df.columns and m2 in class_df.columns]
    plot_correlation_evolution(class_df, key_pairs_class, class_releases_list, 'class', 'class')
    
    # Scatter colorido (ex: CBO vs WMC, LOC vs WMC)
    scatter_pairs = [('cbo', 'wmc'), ('rfc', 'wmc'), ('loc', 'wmc'), ('cbo', 'loc')]
    for x, y in scatter_pairs:
        if x in class_df.columns and y in class_df.columns:
            plot_scatter_by_release(class_df, x, y, x, y, class_releases_list, 'class', 'class')
    
    # Proporções de visibilidade
    plot_modifiers_proportions(class_df, class_releases_list, 'class', 'class')
    
    # Radar profile
    radar_metrics = ['cbo', 'wmc', 'rfc', 'loc', 'lcom', 'lcom_star', 'tcc', 'lcc', 'fanin', 'fanout']
    radar_metrics = [m for m in radar_metrics if m in class_df.columns]
    if len(radar_metrics) >= 3:
        plot_radar_metric_profile(class_df, radar_metrics, class_releases_list, 'class', 'class')
    
    # Waterfall para algumas métricas
    for m in ['loc', 'wmc', 'cbo']:
        plot_waterfall_metric(class_df, m, m, class_releases_list, 'class', 'class')
    
    # Hexbin
    for x, y in [('loc', 'wmc'), ('cbo', 'loc'), ('cbo', 'wmc')]:
        if x in class_df.columns and y in class_df.columns:
            plot_hexbin_by_release(class_df, x, y, x, y, class_releases_list, 'class', 'class')
    
    # ========== MÉTODOS ==========
    print("Gerando gráficos para MÉTODOS...")
    method_metrics_main = [
        'loc', 'wmc', 'rfc', 'cbo', 'cboModified', 'fanin', 'fanout',
        'returnsQty', 'variablesQty', 'parametersQty', 'methodsInvokedQty',
        'methodsInvokedLocalQty', 'methodsInvokedIndirectLocalQty',
        'loopQty', 'comparisonsQty', 'tryCatchQty', 'parenthesizedExpsQty',
        'stringLiteralsQty', 'numbersQty', 'assignmentsQty', 'mathOperationsQty',
        'maxNestedBlocksQty', 'uniqueWordsQty'
    ]
    method_metrics_main = [m for m in method_metrics_main if m in method_df.columns]
    
    priority_method = ['loc', 'wmc', 'cbo', 'parametersQty', 'variablesQty', 'loopQty']
    for metric in [m for m in priority_method if m in method_df.columns]:
        print(f"  Processando {metric}...")
        plot_metric_evolution(method_df, metric, metric, method_releases_list, 'method', 'method')
        plot_histogram_overlay(method_df, metric, metric, method_releases_list, 'method', 'method')
    
    plot_heatmap_metric_means(method_df, method_metrics_main, method_releases_list, 'method', 'method')
    plot_correlation_heatmap(method_df, method_metrics_main, method_releases_list, 'method', 'method')
    
    key_pairs_method = [('loc', 'wmc'), ('cbo', 'loc'), ('parametersQty', 'loc'),
                        ('variablesQty', 'loc'), ('loopQty', 'wmc')]
    key_pairs_method = [(m1, m2) for (m1, m2) in key_pairs_method if m1 in method_df.columns and m2 in method_df.columns]
    plot_correlation_evolution(method_df, key_pairs_method, method_releases_list, 'method', 'method')
    
    # Scatter
    for x, y in [('loc', 'wmc'), ('parametersQty', 'loc'), ('cbo', 'loc')]:
        if x in method_df.columns and y in method_df.columns:
            plot_scatter_by_release(method_df, x, y, x, y, method_releases_list, 'method', 'method')
    
    # Métodos não possuem campos, mas podemos ver proporção de modificadores (static, final, etc.)
    # Os dados incluem 'modifiers'? Sim, é uma string com códigos, mas não é tratável numericamente.
    # Já temos a coluna 'logStatementsQty' e 'hasJavaDoc'.
    plot_method_specific(method_df, method_releases_list)
    
    # Waterfall para métodos
    for m in ['loc', 'wmc', 'parametersQty']:
        plot_waterfall_metric(method_df, m, m, method_releases_list, 'method', 'method')
    
    # Hexbin
    for x, y in [('loc', 'wmc'), ('parametersQty', 'loc')]:
        if x in method_df.columns and y in method_df.columns:
            plot_hexbin_by_release(method_df, x, y, x, y, method_releases_list, 'method', 'method')
    
    print("Todos os gráficos foram salvos na pasta 'plots/'.")