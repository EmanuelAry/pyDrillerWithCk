import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime

# ================= CONFIGURAÇÕES =================
# Caminho do CSV gerado pelo RefactoringMiner
OUTPUT_CSV = Path(r'C:\Users\Emanuel\Documents\pt-BR\pyDriller\bugs_archive\release_refactorings.csv')

# Pasta para salvar os gráficos
GRAPH_DIR = Path(r'C:\Users\Emanuel\Documents\pt-BR\pyDriller\bugs_archive\refectoring_miner_plots')
GRAPH_DIR.mkdir(parents=True, exist_ok=True)

# Estilo dos gráficos
sns.set_theme(style="whitegrid")
plt.rcParams['figure.dpi'] = 120

# ================= FUNÇÕES AUXILIARES =================
def load_and_prepare(csv_path):
    """Carrega o CSV e prepara as colunas para análise."""
    df = pd.read_csv(csv_path)
    # Converte a data (formato 'YYYY-mm-dd-HH') para datetime
    df['release_date'] = pd.to_datetime(df['release_date'], format='%Y-%m-%d-%H')
    # Ordena por data e tag
    df = df.sort_values(['release_date', 'release_tag']).reset_index(drop=True)
    return df

# ================= GRÁFICOS =================
def plot_total_refactorings(df):
    """Gráfico de barras: total de refatorações por release."""
    counts = df.groupby('release_tag').size().reset_index(name='count')
    
    # Ordem cronológica preservada
    order = df[['release_tag', 'release_date']].drop_duplicates().sort_values('release_date')['release_tag']
    
    plt.figure(figsize=(14, 5))
    ax = sns.barplot(data=counts, x='release_tag', y='count', order=order, palette='viridis')
    plt.xticks(rotation=45, ha='right')
    plt.title('Total de Refatorações por Release')
    plt.xlabel('Release Tag')
    plt.ylabel('Número de Refatorações')
    # Adicionar valores sobre as barras
    for p in ax.patches:
        ax.annotate(f'{int(p.get_height())}', (p.get_x() + p.get_width() / 2., p.get_height()),
                    ha='center', va='bottom', fontsize=8)
    plt.tight_layout()
    plt.savefig(GRAPH_DIR / 'total_refactorings_per_release.png')
    plt.show()

def plot_type_distribution(df):
    """Gráfico de pizza e barras: distribuição dos tipos de refatoração (geral)."""
    type_counts = df['refactoring_type'].value_counts()
    
    # Aumenta a largura da figura e ajusta o espaçamento entre subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 7))
    plt.subplots_adjust(wspace=1)  # mais espaço horizontal entre os gráficos
    
    # ---------- Gráfico de Pizza (Top 10 + Outros) ----------
    top10 = type_counts.nlargest(10)
    others = type_counts[~type_counts.index.isin(top10.index)].sum()
    if others > 0:
        top10['Outros'] = others
    
    wedges, texts, autotexts = ax1.pie(
        top10.values,
        labels=top10.index,
        autopct='%1.1f%%',
        startangle=140,
        labeldistance=1.1,
        pctdistance=0.75,
        textprops={'fontsize': 8}   # fonte menor para os nomes
    )
    for t in autotexts:
        t.set_fontsize(7)           # percentuais ainda menores
    ax1.set_title('Distribuição dos Tipos de Refatoração\n(Top 10 + Outros)', fontsize=11)
    
    # ---------- Gráfico de Barras Horizontal ----------
    sns.barplot(x=type_counts.values, y=type_counts.index, ax=ax2, palette='rocket')
    ax2.set_title('Frequência Absoluta por Tipo', fontsize=11)
    ax2.set_xlabel('Contagem')
    ax2.set_ylabel('Tipo de Refatoração')
    # Ajusta fonte do eixo Y se necessário
    if len(type_counts) > 12:
        ax2.tick_params(axis='y', labelsize=8)
    else:
        ax2.tick_params(axis='y', labelsize=10)
    
    # Ajusta layout com bastante folga
    plt.tight_layout(pad=3.0, w_pad=8.0)
    plt.savefig(GRAPH_DIR / 'refactoring_type_distribution.png')
    plt.show()

def plot_types_over_releases(df):
    """Gráfico de barras empilhadas: tipos de refatoração ao longo dos releases."""
    # Tabela pivot: releases x tipo, com contagens
    pivot = df.pivot_table(index='release_tag', columns='refactoring_type', aggfunc='size', fill_value=0)
    
    # Ordenar releases pela data
    release_order = df[['release_tag', 'release_date']].drop_duplicates().sort_values('release_date')['release_tag']
    pivot = pivot.reindex(release_order)
    
    # Selecionar apenas os tipos mais frequentes para clareza (ex: top 8)
    top_types = df['refactoring_type'].value_counts().nlargest(8).index
    pivot_top = pivot[top_types]
    
    plt.figure(figsize=(14, 7))
    pivot_top.plot(kind='bar', stacked=True, colormap='tab20', figsize=(14, 7))
    plt.title('Refatorações por Release (Tipos Principais)')
    plt.xlabel('Release Tag')
    plt.ylabel('Número de Refatorações')
    plt.xticks(rotation=45, ha='right')
    plt.legend(title='Tipo', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(GRAPH_DIR / 'types_over_releases_stacked.png')
    plt.show()
    
    # Versão com linhas (tendências)
    plt.figure(figsize=(14, 7))
    for t in top_types:
        plt.plot(pivot_top.index, pivot_top[t], marker='o', label=t)
    plt.title('Tendência dos Tipos de Refatoração ao Longo dos Releases')
    plt.xlabel('Release Tag')
    plt.ylabel('Contagem')
    plt.xticks(rotation=45, ha='right')
    plt.legend(title='Tipo', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(GRAPH_DIR / 'types_over_releases_lines.png')
    plt.show()

def plot_top_files(df, n=15):
    """Arquivos mais afetados (lado direito, após refatoração)."""
    # Extrai arquivos da coluna 'right_files' (cada entrada pode ter múltiplos separados por ';')
    files = df['right_files'].str.split(';', expand=True).stack().reset_index(drop=True)
    # Remove partes #Lxx para contar o arquivo puro
    files = files.str.replace(r'#L\d+(-L\d+)?', '', regex=True)
    file_counts = files.value_counts().head(n)
    
    plt.figure(figsize=(12, 6))
    sns.barplot(x=file_counts.values, y=file_counts.index, palette='magma')
    plt.title(f'Top {n} Arquivos com Mais Refatorações (lado direito)')
    plt.xlabel('Número de Refatorações')
    plt.ylabel('Arquivo')
    plt.tight_layout()
    plt.savefig(GRAPH_DIR / f'top_{n}_files.png')
    plt.show()

# ================= EXECUÇÃO PRINCIPAL =================
def main():
    if not OUTPUT_CSV.exists():
        print(f"Arquivo CSV não encontrado: {OUTPUT_CSV}")
        return
    
    print("Carregando dados...")
    df = load_and_prepare(OUTPUT_CSV)
    print(f"Registros carregados: {len(df)}")
    print(f"Período: {df['release_date'].min().date()} a {df['release_date'].max().date()}")
    print(f"Releases únicos: {df['release_tag'].nunique()}")
    print(f"Tipos de refatoração distintos: {df['refactoring_type'].nunique()}")
    
    print("\nGerando gráficos...")
    plot_total_refactorings(df)
    plot_type_distribution(df)
    plot_types_over_releases(df)
    plot_top_files(df)
    
    print(f"\nGráficos salvos em: {GRAPH_DIR}")

if __name__ == '__main__':
    main()