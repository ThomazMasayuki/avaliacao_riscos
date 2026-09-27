#!/usr/bin/env bash
# Instalação no Omarchy / Arch Linux (funciona em outras distros com ajustes no passo 1).
set -euo pipefail
cd "$(dirname "$0")"
RAIZ="$(pwd)"

echo "==> 1/4 Verificando Python e Tk"
if ! python3 -c "import tkinter" 2>/dev/null; then
    echo "    tkinter não encontrado. Instalando o pacote 'tk' (pede senha)..."
    sudo pacman -S --needed --noconfirm tk
fi

echo "==> 2/4 Criando ambiente virtual (.venv)"
if command -v uv >/dev/null 2>&1; then
    uv venv --python "$(command -v python3)" .venv
    uv pip install --python .venv/bin/python -r requirements.txt pytest
else
    python3 -m venv .venv
    .venv/bin/pip install -q --upgrade pip
    .venv/bin/pip install -q -r requirements.txt pytest
fi

echo "==> 3/4 Rodando os testes"
.venv/bin/python -m pytest -q

echo "==> 4/4 Criando atalho no menu de aplicativos"
mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/avaliacao-riscos.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Avaliação de Riscos
Comment=Avaliação de riscos e controles com matriz em Excel
Exec=$RAIZ/.venv/bin/python $RAIZ/app.py
Path=$RAIZ
Icon=office-spreadsheet
Terminal=false
Categories=Office;
StartupWMClass=AvaliacaoRiscos
EOF

echo
echo "Pronto. Abra pelo launcher (procure 'Avaliação de Riscos') ou rode:"
echo "    $RAIZ/.venv/bin/python $RAIZ/app.py"
