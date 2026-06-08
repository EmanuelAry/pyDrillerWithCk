import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import re

# ================= CONFIGURAÇÕES =================
archive_dir = Path(r'C:\Users\Emanuel\Documents\pt-BR\pyDriller\ck_archive')
output_plots_dir = archive_dir / 'plots'
output_plots_dir.mkdir(exist_ok=True)

# ================= LEITURA DE TODOS OS CSVs =================
class_files = list(archive_dir.glob('class_*.csv'))
method_files = list(archive_dir.glob('method_*.csv'))

# Função para extrair data e tag do nome do arquivo
# Exemplo: class_2018-11-28-20_androidx-test-1.1.0-alpha01.csv
pattern = r'(class|method)_(\d{4}-\d{2}-\d{2}-\d{2})_(.+)\.csv'

def parse_filename(filename):
    match = re.match(pattern, filename.name)
    if match:
        return match.group(2), match.group(3)  # date_str, tag
    else:
        # Caso não corresponda (ex: class.csv antigo), tentamos usar a data de modificação
        return None, None

def load_dataframe(files, prefix):
    """Lê e concatena os arquivos, adicionando colunas 'date' e 'tag'."""
    dfs = []
    for f in files:
        date_str, tag = parse_filename(f)
        if date_str is None:
            print(f"Formato de nome não reconhecido: {f.name}, ignorando.")
            continue
        try:
            df = pd.read_csv(f)
            df['date'] = date_str
            df['tag'] = tag
            dfs.append(df)
            print(f"Lido {f.name}: {len(df)} registros")
        except Exception as e:
            print(f"Erro ao ler {f.name}: {e}")
    if dfs:
        full_df = pd.concat(dfs, ignore_index=True)
        # Converte 'date' para datetime para ordenação (formato YYYY-MM-DD-HH)
        full_df['datetime'] = pd.to_datetime(full_df['date'], format='%Y-%m-%d-%H')
        # Ordena por data e cria uma ordem numérica
        full_df = full_df.sort_values('datetime')
        full_df['release_order'] = full_df.groupby('tag').ngroup()  # ordem única por tag
        print(f"Total de {prefix}: {len(full_df)} linhas, {full_df['tag'].nunique()} releases")
        return full_df
    else:
        return pd.DataFrame()

# Carrega dados de classes e métodos
df_class = load_dataframe(class_files, 'classes')
df_method = load_dataframe(method_files, 'methods')

# ================= ANÁLISE E GRÁFICOS =================
sns.set_theme(style="whitegrid")
plt.rcParams['figure.figsize'] = (14, 6)

# --- 1. Evolução de métricas de classes ao longo das releases ---
if not df_class.empty:
    # Seleciona métricas de interesse para classes
    class_metrics = ['wmc', 'dit', 'noc', 'cbo', 'lcom', 'rfc', 'loc']
    # Filtra colunas existentes (para compatibilidade com versões diferentes do CK)
    class_metrics = [m for m in class_metrics if m in df_class.columns]
    
    if class_metrics:
        # a) Boxplot por release (tag) para uma métrica chave (ex: CBO)
        plt.figure()
        sns.boxplot(data=df_class, x='tag', y='cbo', palette='viridis')
        plt.xticks(rotation=90)
        plt.title('Distribuição do CBO por Release (Classes)')
        plt.tight_layout()
        plt.savefig(output_plots_dir / 'class_cbo_boxplot.png')
        plt.show()

        # b) Média de LOC por release (linha)
        avg_loc = df_class.groupby('tag')['loc'].mean().reset_index()
        # Mantém a ordenação temporal
        order = df_class[['tag', 'datetime']].drop_duplicates().sort_values('datetime')
        avg_loc = avg_loc.merge(order, on='tag').sort_values('datetime')
        plt.figure()
        plt.plot(avg_loc['tag'], avg_loc['loc'], marker='o', linestyle='-')
        plt.xticks(rotation=90)
        plt.ylabel('Média de LOC')
        plt.title('Média de Linhas de Código (LOC) por Release (Classes)')
        plt.tight_layout()
        plt.savefig(output_plots_dir / 'class_loc_mean.png')
        plt.show()

        # c) Pairplot para algumas métricas (se muitas releases, pode ficar pesado)
        # Amostra ou usa subset
        subset = df_class[class_metrics].dropna()
        if len(subset) > 1:
            try:
                # Matriz de correlação
                plt.figure()
                sns.heatmap(subset.corr(), annot=True, cmap='coolwarm', fmt=".2f")
                plt.title('Correlação entre Métricas de Classe')
                plt.tight_layout()
                plt.savefig(output_plots_dir / 'class_metrics_corr.png')
                plt.show()
            except Exception as e:
                print(f"Não foi possível gerar mapa de calor: {e}")

# --- 2. Análise de métodos ---
if not df_method.empty:
    # Métricas típicas de método
    method_metrics = ['cbo', 'wmc', 'rfc', 'loc', 'parametersQty']
    method_metrics = [m for m in method_metrics if m in df_method.columns]
    
    if method_metrics:
        # Boxplot de LOC de métodos por release
        plt.figure()
        sns.boxplot(data=df_method, x='tag', y='loc', palette='magma')
        plt.xticks(rotation=90)
        plt.title('Distribuição de LOC dos Métodos por Release')
        plt.tight_layout()
        plt.savefig(output_plots_dir / 'method_loc_boxplot.png')
        plt.show()

        # Evolução da complexidade média (WMC) dos métodos
        avg_wmc = df_method.groupby('tag')['wmc'].mean().reset_index()
        order = df_method[['tag', 'datetime']].drop_duplicates().sort_values('datetime')
        avg_wmc = avg_wmc.merge(order, on='tag').sort_values('datetime')
        plt.figure()
        plt.plot(avg_wmc['tag'], avg_wmc['wmc'], marker='s', color='red')
        plt.xticks(rotation=90)
        plt.ylabel('WMC médio')
        plt.title('Complexidade Ciclomática Média dos Métodos por Release')
        plt.tight_layout()
        plt.savefig(output_plots_dir / 'method_wmc_mean.png')
        plt.show()

# --- 3. Evolução do tamanho do sistema (contagem de classes/métodos) ---
if not df_class.empty:
    class_count = df_class.groupby('tag').size().reset_index(name='count')
    order = df_class[['tag', 'datetime']].drop_duplicates().sort_values('datetime')
    class_count = class_count.merge(order, on='tag').sort_values('datetime')
    plt.figure()
    plt.bar(class_count['tag'], class_count['count'], color='steelblue')
    plt.xticks(rotation=90)
    plt.ylabel('Número de Classes')
    plt.title('Quantidade de Classes por Release')
    plt.tight_layout()
    plt.savefig(output_plots_dir / 'class_count.png')
    plt.show()

if not df_method.empty:
    method_count = df_method.groupby('tag').size().reset_index(name='count')
    order = df_method[['tag', 'datetime']].drop_duplicates().sort_values('datetime')
    method_count = method_count.merge(order, on='tag').sort_values('datetime')
    plt.figure()
    plt.bar(method_count['tag'], method_count['count'], color='coral')
    plt.xticks(rotation=90)
    plt.ylabel('Número de Métodos')
    plt.title('Quantidade de Métodos por Release')
    plt.tight_layout()
    plt.savefig(output_plots_dir / 'method_count.png')
    plt.show()

print(f"\nGráficos salvos em: {output_plots_dir}")