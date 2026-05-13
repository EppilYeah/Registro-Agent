import os

# Pastas que você NÃO quer listar
IGNORAR = {'.venv', '__pycache__', '.git', 'node_modules'}

def gerar_arvore(caminho_raiz, arquivo_saida):
    with open(arquivo_saida, 'w', encoding='utf-8') as f:
        for root, dirs, files in os.walk(caminho_raiz):
            # Remove as pastas ignoradas para o os.walk não entrar nelas
            dirs[:] = [d for d in dirs if d not in IGNORAR]
            
            level = root.replace(caminho_raiz, '').count(os.sep)
            indent = ' ' * 4 * level
            f.write(f'{indent}{os.path.basename(root)}/\n')
            
            subindent = ' ' * 4 * (level + 1)
            for file in files:
                if not file.endswith('.pyc'): # ignora compilados
                    f.write(f'{subindent}- {file}\n')

# Roda na pasta atual e salva no txt
gerar_arvore('.', 'estrutura.txt')
print("Arquivo estrutura.txt gerado com sucesso!")