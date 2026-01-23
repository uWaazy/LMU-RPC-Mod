import os
import subprocess
import glob
import sys
import shutil
import re
import zipfile
import datetime

def check_python_version():
    if sys.version_info >= (3, 13):
        print("❌ ERRO CRÍTICO: Versão do Python Incompatível (" + sys.version.split()[0] + ")")
        print("   O PyInstaller não suporta versões do Python superiores à 3.12.")
        print("   Para compilar o projeto, por favor, instale e use Python 3.11 ou 3.12.")
        sys.exit(1)

def clean_artifacts():
    """Limpa pastas de build temporárias e arquivos .spec"""
    if os.path.exists("build"):
        try:
            shutil.rmtree("build")
        except Exception as e:
            print(f"⚠️  Aviso: Não foi possível limpar a pasta 'build': {e}")
    
    for f in glob.glob("*.spec"):
        try:
            os.remove(f)
        except: pass

def increment_version(mode):
    """Lê version.py, incrementa a versão e atualiza o BUILD_TYPE."""
    version_file = "version.py"
    
    if not os.path.exists(version_file):
        print("❌ Erro: version.py não encontrado.")
        sys.exit(1)

    with open(version_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Regex para encontrar VERSION e BUILD_TYPE
    ver_match = re.search(r'VERSION\s*=\s*"([^"]+)"', content)
    if not ver_match:
        print("❌ Erro: Variável VERSION não encontrada em version.py")
        sys.exit(1)
    
    old_ver = ver_match.group(1)
    parts = old_ver.split('.')
    
    # Lógica de incremento (Major.Minor)
    if len(parts) >= 2 and parts[-1].isdigit():
        parts[-1] = str(int(parts[-1]) + 1)
        new_ver = ".".join(parts)
    else:
        new_ver = old_ver + ".1"

    # Define BUILD_TYPE
    new_type = "RELEASE" if mode == "release" else "BETA"

    # Substitui no conteúdo
    new_content = re.sub(r'VERSION\s*=\s*"[^"]+"', f'VERSION = "{new_ver}"', content)
    new_content = re.sub(r'BUILD_TYPE\s*=\s*"[^"]+"', f'BUILD_TYPE = "{new_type}"', new_content)

    with open(version_file, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"♻️ Versão atualizada: {old_ver} -> {new_ver}")
    return new_ver

def create_zip(source_file, output_zip):
    """Cria um arquivo ZIP contendo o executável."""
    try:
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(source_file, os.path.basename(source_file))
        print(f"📦 ZIP criado com sucesso: {output_zip}")
    except Exception as e:
        print(f"❌ Erro ao criar ZIP: {e}")

def update_changelog(version, mode):
    """Pergunta ao usuário as mudanças e atualiza o CHANGELOG.md."""
    changelog_path = "CHANGELOG.md"
    date_str = datetime.date.today().strftime("%Y-%m-%d")
    build_label = "Release" if mode == "release" else "Beta"
    
    print(f"\n📝 O que há de novo na v{version} ({build_label})?")
    print("Digite as alterações item por item. Pressione Enter em uma linha vazia para finalizar.")
    
    entries = []
    while True:
        entry = input("- ").strip()
        if not entry:
            break
        entries.append(f"- {entry}")
    
    if not entries:
        print("⚠️ Nenhuma alteração inserida. O Changelog não será atualizado.")
        return

    new_block = f"\n## v{version} ({build_label}) - {date_str}\n" + "\n".join(entries) + "\n"
    
    content = ""
    if os.path.exists(changelog_path):
        with open(changelog_path, "r", encoding="utf-8") as f:
            content = f.read()
            
    # Insere logo após o título principal se existir, ou no topo
    header = "# Changelog"
    if header in content:
        parts = content.split(header, 1)
        final_content = parts[0] + header + "\n" + new_block + parts[1]
    else:
        final_content = header + "\n" + new_block + "\n" + content
        
    with open(changelog_path, "w", encoding="utf-8") as f:
        f.write(final_content)
        
    print(f"✅ CHANGELOG.md atualizado com sucesso!")

def run_build(mode):
    check_python_version()
    
    # 1. Auto-Incremento de Versão
    new_ver = increment_version(mode)
    
    # 2. Atualizar Changelog (Interativo)
    update_changelog(new_ver, mode)
    
    # Caminhos dos submódulos para garantir que o PyInstaller os encontre
    paths_args = [
        "--paths", os.path.abspath("pyLMUSharedMemory"),
        "--paths", os.path.abspath("pyRfactor2SharedMemory")
    ]

    # Comando base do PyInstaller (com todas as correções de dependências)
    base_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--onefile", "--noconsole",
        "--icon=icon.ico",
        "--add-data", "assets;assets",
        "--add-data", "icon.png;.",
        "--add-data", "pequenobanner.png;.",
        "--collect-all", "pystray",
        "--hidden-import=psutil",
        "--hidden-import=PIL",
        "--hidden-import=PIL.Image",
        "--hidden-import=PIL.ImageDraw",
        "lmu_rpc.py"
    ] + paths_args

    clean_artifacts()

    if mode == "release":
        print(f"\n🔨 COMPILANDO VERSÃO FINAL (RELEASE) v{new_ver}...")
        # Saída: dist/LMU_RPC_v{new_ver}.exe
        name = f"LMU_RPC_v{new_ver}"
        cmd = base_cmd + ["--name", name, "--distpath", "dist"]
        try:
            subprocess.check_call(cmd)
            print(f"\n✅ SUCESSO! Arquivo gerado: dist/{name}.exe")
            create_zip(f"dist/{name}.exe", f"dist/{name}.zip")
        except subprocess.CalledProcessError:
            print("\n❌ ERRO FATAL: O PyInstaller falhou.")
            print("   Dica: Verifique se o Python é compatível (3.10-3.12) e se o arquivo .exe não está aberto.")

    elif mode == "betas":
        print(f"\n🔨 COMPILANDO VERSÃO BETA v{new_ver}...")
        name = f"LMU_RPC_Beta_v{new_ver}"
        dist_path = os.path.join("dist", "beta")
        
        # Beta: Sem console agora
        cmd = base_cmd + ["--name", name, "--distpath", dist_path]
        try:
            subprocess.check_call(cmd)
            print(f"\n✅ SUCESSO! Arquivo gerado: {dist_path}\\{name}.exe")
            create_zip(f"{dist_path}\\{name}.exe", f"{dist_path}\\{name}.zip")
        except subprocess.CalledProcessError:
            print("\n❌ ERRO FATAL: O PyInstaller falhou.")
            print("   Dica: Verifique se o Python é compatível (3.10-3.12) e se o arquivo .exe não está aberto.")

    clean_artifacts()

if __name__ == "__main__":
    # Suporte a argumentos de linha de comando para automação
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        if mode in ["betas", "release"]:
            run_build(mode)
            sys.exit(0)

    print("="*40)
    print("   GERENCIADOR DE BUILD - LMU RPC")
    print("="*40)
    print("1. Criar BETA (Auto-Incremento + Console)")
    print("2. Criar RELEASE (Sobrescreve dist/LMU_RPC.exe)")
    print("="*40)
    
    choice = input("Escolha uma opção (1 ou 2): ").strip()
    
    if choice == "1":
        run_build("betas")
    elif choice == "2":
        run_build("release")
    else:
        print("Opção inválida.")