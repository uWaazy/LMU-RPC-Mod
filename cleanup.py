import os
import shutil

# Lista de arquivos para remover (Dev Tools & Configs automáticas)
files_to_remove = [
    "visual_debugger.py",
    "test_lmu_rpc.py",
    "setup_project.py",
    "run_dev.py",
    "PROJECT_STATE.md",
    "TODO.md",
    "lmu_rpc.log",
    "debug_log.txt"
]

# Lista de pastas para remover
folders_to_remove = [
    "__pycache__",
    "build" # Pasta temporária do PyInstaller
]

print("--- Limpando Arquivos de Desenvolvimento ---")

for file in files_to_remove:
    if os.path.exists(file):
        try:
            os.remove(file)
            print(f"🗑️  Removido: {file}")
        except Exception as e:
            print(f"❌ Erro ao remover {file}: {e}")

for folder in folders_to_remove:
    if os.path.exists(folder):
        try:
            shutil.rmtree(folder)
            print(f"📂 Removida pasta: {folder}")
        except Exception as e:
            print(f"❌ Erro ao remover pasta {folder}: {e}")

print("\n✅ Limpeza concluída! O projeto agora contém apenas os arquivos essenciais.")
print("   Use 'run.bat' para testar e 'python build.py release' para compilar.")