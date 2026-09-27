"""Janela de cadastro/edição de controle."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..calculo import EntradaControle, avaliar_controle
from ..config import Metodologia
from .tema import Tema
from .widgets import (RolagemFrame, Selo, SeletorEscala, campo_texto, escrever_texto,
                      estilizar_texto, ler_texto)


class DialogoControle(tk.Toplevel):
    """Formulário modal. Após salvar, self.resultado contém o dicionário do controle."""

    def __init__(self, master, tema: Tema, m: Metodologia, risco: dict,
                 controle: dict | None = None):
        super().__init__(master)
        self.tema, self.m, self.resultado = tema, m, None
        edicao = controle is not None
        self.title(("Editar controle " + controle["codigo"]) if edicao else "Novo controle")
        self.transient(master.winfo_toplevel())
        altura = min(820, self.winfo_screenheight() - 80)
        self.geometry(f"920x{altura}")
        self.minsize(820, 560)
        self.configure(bg=tema.fundo)

        # rodapé fixo (prévia + botões) e corpo com rolagem
        fixo = ttk.Frame(self, padding=(20, 10, 20, 14))
        fixo.pack(side="bottom", fill="x")
        ttk.Separator(self).pack(side="bottom", fill="x")
        self._rolagem = RolagemFrame(self, tema)
        self._rolagem.pack(fill="both", expand=True)
        corpo = ttk.Frame(self._rolagem.interno, padding=20)
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(0, weight=1)
        corpo.columnconfigure(1, weight=1)

        ttk.Label(corpo, text="Editar controle" if edicao else "Novo controle",
                  style="Titulo.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(corpo, text=f"Risco {risco['codigo']} · {risco['descricao']}",
                  style="Suave.TLabel", wraplength=840).grid(row=1, column=0, columnspan=2,
                                                             sticky="w", pady=(0, 12))

        # descrição
        ttk.Label(corpo, text="Descrição do controle *", style="Negrito.TLabel").grid(
            row=2, column=0, columnspan=2, sticky="w")
        self.txt_desc = campo_texto(corpo, 3)
        estilizar_texto(self.txt_desc, tema)
        self.txt_desc.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(2, 10))

        # tipo e frequência
        self.tipos = {f"{t.codigo} · {t.rotulo}": t.codigo for t in m.tipos_controle.values()}
        ttk.Label(corpo, text="Tipo de controle *", style="Negrito.TLabel").grid(row=4, column=0, sticky="w")
        ttk.Label(corpo, text="Frequência", style="Negrito.TLabel").grid(row=4, column=1, sticky="w", padx=(12, 0))
        self.cb_tipo = ttk.Combobox(corpo, values=list(self.tipos), state="readonly")
        self.cb_tipo.grid(row=5, column=0, sticky="ew", pady=(2, 10))
        self.cb_freq = ttk.Combobox(corpo, values=m.frequencias_controle, state="readonly")
        self.cb_freq.grid(row=5, column=1, sticky="ew", padx=(12, 0), pady=(2, 10))
        self.cb_tipo.bind("<<ComboboxSelected>>", lambda e: self._atualizar())

        # responsável e evidência
        ttk.Label(corpo, text="Responsável (dono do controle)", style="Negrito.TLabel").grid(row=6, column=0, sticky="w")
        ttk.Label(corpo, text="Evidência de execução", style="Negrito.TLabel").grid(row=6, column=1, sticky="w", padx=(12, 0))
        self.ent_resp = ttk.Entry(corpo)
        self.ent_resp.grid(row=7, column=0, sticky="ew", pady=(2, 10))
        self.ent_evid = ttk.Entry(corpo)
        self.ent_evid.grid(row=7, column=1, sticky="ew", padx=(12, 0), pady=(2, 10))

        ttk.Separator(corpo).grid(row=8, column=0, columnspan=2, sticky="ew", pady=8)

        # resultado do teste (opcional)
        teste = ttk.Frame(corpo)
        teste.grid(row=9, column=0, columnspan=2, sticky="ew")
        ttk.Label(teste, text="Resultado do teste (opcional)", style="Negrito.TLabel").pack(side="left")
        ttk.Label(teste, text="   Amostra").pack(side="left")
        self.var_amostra = tk.StringVar()
        self.var_falhas = tk.StringVar()
        ttk.Spinbox(teste, from_=0, to=100000, width=7, textvariable=self.var_amostra,
                    command=self._sugerir).pack(side="left", padx=4)
        ttk.Label(teste, text="Falhas").pack(side="left", padx=(8, 0))
        ttk.Spinbox(teste, from_=0, to=100000, width=7, textvariable=self.var_falhas,
                    command=self._sugerir).pack(side="left", padx=4)
        sug = ttk.Frame(corpo)
        sug.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.lbl_sugestao = ttk.Label(sug, text="Informe amostra e falhas para receber a sugestão "
                                               "da nota de operação.", style="Suave.TLabel")
        self.lbl_sugestao.pack(side="left")
        self.btn_aplicar = ttk.Button(sug, text="Aplicar sugestão", command=self._aplicar_sugestao,
                                      state="disabled")
        self.btn_aplicar.pack(side="right")
        self.var_amostra.trace_add("write", lambda *a: self._sugerir())
        self.var_falhas.trace_add("write", lambda *a: self._sugerir())
        self._sugestao = None

        # notas
        self.sel_desenho = SeletorEscala(corpo, "Avaliação do DESENHO *", m.desenho,
                                         ao_mudar=lambda v: self._atualizar())
        self.sel_desenho.grid(row=11, column=0, sticky="new", pady=(12, 8), padx=(0, 10))
        self.sel_operacao = SeletorEscala(corpo, "Avaliação da OPERAÇÃO (efetividade) *", m.operacao,
                                          ao_mudar=lambda v: self._atualizar())
        self.sel_operacao.grid(row=11, column=1, sticky="new", pady=(12, 8), padx=(10, 0))

        ttk.Label(corpo, text="Observação", style="Negrito.TLabel").grid(row=12, column=0, sticky="w")
        self.txt_obs = campo_texto(corpo, 2)
        estilizar_texto(self.txt_obs, tema)
        self.txt_obs.grid(row=13, column=0, columnspan=2, sticky="ew", pady=(2, 4))

        # prévia + botões
        rodape = ttk.Frame(fixo)
        rodape.pack(fill="x")
        ttk.Label(rodape, text="Efetividade calculada:", style="Negrito.TLabel").pack(side="left")
        self.lbl_ef = ttk.Label(rodape, text="—", style="Subtitulo.TLabel")
        self.lbl_ef.pack(side="left", padx=8)
        self.selo = Selo(rodape, tema)
        self.selo.pack(side="left")
        ttk.Button(rodape, text="Salvar controle", style="Accent.TButton",
                   command=self._salvar).pack(side="right")
        ttk.Button(rodape, text="Cancelar", command=self.destroy).pack(side="right", padx=8)
        self.lbl_formula = ttk.Label(fixo, text="", style="Suave.TLabel")
        self.lbl_formula.pack(anchor="w", pady=(6, 0))

        if edicao:
            escrever_texto(self.txt_desc, controle["descricao"])
            for k, v in self.tipos.items():
                if v == controle["tipo"]:
                    self.cb_tipo.set(k)
            self.cb_freq.set(controle.get("frequencia") or "")
            self.ent_resp.insert(0, controle.get("responsavel") or "")
            self.ent_evid.insert(0, controle.get("evidencia") or "")
            self.var_amostra.set("" if controle.get("amostra") is None else str(controle["amostra"]))
            self.var_falhas.set("" if controle.get("falhas") is None else str(controle["falhas"]))
            self.sel_desenho.set(controle["desenho"])
            self.sel_operacao.set(controle["operacao"])
            escrever_texto(self.txt_obs, controle.get("observacao"))
        self._atualizar()

        self.bind("<Escape>", lambda e: self.destroy())
        self.after(50, self._modal)

    def _modal(self):
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.txt_desc.focus_set()

    # --- lógica ---------------------------------------------------------------
    def _int(self, var: tk.StringVar) -> int | None:
        s = var.get().strip()
        return int(s) if s.isdigit() else None

    def _sugerir(self):
        am, fa = self._int(self.var_amostra), self._int(self.var_falhas)
        if am is not None and fa is not None and fa > am:
            self.lbl_sugestao.configure(text="Falhas maiores que a amostra")
            self._sugestao = None
        else:
            self._sugestao = self.m.sugerir_operacao(am, fa)
            if self._sugestao:
                taxa = fa / am
                n = self.m.operacao[self._sugestao]
                self.lbl_sugestao.configure(text=f"{taxa:.1%} de falha → sugere nota {self._sugestao} ({n.rotulo})")
            else:
                self.lbl_sugestao.configure(text="Informe amostra e falhas para receber a sugestão "
                                                 "da nota de operação.")
        self.btn_aplicar.configure(state="normal" if self._sugestao else "disabled")

    def _aplicar_sugestao(self):
        if self._sugestao:
            self.sel_operacao.set(self._sugestao)
            self._atualizar()

    def _atualizar(self):
        tipo = self.tipos.get(self.cb_tipo.get())
        d, o = self.sel_desenho.get(), self.sel_operacao.get()
        if tipo and d and o:
            r = avaliar_controle(EntradaControle(tipo, d, o), self.m)
            self.lbl_ef.configure(text=f"{r.efetividade:.0%}")
            self.selo.definir(r.classificacao, r.cor)
            self.lbl_formula.configure(
                text=f"Desenho {r.fator_desenho:.2f} × Operação {r.fator_operacao:.2f} × "
                     f"Peso do tipo {r.peso_tipo:.2f} = {r.efetividade:.3f}   ·   "
                     f"natureza: {r.natureza}")
        else:
            self.lbl_ef.configure(text="—")
            self.selo.definir("preencha tipo e notas", None)
            self.lbl_formula.configure(text="")

    def _salvar(self):
        desc = ler_texto(self.txt_desc)
        tipo = self.tipos.get(self.cb_tipo.get())
        faltando = [n for n, ok in (("descrição", desc), ("tipo", tipo),
                                    ("nota de desenho", self.sel_desenho.get()),
                                    ("nota de operação", self.sel_operacao.get())) if not ok]
        if faltando:
            messagebox.showwarning("Campos obrigatórios", "Preencha: " + ", ".join(faltando), parent=self)
            return
        am, fa = self._int(self.var_amostra), self._int(self.var_falhas)
        if am is not None and fa is not None and fa > am:
            messagebox.showwarning("Teste inválido", "O número de falhas não pode ser maior que a amostra.",
                                   parent=self)
            return
        self.resultado = dict(
            descricao=desc, tipo=tipo, frequencia=self.cb_freq.get() or None,
            responsavel=self.ent_resp.get().strip() or None,
            evidencia=self.ent_evid.get().strip() or None,
            desenho=self.sel_desenho.get(), operacao=self.sel_operacao.get(),
            amostra=am, falhas=fa, observacao=ler_texto(self.txt_obs) or None)
        self.destroy()
