"""Janela principal da aplicação desktop de avaliação de riscos."""
from __future__ import annotations

import os
import platform
import subprocess
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .. import db, excel, servico
from ..config import CAMINHO_PADRAO, ErroMetodologia, carregar
from .paginas import PaginaAvaliacao, PaginaAvaliacoes, PaginaMatriz, PaginaMetodologia
from .widgets import Cartao
from .tema import (ACENTO, SIDEBAR_ATIVO, SIDEBAR_BG, SIDEBAR_FG, SIDEBAR_MUTED, Tema, ler_prefs,
                   salvar_prefs)

NAVEGACAO = [
    ("avaliacoes", "▤   Avaliações", PaginaAvaliacoes),
    ("avaliacao", "✎   Riscos e controles", PaginaAvaliacao),
    ("matriz", "▦   Matriz de riscos", PaginaMatriz),
    ("metodologia", "⚙   Metodologia", PaginaMetodologia),
]


def abrir_no_sistema(caminho: Path | str) -> None:
    caminho = str(caminho)
    try:
        if platform.system() == "Windows":
            os.startfile(caminho)  # type: ignore[attr-defined]
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", caminho])
        else:
            subprocess.Popen(["xdg-open", caminho], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:  # noqa: BLE001
        messagebox.showerror("Não foi possível abrir", f"{caminho}\n\n{e}")


def _pasta_padrao_exportacao() -> Path:
    casa = Path.home()
    for nome in ("Documentos", "Documents"):
        if (casa / nome).is_dir():
            return casa / nome
    return casa


class App:
    def __init__(self):
        self.raiz = tk.Tk(className="AvaliacaoRiscos")
        self.raiz.title("Avaliação de Riscos e Controles")
        self.raiz.geometry("1440x900")
        self.raiz.minsize(1180, 740)
        self.prefs = ler_prefs()
        self.tema = Tema(self.raiz)
        try:
            self.m = carregar()
        except (ErroMetodologia, KeyError, OSError) as e:
            messagebox.showerror("Metodologia inválida", f"Erro ao ler {CAMINHO_PADRAO}:\n\n{e}")
            raise SystemExit(1)
        self.aval_id: int | None = self.prefs.get("ultima_avaliacao")
        with db.conectar() as con:
            if self.aval_id and not db.obter_avaliacao(con, self.aval_id):
                self.aval_id = None
        self.pagina_atual = "avaliacoes"

        self._montar_barra_lateral()
        self.conteudo = ttk.Frame(self.raiz)
        self.conteudo.pack(side="left", fill="both", expand=True)
        self.lbl_status = ttk.Label(self.conteudo, text="", style="Suave.TLabel", padding=(24, 4))
        self.lbl_status.pack(side="bottom", fill="x")
        self.area_paginas = ttk.Frame(self.conteudo)
        self.area_paginas.pack(fill="both", expand=True)
        self.area_paginas.rowconfigure(0, weight=1)
        self.area_paginas.columnconfigure(0, weight=1)
        self.paginas: dict = {}
        self._construir_paginas()

        self.raiz.bind("<Control-n>", lambda e: self._atalho("novo"))
        self.raiz.bind("<Control-s>", lambda e: self._atalho("salvar"))
        self.raiz.bind("<Control-e>", lambda e: self.exportar_excel(self.aval_id))
        self.raiz.protocol("WM_DELETE_WINDOW", self._fechar)

        self.atualizar_barra()
        self.mostrar("avaliacao" if self.aval_id else "avaliacoes")
        self.status("Pronto. Atalhos: Ctrl+N novo risco · Ctrl+S salvar risco · Ctrl+E exportar Excel")

    # --- estrutura --------------------------------------------------------------
    def _montar_barra_lateral(self):
        lat = tk.Frame(self.raiz, bg=SIDEBAR_BG, width=250)
        lat.pack(side="left", fill="y")
        lat.pack_propagate(False)
        f = self.tema.familia
        tk.Label(lat, text="◆ Riscos & Controles", bg=SIDEBAR_BG, fg="#FFFFFF",
                 font=(f, 12, "bold"), anchor="w").pack(fill="x", padx=20, pady=(24, 0))
        tk.Label(lat, text="Avaliação de riscos e controles", bg=SIDEBAR_BG, fg=SIDEBAR_MUTED,
                 font=(f, 9), anchor="w").pack(fill="x", padx=20, pady=(2, 24))

        self.botoes_nav = {}
        for chave, texto, _ in NAVEGACAO:
            b = tk.Label(lat, text=texto, bg=SIDEBAR_BG, fg=SIDEBAR_FG, font=(f, 11), anchor="w",
                         padx=20, pady=10, cursor="hand2")
            b.pack(fill="x", padx=10, pady=1)
            b.bind("<Button-1>", lambda e, k=chave: self.mostrar(k))
            b.bind("<Enter>", lambda e, w=b, k=chave: w.configure(
                bg=SIDEBAR_ATIVO) if k != self.pagina_atual else None)
            b.bind("<Leave>", lambda e, w=b, k=chave: w.configure(
                bg=SIDEBAR_BG) if k != self.pagina_atual else None)
            self.botoes_nav[chave] = b

        rodape = tk.Frame(lat, bg=SIDEBAR_BG)
        rodape.pack(side="bottom", fill="x", padx=20, pady=20)
        self.btn_tema = tk.Label(rodape, text="", bg=SIDEBAR_ATIVO, fg=SIDEBAR_FG, font=(f, 9),
                                 padx=10, pady=6, cursor="hand2")
        self.btn_tema.pack(fill="x")
        self.btn_tema.bind("<Button-1>", lambda e: self.alternar_tema())
        self.lbl_versao = tk.Label(rodape, text="", bg=SIDEBAR_BG, fg=SIDEBAR_MUTED, font=(f, 8), anchor="w")
        self.lbl_versao.pack(fill="x", pady=(8, 0))

        caixa = tk.Frame(lat, bg=SIDEBAR_ATIVO)
        caixa.pack(side="bottom", fill="x", padx=20, pady=(0, 4))
        tk.Label(caixa, text="AVALIAÇÃO ABERTA", bg=SIDEBAR_ATIVO, fg=SIDEBAR_MUTED, font=(f, 8, "bold"),
                 anchor="w").pack(fill="x", padx=12, pady=(10, 0))
        self.lbl_aval = tk.Label(caixa, text="", bg=SIDEBAR_ATIVO, fg="#FFFFFF", font=(f, 10, "bold"),
                                 anchor="w", justify="left", wraplength=190)
        self.lbl_aval.pack(fill="x", padx=12)
        self.lbl_aval_info = tk.Label(caixa, text="", bg=SIDEBAR_ATIVO, fg=SIDEBAR_MUTED, font=(f, 9),
                                      anchor="w", justify="left", wraplength=190)
        self.lbl_aval_info.pack(fill="x", padx=12, pady=(0, 10))

    def _construir_paginas(self):
        for p in self.paginas.values():
            p.destroy()
        self.paginas = {}
        for chave, _, classe in NAVEGACAO:
            p = classe(self.area_paginas, self)
            p.grid(row=0, column=0, sticky="nsew")
            self.paginas[chave] = p

    # --- navegação --------------------------------------------------------------
    def mostrar(self, chave: str):
        if self.pagina_atual == "avaliacao" and chave != "avaliacao":
            pag = self.paginas["avaliacao"]
            if pag.alterado() and not messagebox.askyesno(
                    "Alterações não salvas", "O risco em edição não foi salvo. Sair mesmo assim?"):
                return
            pag._foto = None
        self.pagina_atual = chave
        for k, b in self.botoes_nav.items():
            ativo = k == chave
            b.configure(bg=ACENTO if ativo else SIDEBAR_BG, fg="#FFFFFF" if ativo else SIDEBAR_FG,
                        font=(self.tema.familia, 11, "bold" if ativo else "normal"))
        pagina = self.paginas[chave]
        pagina.tkraise()
        pagina.atualizar()

    def abrir_avaliacao(self, aval_id: int, pagina: str = "avaliacao"):
        pag = self.paginas["avaliacao"]
        if self.pagina_atual == "avaliacao" and pag.alterado() and not messagebox.askyesno(
                "Alterações não salvas", "O risco em edição não foi salvo. Descartar?"):
            return
        self.aval_id = aval_id
        pag.risco_id, pag._foto = None, None
        self.salvar_pref(ultima_avaliacao=aval_id)
        self.atualizar_barra()
        self.pagina_atual = ""  # força atualização sem nova confirmação
        self.mostrar(pagina)

    def atualizar_barra(self):
        modo = "☾  Tema escuro" if not self.tema.escuro else "☀  Tema claro"
        self.btn_tema.configure(text=modo)
        self.lbl_versao.configure(text=f"Metodologia {self.m.versao}")
        if self.aval_id:
            with db.conectar() as con:
                a = db.obter_avaliacao(con, self.aval_id)
            if a:
                self.lbl_aval.configure(text=f"{a['area']}")
                self.lbl_aval_info.configure(text=f"{a['periodo']} · {a['status']}\n{a['avaliador']}")
                return
        self.lbl_aval.configure(text="Nenhuma")
        self.lbl_aval_info.configure(text="Abra ou crie em Avaliações")

    # --- ações globais ----------------------------------------------------------
    def status(self, msg: str):
        self.lbl_status.configure(text=f"{datetime.now():%H:%M}  ·  {msg}")

    def salvar_pref(self, **kw):
        self.prefs.update(kw)
        salvar_prefs(**kw)

    def alternar_tema(self):
        self.tema.aplicar("light" if self.tema.escuro else "dark")
        Cartao.recolorir_todos()
        self.atualizar_barra()
        for p in self.paginas.values():
            p.atualizar_tema()
        self.paginas[self.pagina_atual or "avaliacoes"].atualizar()

    def _atalho(self, acao: str):
        if self.pagina_atual != "avaliacao" or not self.aval_id:
            return
        pag = self.paginas["avaliacao"]
        if acao == "novo":
            pag.novo_risco()
        elif acao == "salvar":
            pag.salvar_risco()

    def exportar_excel(self, aval_id: int | None):
        if not aval_id:
            messagebox.showinfo("Exportar", "Abra ou selecione uma avaliação primeiro.")
            return
        if self.pagina_atual == "avaliacao" and self.paginas["avaliacao"].alterado():
            if not messagebox.askyesno("Alterações não salvas",
                                       "O risco em edição não foi salvo e ficará fora do Excel. Continuar?"):
                return
        with db.conectar() as con:
            aval = db.obter_avaliacao(con, aval_id)
            itens = servico.avaliar_avaliacao(con, aval_id, self.m)
        if not itens:
            messagebox.showinfo("Exportar", "A avaliação ainda não tem riscos cadastrados.")
            return
        nome = (f"Matriz_Riscos_{aval['area']}_{aval['periodo']}_{datetime.now():%Y%m%d_%H%M}.xlsx"
                .replace(" ", "_").replace("/", "-"))
        pasta = self.prefs.get("pasta_exportacao") or str(_pasta_padrao_exportacao())
        caminho = filedialog.asksaveasfilename(
            parent=self.raiz, title="Salvar matriz de riscos", initialdir=pasta, initialfile=nome,
            defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if not caminho:
            return
        try:
            excel.exportar(caminho, aval, itens, self.m)
        except PermissionError:
            messagebox.showerror("Erro ao salvar", "Não foi possível salvar. O arquivo está aberto em outro programa?")
            return
        self.salvar_pref(pasta_exportacao=str(Path(caminho).parent))
        self.status(f"Matriz exportada: {caminho}")
        if messagebox.askyesno("Matriz exportada", f"Arquivo salvo em:\n{caminho}\n\nAbrir agora?"):
            abrir_no_sistema(caminho)

    def recarregar_metodologia(self):
        try:
            self.m = carregar()
        except (ErroMetodologia, KeyError, ValueError, OSError) as e:
            messagebox.showerror("Metodologia inválida", f"O arquivo tem um erro e não foi carregado:\n\n{e}")
            return
        atual = self.pagina_atual or "metodologia"
        self._construir_paginas()
        self.atualizar_barra()
        self.pagina_atual = ""
        self.mostrar(atual)
        self.status(f"Metodologia {self.m.versao} recarregada.")

    def abrir_yaml(self):
        abrir_no_sistema(CAMINHO_PADRAO)

    def _fechar(self):
        pag = self.paginas.get("avaliacao")
        if pag and self.pagina_atual == "avaliacao" and pag.alterado():
            if not messagebox.askyesno("Alterações não salvas", "O risco em edição não foi salvo. Fechar mesmo assim?"):
                return
        self.raiz.destroy()

    def executar(self):
        self.raiz.mainloop()


def main():
    App().executar()
