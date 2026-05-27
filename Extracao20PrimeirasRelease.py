from pydriller import Repository
from git import Repo
from datetime import datetime  # Import necessário para converter e formatar a data

repo_path = r'C:\Users\Emanuel\Desktop\android_test\android-test'

# Se precisar do PyDriller para minerar commits
repo = Repository(repo_path)

# Para acessar tags, use GitPython diretamente
git_repo = Repo(repo_path)
tags = sorted(git_repo.tags, key=lambda t: t.commit.committed_date)
primeiras_20_tags = tags[:20]

for tag in primeiras_20_tags:
    # Converte o timestamp para datetime e formata como dd/mm/yyyy
    data_formatada = datetime.fromtimestamp(tag.commit.committed_date).strftime('%d/%m/%Y')
    print(f"Tag: {tag.name}, Data: {data_formatada}")