"""
Script de instalação offline — Sistema de Escala FAB
=====================================================
Execute este script no NOVO SERVIDOR (sem internet) para criar o ambiente virtual
e instalar todas as dependências a partir dos arquivos .whl desta pasta.

Pré-requisitos no servidor de destino:
  - Python 3.12 instalado  (python3.12 --version)
  - pip instalado          (python3.12 -m pip --version)

Uso:
  python3.12 instalar.py
  -- ou --
  python3 instalar.py   (se o padrão já for 3.12)
"""

import os
import sys
import subprocess
import venv
from pathlib import Path

PASTA_MODULOS = Path(__file__).parent.resolve()
PASTA_PROJETO = PASTA_MODULOS.parent.resolve()
VENV_DIR = PASTA_PROJETO / ".venv"

PYTHON_MIN = (3, 12)

def verificar_python():
    v = sys.version_info[:2]
    if v < PYTHON_MIN:
        sys.exit(
            f"[ERRO] Python {'.'.join(map(str, PYTHON_MIN))}+ é necessário. "
            f"Versão atual: {sys.version}"
        )
    print(f"[OK] Python {sys.version.split()[0]}")

def criar_venv():
    if VENV_DIR.exists():
        print(f"[INFO] Ambiente virtual já existe em: {VENV_DIR}")
        return
    print(f"[INFO] Criando ambiente virtual em: {VENV_DIR}")
    venv.create(str(VENV_DIR), with_pip=True)
    print("[OK] Ambiente virtual criado.")

def pip_venv():
    """Retorna o caminho do pip dentro do venv."""
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "pip.exe"
    return VENV_DIR / "bin" / "pip"

def instalar_pacotes():
    pip = pip_venv()
    wheels = sorted(PASTA_MODULOS.glob("*.whl"))
    if not wheels:
        sys.exit("[ERRO] Nenhum arquivo .whl encontrado em: " + str(PASTA_MODULOS))

    print(f"\n[INFO] Instalando {len(wheels)} pacote(s) a partir de {PASTA_MODULOS}:")
    for w in wheels:
        print(f"       {w.name}")

    cmd = [
        str(pip), "install",
        "--no-index",
        "--find-links", str(PASTA_MODULOS),
        *[str(w) for w in wheels],
    ]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit("[ERRO] Falha na instalação dos pacotes.")
    print("\n[OK] Todos os pacotes instalados com sucesso.")

def mostrar_proximos_passos():
    if os.name == "nt":
        ativar = rf"{VENV_DIR}\Scripts\activate"
        python_venv = rf"{VENV_DIR}\Scripts\python.exe"
    else:
        ativar = f"source {VENV_DIR}/bin/activate"
        python_venv = f"{VENV_DIR}/bin/python"

    print(f"""
=======================================================
 INSTALAÇÃO CONCLUÍDA
=======================================================

Próximos passos para iniciar o sistema:

1. Ativar o ambiente virtual:
   {ativar}

2. Aplicar as migrações do banco de dados (primeiro uso):
   {python_venv} manage.py migrate --noinput

3. Criar o superusuário (primeiro uso):
   {python_venv} manage.py createsuperuser

4. (Opcional) Popular dados de exemplo:
   {python_venv} manage.py seed_dados

5. Iniciar o servidor de desenvolvimento:
   {python_venv} manage.py runserver 0.0.0.0:8000

   -- OU em produção com Gunicorn --
   {VENV_DIR}/bin/gunicorn --bind 0.0.0.0:8000 --workers 3 core.wsgi:application

6. Coletar arquivos estáticos (produção/Gunicorn):
   {python_venv} manage.py collectstatic --noinput

=======================================================
 Pacotes instalados:
""")
    for w in sorted(PASTA_MODULOS.glob("*.whl")):
        print(f"   • {w.stem}")
    print("=======================================================")

def main():
    print("=" * 55)
    print(" Instalador Offline — Sistema de Escala FAB")
    print("=" * 55)
    verificar_python()
    criar_venv()
    instalar_pacotes()
    mostrar_proximos_passos()

if __name__ == "__main__":
    main()
