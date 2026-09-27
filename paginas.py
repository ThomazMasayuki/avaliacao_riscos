"""Páginas da aplicação."""
from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from .. import db, servico
from ..calculo import EntradaControle, avaliar_risco
from .dialogo_controle import DialogoControle
from .widgets import (Cartao, CartaoKpi, MapaCalor, RolagemFrame, Selo, SeletorEscala,
                      campo_texto, escrever_texto, estilizar_texto, ler_texto, tabela)

if TYPE_CHECKING:
    from .app import App


def _periodo_atual() -> str:
    hoje = date.today()
    return f"{hoje.year}-T{(hoje.month - 1) // 3 + 1}"


def _cortar(txt: str, n: int) -> str:
    txt = (txt or "").replace("\n", " ")
    return txt if len(txt) <= n else txt[: n - 1] + "…"


class Pagina(ttk.Frame):
    titulo = ""

    def __init__(self, master, app: "App"):
        super().__init__(master, padding=(24, 20))
        self.app = app

    @property
    def m(self):
        return self.app.m

    @property
    def tema(self):
        return self.app.tema

    def atualizar(self):
        pass

    def atualizar_tema(self):
        self.atualizar()

    def cabecalho(self, titulo: str, subtitulo: str = "") -> ttk.Frame:
        topo = ttk.Frame(self)
        topo.pack(fill="x", pady=(0, 14))
        esq = ttk.Frame(topo)
        esq.pack(side="left", fill="x", expand=True)
        self._lbl_titulo = ttk.Label(esq, text=titulo, style="Titulo.TLabel")
        self._lbl_titulo.pack(anchor="w")
        self._lbl_sub = ttk.Label(esq, text=subtitulo, style="Suave.TLabel")
        self._lbl_sub.pack(anchor="w")
        acoes = ttk.Frame(topo)
        acoes.pack(side="right")
        return acoes

    def colorir_niveis(self, tv: ttk.Treeview):
        for f in self.m.faixas_risco:
            tv.tag_configure(f"nivel_{f.rotulo}", background=self.tema.tinta(f.cor, 0.28),
                             foreground=self.tema.texto)


# =============================================================================
# 1. AVALIAÇÕES
# =============================================================================
class PaginaAvaliacoes(Pagina):
    titulo = "Avaliações"

    def __init__(self, master, app):
        super().__init__(master, app)
        acoes = self.cabecalho("Avaliações de risco",
                               "Inicie uma avaliação por área e período ou continue uma existente.")
        ttk.Button(acoes, text="Carregar avaliação de exemplo", command=self._exemplo).pack(side="right")

        corpo = ttk.Frame(self)
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(1, weight=1)
        corpo.rowconfigure(0, weight=1)

        # --- nova avaliação
        nova = Cartao(corpo, "Nova avaliação")
        nova.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        ttk.Label(nova, text="Área avaliada *", style="Card.TLabel").pack(anchor="w")
        self.cb_area = ttk.Combobox(nova, values=self.m.areas, state="readonly", width=32)
        self.cb_area.pack(fill="x", pady=(2, 10))
        ttk.Label(nova, text="Período / ciclo *", style="Card.TLabel").pack(anchor="w")
        self.cb_periodo = ttk.Combobox(nova, width=32, values=self._periodos())
        self.cb_periodo.set(_periodo_atual())
        self.cb_periodo.pack(fill="x", pady=(2, 10))
        ttk.Label(nova, text="Avaliador *", style="Card.TLabel").pack(anchor="w")
        self.ent_avaliador = ttk.Entry(nova)
        self.ent_avaliador.insert(0, self.app.prefs.get("avaliador", ""))
        self.ent_avaliador.pack(fill="x", pady=(2, 10))
        ttk.Label(nova, text="Descrição / escopo", style="Card.TLabel").pack(anchor="w")
        self.txt_desc = campo_texto(nova, 4)
        self.txt_desc.configure(width=36)
        self.txt_desc.pack(fill="x", pady=(2, 14))
        ttk.Button(nova, text="Iniciar avaliação  →", style="Accent.TButton",
                   command=self._criar).pack(fill="x")
        ttk.Label(nova, text="As escalas e listas vêm do arquivo de metodologia.",
                  style="CardSuave.TLabel").pack(anchor="w", pady=(12, 0))

        # --- lista
        lista = Cartao(corpo, "Avaliações registradas")
        lista.grid(row=0, column=1, sticky="nsew")
        self.tv = tabela(lista, [
            ("area", "Área", 170, "w"), ("periodo", "Período", 85, "center"),
            ("avaliador", "Avaliador", 150, "w"), ("status", "Status", 115, "center"),
            ("riscos", "Riscos", 60, "center"), ("controles", "Controles", 80, "center"),
            ("atual", "Atualizada", 130, "center")], altura=14)
        self.tv.quadro.pack(fill="both", expand=True)
        self.tv.bind("<Double-1>", lambda e: self._abrir())
        self.tv.tag_configure("concluida", foreground="#2E7D32")

        bts = ttk.Frame(lista, style="Plano.TFrame")
        bts.pack(fill="x", pady=(12, 0))
        ttk.Button(bts, text="Abrir", style="Accent.TButton", command=self._abrir).pack(side="left")
        ttk.Button(bts, text="Ver matriz", command=self._matriz).pack(side="left", padx=6)
        ttk.Button(bts, text="Exportar Excel", command=self._exportar).pack(side="left")
        ttk.Button(bts, text="Concluir / reabrir", command=self._status).pack(side="left", padx=6)
        ttk.Button(bts, text="Excluir", command=self._excluir).pack(side="right")

    def _periodos(self):
        a = date.today().year
        return [f"{ano}-T{t}" for ano in (a, a - 1) for t in (4, 3, 2, 1)] + [str(a), str(a - 1)]

    def atualizar_tema(self):
        estilizar_texto(self.txt_desc, self.tema)
        self.atualizar()

    def atualizar(self):
        estilizar_texto(self.txt_desc, self.tema)
        self.tv.delete(*self.tv.get_children())
        with db.conectar() as con:
            for a in db.listar_avaliacoes(con):
                self.tv.insert("", "end", iid=str(a["id"]), values=(
                    a["area"], a["periodo"], a["avaliador"], a["status"], a["qtd_riscos"],
                    a["qtd_controles"], a["atualizada_em"].replace("T", " ")[:16]),
                    tags=("concluida",) if a["status"] == "Concluída" else ())
        if self.app.aval_id and self.tv.exists(str(self.app.aval_id)):
            self.tv.selection_set(str(self.app.aval_id))

    def _selecionada(self) -> int | None:
        sel = self.tv.selection()
        if not sel:
            messagebox.showinfo("Selecione", "Selecione uma avaliação na lista.")
            return None
        return int(sel[0])

    def _criar(self):
        area, periodo = self.cb_area.get(), self.cb_periodo.get().strip()
        avaliador = self.ent_avaliador.get().strip()
        if not (area and periodo and avaliador):
            messagebox.showwarning("Campos obrigatórios", "Informe área, período e avaliador.")
            return
        with db.conectar() as con:
            existe = [a for a in db.listar_avaliacoes(con)
                      if a["area"] == area and a["periodo"] == periodo]
            if existe and not messagebox.askyesno(
                    "Avaliação existente",
                    f"Já existe avaliação de {area} em {periodo}. Criar outra mesmo assim?"):
                return
            aid = db.criar_avaliacao(con, area, periodo, avaliador, ler_texto(self.txt_desc), self.m.versao)
        self.app.salvar_pref(avaliador=avaliador)
        escrever_texto(self.txt_desc, "")
        self.app.abrir_avaliacao(aid)

    def _abrir(self):
        aid = self._selecionada()
        if aid:
            self.app.abrir_avaliacao(aid)

    def _matriz(self):
        aid = self._selecionada()
        if aid:
            self.app.abrir_avaliacao(aid, pagina="matriz")

    def _exportar(self):
        aid = self._selecionada()
        if aid:
            self.app.exportar_excel(aid)

    def _status(self):
        aid = self._selecionada()
        if not aid:
            return
        with db.conectar() as con:
            a = db.obter_avaliacao(con, aid)
            novo = "Em andamento" if a["status"] == "Concluída" else "Concluída"
            db.atualizar_status(con, aid, novo)
        self.app.status(f"Avaliação {a['area']} {a['periodo']}: {novo}")
        self.atualizar()
        self.app.atualizar_barra()

    def _excluir(self):
        aid = self._selecionada()
        if not aid:
            return
        if messagebox.askyesno("Excluir avaliação",
                               "Excluir a avaliação com todos os riscos e controles? "
                               "Esta ação não pode ser desfeita.", icon="warning"):
            with db.conectar() as con:
                db.excluir_avaliacao(con, aid)
            if self.app.aval_id == aid:
                self.app.aval_id = None
                self.app.atualizar_barra()
            self.atualizar()

    def _exemplo(self):
        from scripts.exemplo import criar_exemplo
        with db.conectar() as con:
            aid = criar_exemplo(con)
        self.app.status("Avaliação de exemplo criada.")
        self.app.abrir_avaliacao(aid)


# =============================================================================
# 2. RISCOS E CONTROLES (tela de trabalho da avaliação)
# =============================================================================
class PaginaAvaliacao(Pagina):
    titulo = "Riscos e controles"

    def __init__(self, master, app):
        super().__init__(master, app)
        self.risco_id: int | None = None
        self.riscos: list[dict] = []
        self.controles: list[dict] = []
        self._foto: dict | None = None

        acoes = self.cabecalho("Riscos e controles", "")
        ttk.Button(acoes, text="Exportar Excel", command=lambda: self.app.exportar_excel(self.app.aval_id)
                   ).pack(side="right")
        ttk.Button(acoes, text="Ver matriz da área", command=lambda: self.app.mostrar("matriz")
                   ).pack(side="right", padx=8)

        self.vazio = ttk.Label(self, text="Nenhuma avaliação aberta. Vá em Avaliações para iniciar ou abrir uma.",
                               style="Suave.TLabel")
        self.corpo = ttk.Frame(self)
        self.corpo.columnconfigure(1, weight=1)
        self.corpo.columnconfigure(2, minsize=300)
        self.corpo.rowconfigure(0, weight=1)

        self._montar_lista()
        self._montar_formulario()
        self._montar_resultado()

    # --- montagem --------------------------------------------------------------
    def _montar_lista(self):
        c = Cartao(self.corpo, "Riscos da avaliação")
        c.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self.tv = tabela(c, [("cod", "Cód.", 46, "center"), ("risco", "Risco", 150, "w"),
                             ("res", "Residual", 88, "center")], altura=16)
        self.tv.quadro.pack(fill="both", expand=True)
        self.tv.bind("<<TreeviewSelect>>", self._selecionou)
        b = ttk.Frame(c, style="Plano.TFrame")
        b.pack(fill="x", pady=(10, 0))
        ttk.Button(b, text="+ Novo risco", style="Accent.TButton", command=self.novo_risco
                   ).pack(side="left", fill="x", expand=True)
        ttk.Button(b, text="Excluir", command=self._excluir_risco).pack(side="left", padx=(6, 0))
        self.lbl_contagem = ttk.Label(c, text="", style="CardSuave.TLabel")
        self.lbl_contagem.pack(anchor="w", pady=(8, 0))

    def _montar_formulario(self):
        self.rolagem = RolagemFrame(self.corpo, self.tema)
        self.rolagem.grid(row=0, column=1, sticky="nsew")
        area = self.rolagem.interno

        f = Cartao(area)
        f.pack(fill="x", padx=(0, 6))
        self.lbl_form_titulo = ttk.Label(f, text="Novo risco", style="CardTitulo.TLabel")
        self.lbl_form_titulo.pack(anchor="w", pady=(0, 10))
        g = ttk.Frame(f, style="Plano.TFrame")
        g.pack(fill="x")
        g.columnconfigure(0, weight=1)
        g.columnconfigure(1, weight=1)

        def rotulo(txt, r, c, span=1):
            ttk.Label(g, text=txt, style="Card.TLabel").grid(row=r, column=c, columnspan=span, sticky="w",
                                                            padx=(0 if c == 0 else 12, 0))

        rotulo("Processo *", 0, 0)
        rotulo("Categoria do risco *", 0, 1)
        self.cb_processo = ttk.Combobox(g)
        self.cb_processo.grid(row=1, column=0, sticky="ew", pady=(2, 10))
        self.cb_categoria = ttk.Combobox(g, values=self.m.categorias_risco, state="readonly")
        self.cb_categoria.grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=(2, 10))

        rotulo("Descrição do risco *  (evento que pode afetar o objetivo)", 2, 0, span=2)
        self.txt_desc = campo_texto(g, 2)
        self.txt_desc.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(2, 10))
        rotulo("Causa", 4, 0)
        rotulo("Consequência", 4, 1)
        self.txt_causa = campo_texto(g, 2)
        self.txt_causa.grid(row=5, column=0, sticky="ew", pady=(2, 10))
        self.txt_cons = campo_texto(g, 2)
        self.txt_cons.grid(row=5, column=1, sticky="ew", padx=(12, 0), pady=(2, 10))
        rotulo("Responsável pelo risco", 6, 0)
        self.ent_resp = ttk.Entry(g)
        self.ent_resp.grid(row=7, column=0, sticky="ew", pady=(2, 12))

        self.sel_p = SeletorEscala(f, "PROBABILIDADE *", self.m.probabilidade,
                                   ao_mudar=lambda v: self.previa(), cartao=True)
        self.sel_p.pack(fill="x", pady=(4, 10))
        self.sel_i = SeletorEscala(f, "IMPACTO *", self.m.impacto,
                                   ao_mudar=lambda v: self.previa(), cartao=True)
        self.sel_i.pack(fill="x", pady=(0, 10))

        ttk.Label(f, text="Justificativa das notas", style="Card.TLabel").pack(anchor="w")
        self.txt_just = campo_texto(f, 2)
        self.txt_just.pack(fill="x", pady=(2, 12))
        bf = ttk.Frame(f, style="Plano.TFrame")
        bf.pack(fill="x")
        ttk.Button(bf, text="Salvar risco", style="Accent.TButton", command=self.salvar_risco
                   ).pack(side="right")
        ttk.Button(bf, text="Descartar alterações", command=self._recarregar_form).pack(side="right", padx=8)

        # --- controles
        c = Cartao(area)
        c.pack(fill="x", padx=(0, 6), pady=(14, 4))
        topo = ttk.Frame(c, style="Plano.TFrame")
        topo.pack(fill="x", pady=(0, 8))
        ttk.Label(topo, text="Controles do risco", style="CardTitulo.TLabel").pack(side="left")
        self.btn_add_ctrl = ttk.Button(topo, text="+ Adicionar controle", style="Accent.TButton",
                                       command=self._novo_controle)
        self.btn_add_ctrl.pack(side="right")
        self.tv_ctrl = tabela(c, [
            ("cod", "Cód.", 64, "center"), ("desc", "Controle", 150, "w"),
            ("tipo", "Tipo", 40, "center"), ("d", "D", 30, "center"),
            ("o", "O", 30, "center"), ("ef", "Efetividade", 150, "center")], altura=5)
        self.tv_ctrl.quadro.pack(fill="x")
        self.tv_ctrl.bind("<Double-1>", lambda e: self._editar_controle())
        b = ttk.Frame(c, style="Plano.TFrame")
        b.pack(fill="x", pady=(8, 0))
        self.btn_edit_ctrl = ttk.Button(b, text="Editar", command=self._editar_controle)
        self.btn_edit_ctrl.pack(side="left")
        self.btn_del_ctrl = ttk.Button(b, text="Excluir", command=self._excluir_controle)
        self.btn_del_ctrl.pack(side="left", padx=6)
        tipos = "   ".join(f"{t.codigo} = {t.rotulo}" for t in self.m.tipos_controle.values())
        ttk.Label(c, text=f"D = desenho · O = operação   |   {tipos}", style="CardSuave.TLabel",
                  wraplength=420).pack(anchor="w", pady=(6, 0))
        self.lbl_ctrl_info = ttk.Label(c, text="", style="CardSuave.TLabel")
        self.lbl_ctrl_info.pack(anchor="w", pady=(6, 0))
        self._textos = [self.txt_desc, self.txt_causa, self.txt_cons, self.txt_just]

    def _montar_resultado(self):
        c = Cartao(self.corpo, "Resultado em tempo real")
        c.grid(row=0, column=2, sticky="nsew", padx=(14, 0))

        def linha(rotulo):
            ttk.Label(c, text=rotulo.upper(), style="CardSuave.TLabel").pack(anchor="w", pady=(8, 2))
            fr = ttk.Frame(c, style="Plano.TFrame")
            fr.pack(fill="x")
            return fr

        fr = linha("Risco inerente (P × I)")
        self.lbl_ine = ttk.Label(fr, text="—", style="CardKpi.TLabel")
        self.lbl_ine.pack(side="left")
        self.selo_ine = Selo(fr, self.tema)
        self.selo_ine.pack(side="left", padx=10)

        fr = linha("Efetividade combinada dos controles")
        self.lbl_ef = ttk.Label(fr, text="—", style="CardKpi.TLabel")
        self.lbl_ef.pack(side="left")
        self.lbl_ef_det = ttk.Label(fr, text="", style="CardSuave.TLabel")
        self.lbl_ef_det.pack(side="left", padx=10)

        fr = linha("Risco residual")
        self.lbl_res = ttk.Label(fr, text="—", style="CardKpi.TLabel")
        self.lbl_res.pack(side="left")
        self.selo_res = Selo(fr, self.tema)
        self.selo_res.pack(side="left", padx=10)
        self.lbl_reducao = ttk.Label(c, text="", style="CardSuave.TLabel")
        self.lbl_reducao.pack(anchor="w", pady=(4, 0))

        ttk.Label(c, text="POSIÇÃO NA MATRIZ", style="CardSuave.TLabel").pack(anchor="w", pady=(14, 2))
        self.mapa = MapaCalor(c, self.tema, self.m, compacto=True, width=260, height=240)
        self.mapa.pack(fill="x")
        ttk.Label(c, text="○ inerente   ● residual", style="CardSuave.TLabel").pack(anchor="w", pady=(4, 0))
        self.lbl_obs = ttk.Label(c, text="", style="CardSuave.TLabel", wraplength=260, justify="left")
        self.lbl_obs.pack(anchor="w", pady=(10, 0))

    # --- ciclo de vida ------------------------------------------------------------
    def atualizar_tema(self):
        self.rolagem.atualizar_tema()
        for t in self._textos:
            estilizar_texto(t, self.tema)
        self.selo_ine.tema = self.selo_res.tema = self.tema
        self.atualizar(manter=True)

    def atualizar(self, manter: bool = False):
        for t in self._textos:
            estilizar_texto(t, self.tema)
        self.colorir_niveis(self.tv)
        if not self.app.aval_id:
            self.corpo.pack_forget()
            self.vazio.pack(anchor="w", pady=30)
            self._lbl_titulo.configure(text="Riscos e controles")
            self._lbl_sub.configure(text="")
            return
        self.vazio.pack_forget()
        self.corpo.pack(fill="both", expand=True)
        with db.conectar() as con:
            aval = db.obter_avaliacao(con, self.app.aval_id)
            itens = servico.avaliar_avaliacao(con, self.app.aval_id, self.m)
        self.aval = aval
        self._lbl_titulo.configure(text=f"{aval['area']} · {aval['periodo']}")
        self._lbl_sub.configure(text=f"Avaliador: {aval['avaliador']}   ·   Status: {aval['status']}   ·   "
                                     f"Metodologia {self.m.versao}")
        self.riscos = [it.risco for it in itens]
        self.tv.delete(*self.tv.get_children())
        for it in itens:
            r = it.resultado
            self.tv.insert("", "end", iid=str(it.risco["id"]), tags=(f"nivel_{r.nivel_residual}",),
                           values=(it.risco["codigo"], _cortar(it.risco["descricao"], 40),
                                   f"{r.residual:.1f} {r.nivel_residual}"))
        sem = sum(1 for it in itens if not it.controles)
        self.lbl_contagem.configure(text=f"{len(itens)} risco(s) · {sum(len(i.controles) for i in itens)} "
                                         f"controle(s)" + (f" · {sem} sem controle" if sem else ""))
        self.cb_processo.configure(values=sorted({r["processo"] for r in self.riscos}))

        if manter and self.risco_id and self.tv.exists(str(self.risco_id)):
            self.tv.selection_set(str(self.risco_id))
            self._carregar_controles()
        elif self.risco_id and self.tv.exists(str(self.risco_id)):
            self.tv.selection_set(str(self.risco_id))
        elif self.riscos:
            self.tv.selection_set(str(self.riscos[0]["id"]))
        else:
            self.novo_risco(confirmar=False)

    # --- formulário ---------------------------------------------------------------
    def _form(self) -> dict:
        return dict(processo=self.cb_processo.get().strip(), categoria=self.cb_categoria.get(),
                    descricao=ler_texto(self.txt_desc), causa=ler_texto(self.txt_causa),
                    consequencia=ler_texto(self.txt_cons), responsavel=self.ent_resp.get().strip(),
                    probabilidade=self.sel_p.get(), impacto=self.sel_i.get(),
                    justificativa=ler_texto(self.txt_just))

    def _preencher(self, r: dict | None):
        r = r or {}
        self.cb_processo.set(r.get("processo") or "")
        self.cb_categoria.set(r.get("categoria") or "")
        escrever_texto(self.txt_desc, r.get("descricao"))
        escrever_texto(self.txt_causa, r.get("causa"))
        escrever_texto(self.txt_cons, r.get("consequencia"))
        self.ent_resp.delete(0, "end")
        self.ent_resp.insert(0, r.get("responsavel") or "")
        self.sel_p.set(r.get("probabilidade"))
        self.sel_i.set(r.get("impacto"))
        escrever_texto(self.txt_just, r.get("justificativa"))
        self._foto = self._form()

    def alterado(self) -> bool:
        return self._foto is not None and self._form() != self._foto

    def _confirmar_descartar(self) -> bool:
        if self.alterado():
            return messagebox.askyesno("Alterações não salvas",
                                       "O risco atual tem alterações não salvas. Descartar?")
        return True

    def _selecionou(self, _e=None):
        sel = self.tv.selection()
        if not sel:
            return
        rid = int(sel[0])
        if rid == self.risco_id and self._foto is not None:
            return
        if not self._confirmar_descartar():
            if self.risco_id:
                self.tv.selection_set(str(self.risco_id))
            else:
                self.tv.selection_remove(sel)
            return
        self.risco_id = rid
        self._recarregar_form()

    def _recarregar_form(self):
        r = next((x for x in self.riscos if x["id"] == self.risco_id), None)
        if r is None:
            self.risco_id = None
        self._preencher(r)
        self.lbl_form_titulo.configure(text=f"Risco {r['codigo']}" if r else "Novo risco")
        self._carregar_controles()

    def novo_risco(self, confirmar: bool = True):
        if confirmar and not self._confirmar_descartar():
            return
        self.risco_id = None
        self.tv.selection_remove(self.tv.selection())
        self._preencher(None)
        self.lbl_form_titulo.configure(text="Novo risco")
        self._carregar_controles()
        self.cb_processo.focus_set()

    def salvar_risco(self):
        d = self._form()
        faltando = [n for n, k in (("processo", "processo"), ("categoria", "categoria"),
                                   ("descrição", "descricao"), ("probabilidade", "probabilidade"),
                                   ("impacto", "impacto")) if not d[k]]
        if faltando:
            messagebox.showwarning("Campos obrigatórios", "Preencha: " + ", ".join(faltando))
            return
        with db.conectar() as con:
            if self.risco_id:
                db.atualizar_risco(con, self.risco_id, **d)
                msg = "Risco atualizado."
            else:
                self.risco_id = db.criar_risco(con, self.app.aval_id, **d)
                msg = "Risco criado. Agora cadastre os controles que o mitigam."
        self._foto = None
        self.app.status(msg)
        self.atualizar()
        self._recarregar_form()

    def _excluir_risco(self):
        if not self.risco_id:
            return
        r = next(x for x in self.riscos if x["id"] == self.risco_id)
        if messagebox.askyesno("Excluir risco", f"Excluir o risco {r['codigo']} e seus controles?",
                               icon="warning"):
            with db.conectar() as con:
                db.excluir_risco(con, self.risco_id)
            self.risco_id, self._foto = None, None
            self.atualizar()

    # --- controles ----------------------------------------------------------------
    def _carregar_controles(self):
        self.tv_ctrl.delete(*self.tv_ctrl.get_children())
        self.controles = []
        tem_risco = self.risco_id is not None
        for b in (self.btn_add_ctrl, self.btn_edit_ctrl, self.btn_del_ctrl):
            b.configure(state="normal" if tem_risco else "disabled")
        if tem_risco:
            with db.conectar() as con:
                self.controles = db.listar_controles(con, self.risco_id)
            self.lbl_ctrl_info.configure(
                text="Duplo clique para editar." if self.controles else
                "Nenhum controle cadastrado — o residual será igual ao inerente.")
        else:
            self.lbl_ctrl_info.configure(text="Salve o risco para cadastrar os controles.")
        for f in self.m.classificacao_controle:
            self.tv_ctrl.tag_configure(f"cls_{f.rotulo}", background=self.tema.tinta(f.cor, 0.25),
                                       foreground=self.tema.texto)
        self.previa()

    def _risco_atual(self) -> dict:
        base = next((x for x in self.riscos if x["id"] == self.risco_id), {})
        return {**base, **self._form(), "codigo": base.get("codigo", "novo")}

    def _novo_controle(self):
        if not self.risco_id:
            return
        dlg = DialogoControle(self, self.tema, self.m, self._risco_atual())
        self.wait_window(dlg)
        if dlg.resultado:
            with db.conectar() as con:
                db.criar_controle(con, self.risco_id, **dlg.resultado)
            self.app.status("Controle adicionado.")
            self._apos_controle()

    def _editar_controle(self):
        sel = self.tv_ctrl.selection()
        if not sel:
            return
        ctrl = next(c for c in self.controles if c["id"] == int(sel[0]))
        dlg = DialogoControle(self, self.tema, self.m, self._risco_atual(), ctrl)
        self.wait_window(dlg)
        if dlg.resultado:
            with db.conectar() as con:
                db.atualizar_controle(con, ctrl["id"], **dlg.resultado)
            self.app.status(f"Controle {ctrl['codigo']} atualizado.")
            self._apos_controle()

    def _excluir_controle(self):
        sel = self.tv_ctrl.selection()
        if not sel:
            return
        ctrl = next(c for c in self.controles if c["id"] == int(sel[0]))
        if messagebox.askyesno("Excluir controle", f"Excluir o controle {ctrl['codigo']}?"):
            with db.conectar() as con:
                db.excluir_controle(con, ctrl["id"])
            self._apos_controle()

    def _apos_controle(self):
        foto, form = self._foto, self._form()
        self.atualizar(manter=True)
        # preserva o que o usuário digitou no risco e não salvou
        if foto is not None and form != foto:
            self._preencher({**form})
            self._foto = foto
        self._carregar_controles()

    # --- prévia -------------------------------------------------------------------
    def previa(self):
        p, i = self.sel_p.get(), self.sel_i.get()
        entradas = [EntradaControle(c["tipo"], c["desenho"], c["operacao"]) for c in self.controles]
        self.tv_ctrl.delete(*self.tv_ctrl.get_children())
        if p and i:
            r = avaliar_risco(p, i, entradas, self.m)
            rcs = r.controles
        else:
            r = None
            from ..calculo import avaliar_controle
            rcs = [avaliar_controle(e, self.m) for e in entradas]
        for c, rc in zip(self.controles, rcs):
            self.tv_ctrl.insert("", "end", iid=str(c["id"]), tags=(f"cls_{rc.classificacao}",), values=(
                c["codigo"], _cortar(c["descricao"], 60), c["tipo"], c["desenho"], c["operacao"],
                f"{rc.efetividade:.0%} · {rc.classificacao}"))

        if not r:
            for lbl in (self.lbl_ine, self.lbl_ef, self.lbl_res):
                lbl.configure(text="—")
            self.selo_ine.definir("selecione P e I", None)
            self.selo_res.definir("—", None)
            self.lbl_ef_det.configure(text="")
            self.lbl_reducao.configure(text="")
            self.lbl_obs.configure(text="Selecione probabilidade e impacto para calcular o risco.")
            self.mapa.definir()
            return
        self.lbl_ine.configure(text=str(r.inerente))
        self.selo_ine.definir(r.nivel_inerente, r.cor_inerente)
        self.lbl_ef.configure(text=f"{r.efetividade_combinada:.0%}")
        self.lbl_ef_det.configure(
            text=f"prev. {r.efetividade_preventiva:.0%} · det. {r.efetividade_detectiva:.0%}")
        self.lbl_res.configure(text=f"{r.residual:.1f}")
        self.selo_res.definir(r.nivel_residual, r.cor_residual)
        self.lbl_reducao.configure(
            text=f"P {r.probabilidade} → {r.prob_residual:.2f}   ·   I {r.impacto} → {r.impacto_residual:.2f}"
                 f"   ·   redução de {r.reducao:.0%}")
        self.mapa.definir([("", r.posicao_inerente)], (r.posicao_inerente, r.posicao_residual))
        obs = []
        if not self.controles:
            obs.append("Sem controles: residual igual ao inerente.")
        if self.alterado():
            obs.append("Alterações não salvas — clique em Salvar risco.")
        if r.nivel_residual in ("Alto", "Crítico"):
            obs.append("Residual acima do apetite típico: avalie plano de ação.")
        self.lbl_obs.configure(text="\n".join(obs))


# =============================================================================
# 3. MATRIZ DE RISCOS
# =============================================================================
class PaginaMatriz(Pagina):
    titulo = "Matriz de riscos"

    def __init__(self, master, app):
        super().__init__(master, app)
        acoes = self.cabecalho("Matriz de riscos", "")
        ttk.Button(acoes, text="Exportar matriz para Excel", style="Accent.TButton",
                   command=lambda: self.app.exportar_excel(self.app.aval_id)).pack(side="right")
        ttk.Button(acoes, text="Editar riscos", command=lambda: self.app.mostrar("avaliacao")
                   ).pack(side="right", padx=8)

        self.vazio = ttk.Label(self, text="Abra uma avaliação para visualizar a matriz.", style="Suave.TLabel")
        self.corpo = ttk.Frame(self)

        kpis = ttk.Frame(self.corpo)
        kpis.pack(fill="x", pady=(0, 14))
        self.kpis = {}
        for chave, rot in (("riscos", "Riscos"), ("controles", "Controles"), ("sem", "Sem controle"),
                           ("ef", "Efetividade média"), ("ine", "Inerente médio"), ("res", "Residual médio")):
            k = CartaoKpi(kpis, rot)
            k.pack(side="left", fill="x", expand=True, padx=(0, 10))
            self.kpis[chave] = k

        mapas = ttk.Frame(self.corpo)
        mapas.pack(fill="x")
        mapas.columnconfigure(0, weight=1)
        mapas.columnconfigure(1, weight=1)
        c1 = Cartao(mapas)
        c1.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        self.mapa_ine = MapaCalor(c1, self.tema, self.m, "Risco inerente", height=360)
        self.mapa_ine.pack(fill="both", expand=True)
        c2 = Cartao(mapas)
        c2.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        self.mapa_res = MapaCalor(c2, self.tema, self.m, "Risco residual (após controles)", height=360)
        self.mapa_res.pack(fill="both", expand=True)

        c3 = Cartao(self.corpo, "Riscos por criticidade residual")
        c3.pack(fill="both", expand=True, pady=(14, 0))
        self.tv = tabela(c3, [
            ("cod", "Cód.", 55, "center"), ("proc", "Processo", 150, "w"), ("risco", "Risco", 280, "w"),
            ("p", "P", 40, "center"), ("i", "I", 40, "center"), ("ine", "Inerente", 110, "center"),
            ("ctrl", "Controles", 75, "center"), ("ef", "Efetiv.", 70, "center"),
            ("res", "Residual", 120, "center")], altura=7)
        self.tv.quadro.pack(fill="both", expand=True)
        self.tv.bind("<Double-1>", self._abrir_risco)

    def atualizar(self):
        self.colorir_niveis(self.tv)
        if not self.app.aval_id:
            self.corpo.pack_forget()
            self.vazio.pack(anchor="w", pady=30)
            self._lbl_titulo.configure(text="Matriz de riscos")
            self._lbl_sub.configure(text="")
            return
        self.vazio.pack_forget()
        self.corpo.pack(fill="both", expand=True)
        with db.conectar() as con:
            aval = db.obter_avaliacao(con, self.app.aval_id)
            itens = servico.avaliar_avaliacao(con, self.app.aval_id, self.m)
        rs = servico.resumo(itens, self.m)
        self._lbl_titulo.configure(text=f"Matriz de riscos · {aval['area']}")
        self._lbl_sub.configure(text=f"Período {aval['periodo']}   ·   Avaliador: {aval['avaliador']}   ·   "
                                     f"Status: {aval['status']}   ·   Método residual: {self.m.metodo_residual}")
        self.kpis["riscos"].definir(str(rs["qtd_riscos"]))
        self.kpis["controles"].definir(str(rs["qtd_controles"]))
        self.kpis["sem"].definir(str(rs["riscos_sem_controle"]))
        self.kpis["ef"].definir(f"{rs['efetividade_media']:.0%}")
        self.kpis["ine"].definir(f"{rs['inerente_medio']:.1f}")
        self.kpis["res"].definir(f"{rs['residual_medio']:.1f}")
        self.mapa_ine.definir([(it.risco["codigo"], it.resultado.posicao_inerente) for it in itens])
        self.mapa_res.definir([(it.risco["codigo"], it.resultado.posicao_residual) for it in itens])
        self.tv.delete(*self.tv.get_children())
        for it in sorted(itens, key=lambda x: (-x.resultado.residual, -x.resultado.inerente)):
            r = it.resultado
            self.tv.insert("", "end", iid=str(it.risco["id"]), tags=(f"nivel_{r.nivel_residual}",), values=(
                it.risco["codigo"], _cortar(it.risco["processo"], 26), _cortar(it.risco["descricao"], 60),
                r.probabilidade, r.impacto, f"{r.inerente} · {r.nivel_inerente}", len(it.controles),
                f"{r.efetividade_combinada:.0%}", f"{r.residual:.1f} · {r.nivel_residual}"))

    def _abrir_risco(self, _e=None):
        sel = self.tv.selection()
        if sel:
            pag = self.app.paginas["avaliacao"]
            pag.risco_id, pag._foto = int(sel[0]), None
            self.app.mostrar("avaliacao")
            pag._recarregar_form()


# =============================================================================
# 4. METODOLOGIA
# =============================================================================
class PaginaMetodologia(Pagina):
    titulo = "Metodologia"

    def __init__(self, master, app):
        super().__init__(master, app)
        acoes = self.cabecalho("Metodologia", "")
        ttk.Button(acoes, text="Recarregar", style="Accent.TButton",
                   command=self.app.recarregar_metodologia).pack(side="right")
        ttk.Button(acoes, text="Abrir arquivo YAML", command=self.app.abrir_yaml).pack(side="right", padx=8)
        self.rolagem = RolagemFrame(self, self.tema)
        self.rolagem.pack(fill="both", expand=True)

    def atualizar_tema(self):
        self.rolagem.atualizar_tema()
        self.atualizar()

    def atualizar(self):
        m = self.m
        self._lbl_sub.configure(text=f"Versão {m.versao} · edite config/metodologia.yaml e clique em Recarregar.")
        for w in self.rolagem.interno.winfo_children():
            w.destroy()
        area = self.rolagem.interno

        c = Cartao(area, "Fórmulas")
        c.pack(fill="x", padx=(0, 6), pady=(0, 12))
        for t in (
            "Risco inerente = Probabilidade × Impacto  (1 a 25)",
            "Efetividade do controle = fator do desenho × fator da operação × peso do tipo",
            f"Efetividade combinada = 1 − Π(1 − efetividade de cada controle), limitada a {m.efetividade_maxima:.0%}",
            "P residual = 1 + (P − 1) × (1 − efetividade)   ·   I residual = 1 + (I − 1) × (1 − efetividade)",
            "Risco residual = P residual × I residual",
            f"Método em uso: {m.metodo_residual} — " + (
                "a efetividade combinada reduz P e I" if m.metodo_residual == "proporcional"
                else "preventivos reduzem P e detectivos reduzem I"),
        ):
            ttk.Label(c, text="•  " + t, style="Card.TLabel").pack(anchor="w", pady=1)

        grade = ttk.Frame(area)
        grade.pack(fill="x", padx=(0, 6))
        grade.columnconfigure(0, weight=1)
        grade.columnconfigure(1, weight=1)

        def escala(titulo, niveis, r, col, fator=False):
            cc = Cartao(grade, titulo)
            cc.grid(row=r, column=0, columnspan=2, sticky="nsew", pady=6)
            cols = [("n", "Nota", 50, "center"), ("r", "Rótulo", 190, "w"), ("d", "Descrição", 600, "w")]
            if fator:
                cols.append(("f", "Fator", 60, "center"))
            tv = tabela(cc, cols, altura=5)
            tv.quadro.pack(fill="x")
            for n in niveis.values():
                vals = [n.valor, n.rotulo, n.descricao] + ([f"{n.fator:.2f}"] if fator else [])
                tv.insert("", "end", values=vals)

        escala("Probabilidade", m.probabilidade, 0, 0)
        escala("Impacto", m.impacto, 1, 0)
        escala("Desenho do controle", m.desenho, 2, 0, fator=True)
        escala("Operação do controle", m.operacao, 3, 0, fator=True)

        cc = Cartao(grade, "Tipos de controle")
        cc.grid(row=4, column=0, sticky="nsew", padx=(0, 6), pady=6)
        tv = tabela(cc, [("c", "Código", 60, "center"), ("r", "Tipo", 200, "w"),
                         ("n", "Natureza", 110, "center"), ("p", "Peso", 60, "center")], altura=4)
        tv.quadro.pack(fill="x")
        for t in m.tipos_controle.values():
            tv.insert("", "end", values=(t.codigo, t.rotulo, t.natureza, f"{t.peso:.2f}"))

        cc = Cartao(grade, "Faixas de risco e classificação de controles")
        cc.grid(row=4, column=1, sticky="nsew", padx=(6, 0), pady=6)
        for f in sorted(m.faixas_risco, key=lambda x: -x.minimo):
            fr = ttk.Frame(cc, style="Plano.TFrame")
            fr.pack(fill="x", pady=2)
            s = Selo(fr, self.tema, width=10)
            s.definir(f.rotulo, f.cor)
            s.pack(side="left")
            ttk.Label(fr, text=f"  pontuação de {f.minimo:.0f} a {f.maximo:.0f}", style="Card.TLabel").pack(side="left")
        ttk.Separator(cc).pack(fill="x", pady=8)
        for f in sorted(m.classificacao_controle, key=lambda x: -x.minimo):
            fr = ttk.Frame(cc, style="Plano.TFrame")
            fr.pack(fill="x", pady=2)
            s = Selo(fr, self.tema, width=18)
            s.definir(f.rotulo, f.cor)
            s.pack(side="left")
            ttk.Label(fr, text=f"  efetividade ≥ {f.minimo:.0%}", style="Card.TLabel").pack(side="left")
