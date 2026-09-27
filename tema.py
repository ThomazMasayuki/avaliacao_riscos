"""Tema visual: tema Sun Valley (sv-ttk) + paleta e fontes da aplicação."""
from __future__ import annotations

import json
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

import sv_ttk

from ..config import RAIZ

PREFS = RAIZ / "data" / "preferencias.json"

SIDEBAR_BG = "#14213D"
SIDEBAR_FG = "#E5E9F0"
SIDEBAR_MUTED = "#8FA1C0"
SIDEBAR_ATIVO = "#24365F"
ACENTO = "#2F6FED"


def ler_prefs() -> dict:
    try:
        return json.loads(PREFS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def salvar_prefs(**kw) -> None:
    p = ler_prefs()
    p.update(kw)
    try:
        PREFS.parent.mkdir(parents=True, exist_ok=True)
        PREFS.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _familia() -> str:
    disponiveis = set(tkfont.families())
    for f in ("Inter", "Cantarell", "Noto Sans", "Segoe UI", "Ubuntu", "DejaVu Sans"):
        if f in disponiveis:
            return f
    return tkfont.nametofont("TkDefaultFont").actual("family")


class Tema:
    """Centraliza fontes e cores dependentes do modo claro/escuro."""

    def __init__(self, raiz: tk.Tk):
        self.raiz = raiz
        self.familia = _familia()
        f = self.familia
        self.f_titulo = (f, 18, "bold")
        self.f_subtitulo = (f, 12, "bold")
        self.f_normal = (f, 10)
        self.f_pequena = (f, 9)
        self.f_negrito = (f, 10, "bold")
        self.f_kpi = (f, 22, "bold")
        self.f_badge = (f, 20, "bold")
        self.modo = ler_prefs().get("tema", "light")
        self.aplicar(self.modo)

    # --- cores do modo atual ---------------------------------------------------
    @property
    def escuro(self) -> bool:
        return self.modo == "dark"

    @property
    def fundo(self) -> str:
        return "#1C1C1C" if self.escuro else "#FAFAFA"

    @property
    def cartao(self) -> str:
        # Cartões usam o mesmo fundo do tema (estilo "outlined"); o sv-ttk desenha
        # rótulos com o fundo do tema, então cores diferentes gerariam manchas.
        return self.fundo

    @property
    def texto(self) -> str:
        return "#F2F2F2" if self.escuro else "#1B1B1B"

    @property
    def texto_suave(self) -> str:
        return "#A8A8A8" if self.escuro else "#5F6368"

    @property
    def borda(self) -> str:
        return "#3A3A3A" if self.escuro else "#DADDE3"

    def tinta(self, cor: str, forca: float = 0.22) -> str:
        """Mistura a cor com o fundo (usado em linhas de tabela por nível)."""
        return misturar(cor, self.cartao, forca)

    def aplicar(self, modo: str) -> None:
        self.modo = modo
        sv_ttk.set_theme(modo)
        st = ttk.Style(self.raiz)
        f = self.familia
        st.configure(".", font=(f, 10))
        st.configure("Titulo.TLabel", font=self.f_titulo)
        st.configure("Subtitulo.TLabel", font=self.f_subtitulo)
        st.configure("Suave.TLabel", font=self.f_pequena, foreground=self.texto_suave)
        st.configure("Negrito.TLabel", font=self.f_negrito)
        st.configure("Kpi.TLabel", font=self.f_kpi)
        st.configure("Treeview", rowheight=30, font=(f, 10))
        st.configure("Treeview.Heading", font=(f, 10, "bold"))
        st.configure("Plano.TFrame", background=self.cartao)
        st.configure("Borda.TFrame", background=self.borda)
        st.configure("Card.TRadiobutton", background=self.cartao)
        st.configure("Card.TLabel", background=self.cartao)
        st.configure("CardSuave.TLabel", background=self.cartao, foreground=self.texto_suave,
                     font=self.f_pequena)
        st.configure("CardNegrito.TLabel", background=self.cartao, font=self.f_negrito)
        st.configure("CardTexto.TLabel", background=self.cartao, foreground=self.texto, font=self.f_pequena)
        st.configure("Texto.TLabel", foreground=self.texto, font=self.f_pequena)
        st.configure("CardTitulo.TLabel", background=self.cartao, font=self.f_subtitulo)
        st.configure("CardKpi.TLabel", background=self.cartao, font=self.f_kpi)
        salvar_prefs(tema=modo)


# --- utilidades de cor ------------------------------------------------------
def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def misturar(cor: str, fundo: str, forca: float) -> str:
    a, b = _rgb(cor), _rgb(fundo)
    return "#%02X%02X%02X" % tuple(int(b[i] + (a[i] - b[i]) * forca) for i in range(3))


def texto_contraste(cor: str) -> str:
    r, g, b = _rgb(cor)
    luz = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#111111" if luz > 0.6 else "#FFFFFF"
