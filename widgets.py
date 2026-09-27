"""Componentes reutilizáveis da interface."""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk
from typing import Callable

from ..config import Metodologia, Nivel
from .tema import Tema, texto_contraste


# =============================================================================
class Cartao(tk.Frame):
    """Cartão com fundo próprio, borda fina e padding. Acompanha o tema."""

    registro: list["Cartao"] = []

    def __init__(self, master, titulo: str | None = None, padding=16, **kw):
        px, py = (padding, padding) if isinstance(padding, int) else padding
        super().__init__(master, padx=px, pady=py, highlightthickness=1, bd=0, **kw)
        Cartao.registro.append(self)
        self.recolorir()
        if titulo:
            ttk.Label(self, text=titulo, style="CardTitulo.TLabel").pack(anchor="w", pady=(0, 8))

    def recolorir(self):
        st = ttk.Style(self)
        bg = st.lookup("Plano.TFrame", "background") or "#FFFFFF"
        borda = st.lookup("Borda.TFrame", "background") or "#E2E5EA"
        self.configure(bg=bg, highlightbackground=borda, highlightcolor=borda)

    @classmethod
    def recolorir_todos(cls):
        vivos = []
        for c in cls.registro:
            try:
                c.recolorir()
                vivos.append(c)
            except tk.TclError:
                pass  # destruído
        cls.registro = vivos


# =============================================================================
class RolagemFrame(ttk.Frame):
    """Frame com barra de rolagem vertical (conteúdo em .interno)."""

    def __init__(self, master, tema: Tema, **kw):
        super().__init__(master, **kw)
        self.tema = tema
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0, bg=tema.fundo)
        self.barra = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.interno = ttk.Frame(self.canvas)
        self._janela = self.canvas.create_window((0, 0), window=self.interno, anchor="nw")
        self.canvas.configure(yscrollcommand=self.barra.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.barra.pack(side="right", fill="y")
        self.interno.bind("<Configure>",
                          lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfigure(self._janela, width=e.width))
        for w in (self.canvas, self.interno):
            w.bind("<Enter>", self._ativar_roda)
            w.bind("<Leave>", self._desativar_roda)

    def _ativar_roda(self, _e=None):
        self.bind_all("<MouseWheel>", self._roda)          # Windows / macOS
        self.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-2, "units"))  # Linux
        self.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(2, "units"))

    def _desativar_roda(self, _e=None):
        self.unbind_all("<MouseWheel>")
        self.unbind_all("<Button-4>")
        self.unbind_all("<Button-5>")

    def _roda(self, e):
        self.canvas.yview_scroll(int(-e.delta / 120) or (-1 if e.delta > 0 else 1), "units")

    def atualizar_tema(self):
        self.canvas.configure(bg=self.tema.fundo)


# =============================================================================
class SeletorEscala(ttk.Frame):
    """Seleção de nota 1–5 em lista, com o rótulo e o significado de cada nível.

    Mostrar todas as descrições lado a lado padroniza o julgamento entre
    avaliadores: a nota escolhida fica justificada pela própria metodologia.
    """

    def __init__(self, master, titulo: str, niveis: dict[int, Nivel],
                 ao_mudar: Callable[[int], None] | None = None, cartao: bool = False, **kw):
        estilo_fr = "Plano.TFrame" if cartao else "TFrame"
        super().__init__(master, style=estilo_fr, **kw)
        self.niveis = niveis
        self.ao_mudar = ao_mudar
        self.var = tk.IntVar(value=0)
        self._suave = "CardSuave.TLabel" if cartao else "Suave.TLabel"
        self._destaque = "CardNegrito.TLabel" if cartao else "Negrito.TLabel"
        self._escolhido = "CardTexto.TLabel" if cartao else "Texto.TLabel"
        self._estilo_fr = estilo_fr
        estilo_rb = "Card.TRadiobutton" if cartao else "TRadiobutton"

        topo = ttk.Frame(self, style=estilo_fr)
        topo.pack(fill="x", pady=(0, 4))
        ttk.Label(topo, text=titulo, style=self._destaque).pack(side="left")
        self.lbl_rotulo = ttk.Label(topo, text="— selecione —", style=self._suave)
        self.lbl_rotulo.pack(side="right")

        grade = ttk.Frame(self, style=estilo_fr)
        grade.pack(fill="x")
        grade.columnconfigure(1, weight=1)
        self._descs: dict[int, ttk.Label] = {}
        for linha, (v, n) in enumerate(niveis.items()):
            rb = ttk.Radiobutton(grade, text=f"{v}  {n.rotulo}", value=v, variable=self.var,
                                 command=self._mudou, style=estilo_rb)
            rb.grid(row=linha, column=0, sticky="nw", pady=1)
            # tk.Label (clássico): cor de fundo sob controle total, sem artefatos do tema
            d = tk.Label(grade, text=n.descricao, justify="left", anchor="w", wraplength=300, bd=0,
                         cursor="hand2")
            d.grid(row=linha, column=1, sticky="ew", padx=(12, 0), pady=(4, 2))
            d.bind("<Button-1>", lambda e, val=v: (self.var.set(val), self._mudou()))
            self._descs[v] = d
        self._grade = grade
        grade.bind("<Configure>", self._ajustar_quebra)
        self._pintar()

    def _ajustar_quebra(self, e):
        col0 = self._grade.grid_bbox(0, 0)[2]
        largura = max(140, e.width - col0 - 16)
        for d in self._descs.values():
            d.configure(wraplength=largura)

    def _pintar(self):
        v = self.var.get()
        st = ttk.Style(self)
        bg = st.lookup(self._estilo_fr, "background") or st.lookup("TFrame", "background")
        for k, d in self._descs.items():
            estilo = self._escolhido if k == v else self._suave
            d.configure(bg=bg, fg=st.lookup(estilo, "foreground") or "#000000",
                        font=st.lookup(estilo, "font") or "TkDefaultFont")
        n = self.niveis.get(v)
        self.lbl_rotulo.configure(text=f"Nota {v} · {n.rotulo}" if n else "— selecione —")

    def _mudou(self):
        self._pintar()
        if self.ao_mudar:
            self.ao_mudar(self.var.get())

    def get(self) -> int:
        return self.var.get()

    def set(self, valor: int | None):
        self.var.set(int(valor or 0))
        self._pintar()


# =============================================================================
class Selo(tk.Label):
    """Selo colorido (nível de risco / classificação)."""

    def __init__(self, master, tema: Tema, fonte=None, **kw):
        super().__init__(master, text="—", font=fonte or tema.f_negrito, padx=12, pady=4,
                         bg=tema.borda, fg=tema.texto, **kw)
        self.tema = tema

    def definir(self, texto: str, cor: str | None):
        if cor:
            self.configure(text=texto, bg=cor, fg=texto_contraste(cor))
        else:
            self.configure(text=texto, bg=self.tema.borda, fg=self.tema.texto)


# =============================================================================
class CartaoKpi(Cartao):
    def __init__(self, master, rotulo: str, **kw):
        super().__init__(master, padding=(16, 10), **kw)
        ttk.Label(self, text=rotulo.upper(), style="CardSuave.TLabel").pack(anchor="w")
        self.valor = ttk.Label(self, text="—", style="CardKpi.TLabel")
        self.valor.pack(anchor="w")

    def definir(self, texto: str):
        self.valor.configure(text=texto)


# =============================================================================
class MapaCalor(tk.Canvas):
    """Matriz 5×5 (probabilidade × impacto) desenhada em Canvas.

    marcadores: lista de (texto, (p, i)) — os códigos dos riscos em cada célula.
    trajetoria: opcional ((p_ini, i_ini), (p_res, i_res)) — seta inerente → residual.
    """

    def __init__(self, master, tema: Tema, m: Metodologia, titulo: str = "",
                 compacto: bool = False, **kw):
        super().__init__(master, highlightthickness=0, bd=0, **kw)
        self.tema, self.m, self.titulo, self.compacto = tema, m, titulo, compacto
        self.marcadores: list[tuple[str, tuple[int, int]]] = []
        self.trajetoria = None
        self.bind("<Configure>", lambda e: self.desenhar())

    def definir(self, marcadores=None, trajetoria=None):
        self.marcadores = marcadores or []
        self.trajetoria = trajetoria
        self.desenhar()

    def desenhar(self):
        self.delete("all")
        t = self.tema
        self.configure(bg=t.cartao)
        w, h = self.winfo_width(), self.winfo_height()
        if w < 50 or h < 50:
            return
        f = t.familia
        topo = 26 if self.titulo else 6
        esq = 30 if self.compacto else 112
        base = 22 if self.compacto else 58
        if self.titulo:
            self.create_text(4, 12, text=self.titulo, anchor="w", font=(f, 11, "bold"), fill=t.texto)
        lado = min((w - esq - 8) / 5, (h - topo - base) / 5)
        x0 = esq + max(0, (w - esq - 8 - lado * 5) / 2)
        y0 = topo

        def centro(p, i):
            return x0 + (i - 0.5) * lado, y0 + (5 - p + 0.5) * lado

        for p in range(1, 6):
            for i in range(1, 6):
                cor = self.m.faixa_risco(p * i).cor
                xa, ya = x0 + (i - 1) * lado, y0 + (5 - p) * lado
                self.create_rectangle(xa + 1, ya + 1, xa + lado - 1, ya + lado - 1,
                                      fill=cor, outline=t.cartao, width=2)
        # rótulos dos eixos
        for p in range(1, 6):
            _, yc = centro(p, 1)
            txt = str(p) if self.compacto else f"{p} {self.m.probabilidade[p].rotulo}"
            self.create_text(x0 - 6, yc, text=txt, anchor="e", font=(f, 8), fill=t.texto_suave)
        fonte_eixo = tkfont.Font(family=f, size=8)
        for i in range(1, 6):
            xc, _ = centro(1, i)
            if self.compacto:
                txt = str(i)
            else:
                rot = self.m.impacto[i].rotulo
                while fonte_eixo.measure(rot) > lado - 4 and len(rot) > 3:
                    rot = rot[:-2] + "…"
                txt = f"{i}\n{rot}"
            self.create_text(xc, y0 + 5 * lado + 4, text=txt, anchor="n", font=fonte_eixo,
                             fill=t.texto_suave, justify="center")
        if not self.compacto:
            self.create_text(x0 + 2.5 * lado, h - 4, text="IMPACTO", anchor="s",
                             font=(f, 8, "bold"), fill=t.texto_suave)
            self.create_text(10, y0 + 2.5 * lado, text="PROBABILIDADE", angle=90,
                             font=(f, 8, "bold"), fill=t.texto_suave)

        # códigos dos riscos por célula
        por_celula: dict[tuple[int, int], list[str]] = {}
        for txt, pos in self.marcadores:
            por_celula.setdefault(pos, []).append(txt)
        for (p, i), cods in por_celula.items():
            xc, yc = centro(p, i)
            cor = self.m.faixa_risco(p * i).cor
            fg = texto_contraste(cor)
            if len(cods) > 3:
                exibe = "\n".join(cods[:2] + [f"+{len(cods) - 2}"])
            else:
                exibe = "\n".join(cods)
            tam = 8 if len(cods) > 1 or lado < 60 else 10
            self.create_text(xc, yc, text=exibe, font=(f, tam, "bold"), fill=fg, justify="center")

        # trajetória inerente → residual
        if self.trajetoria:
            (pa, ia), (pr, ir) = self.trajetoria
            xa, ya = centro(pa, ia)
            xr, yr = centro(pr, ir)
            r = max(6, lado * 0.18)
            if (pa, ia) != (pr, ir):
                self.create_line(xa, ya, xr, yr, width=3, fill="#111111", arrow="last",
                                 arrowshape=(12, 14, 5))
            self.create_oval(xa - r, ya - r, xa + r, ya + r, outline="#111111", width=3)
            self.create_oval(xr - r * 0.7, yr - r * 0.7, xr + r * 0.7, yr + r * 0.7,
                             fill="#111111", outline="#FFFFFF", width=2)


# =============================================================================
def tabela(master, colunas: list[tuple[str, str, int, str]], altura=8, **kw) -> ttk.Treeview:
    """Cria Treeview + scrollbar. colunas = (id, título, largura, âncora)."""
    quadro = ttk.Frame(master)
    tv = ttk.Treeview(quadro, columns=[c[0] for c in colunas], show="headings",
                      height=altura, selectmode="browse", **kw)
    for cid, titulo, larg, anc in colunas:
        tv.heading(cid, text=titulo, anchor=anc)
        tv.column(cid, width=larg, anchor=anc, stretch=anc == "w")
    sb = ttk.Scrollbar(quadro, orient="vertical", command=tv.yview)
    tv.configure(yscrollcommand=sb.set)
    tv.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    tv.quadro = quadro  # para posicionar com pack/grid
    return tv


def campo_texto(master, altura=3) -> tk.Text:
    """Caixa de texto multilinha com aparência próxima do tema."""
    return tk.Text(master, height=altura, wrap="word", relief="flat", bd=0,
                   highlightthickness=1, padx=8, pady=6)


def estilizar_texto(txt: tk.Text, tema: Tema):
    txt.configure(bg=tema.cartao, fg=tema.texto, insertbackground=tema.texto,
                  highlightbackground=tema.borda, highlightcolor="#2F6FED",
                  font=tema.f_normal)


def ler_texto(txt: tk.Text) -> str:
    return txt.get("1.0", "end").strip()


def escrever_texto(txt: tk.Text, valor: str | None):
    txt.delete("1.0", "end")
    txt.insert("1.0", valor or "")
