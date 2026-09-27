"""Carregamento e validação da metodologia (config/metodologia.yaml)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
CAMINHO_PADRAO = RAIZ / "config" / "metodologia.yaml"


@dataclass(frozen=True)
class Nivel:
    valor: int
    rotulo: str
    descricao: str
    fator: float | None = None

    @property
    def texto(self) -> str:
        return f"{self.valor} · {self.rotulo}"


@dataclass(frozen=True)
class TipoControle:
    codigo: str
    rotulo: str
    natureza: str  # preventivo | detectivo
    peso: float


@dataclass(frozen=True)
class Faixa:
    minimo: float
    rotulo: str
    cor: str
    maximo: float | None = None


@dataclass(frozen=True)
class Metodologia:
    versao: str
    descricao: str
    probabilidade: dict[int, Nivel]
    impacto: dict[int, Nivel]
    desenho: dict[int, Nivel]
    operacao: dict[int, Nivel]
    tipos_controle: dict[str, TipoControle]
    metodo_residual: str
    efetividade_maxima: float
    classificacao_controle: list[Faixa]
    faixas_risco: list[Faixa]
    areas: list[str] = field(default_factory=list)
    categorias_risco: list[str] = field(default_factory=list)
    frequencias_controle: list[str] = field(default_factory=list)
    sugestao_operacao: list[tuple[float, int]] = field(default_factory=list)

    # --- consultas -----------------------------------------------------------
    def sugerir_operacao(self, amostra: int | None, falhas: int | None) -> int | None:
        """Sugere a nota de operação (1..5) a partir do resultado do teste."""
        if not amostra or amostra <= 0 or falhas is None or falhas < 0:
            return None
        taxa = min(falhas / amostra, 1.0)
        for limite, nota in sorted(self.sugestao_operacao):
            if taxa <= limite + 1e-12:
                return nota
        return 1

    def faixa_risco(self, pontuacao: float) -> Faixa:
        """Retorna a faixa do risco. Pontuação fracionária é arredondada
        meio-para-cima (mesmo comportamento do ARRED/ROUND do Excel)."""
        p = int(pontuacao + 0.5)
        for f in self.faixas_risco:
            if f.minimo <= p <= (f.maximo if f.maximo is not None else 25):
                return f
        return self.faixas_risco[-1] if p > 25 else self.faixas_risco[0]

    def classificacao(self, efetividade: float) -> Faixa:
        for f in sorted(self.classificacao_controle, key=lambda x: -x.minimo):
            if efetividade >= f.minimo - 1e-9:
                return f
        return self.classificacao_controle[-1]


class ErroMetodologia(ValueError):
    pass


def _niveis(bruto: dict, nome: str, exige_fator: bool = False) -> dict[int, Nivel]:
    niveis = {}
    for k, v in bruto.items():
        k = int(k)
        if exige_fator and "fator" not in v:
            raise ErroMetodologia(f"'{nome}' nível {k}: campo 'fator' obrigatório")
        fator = float(v["fator"]) if "fator" in v else None
        if fator is not None and not 0 <= fator <= 1:
            raise ErroMetodologia(f"'{nome}' nível {k}: fator deve estar entre 0 e 1")
        niveis[k] = Nivel(k, str(v["rotulo"]), str(v.get("descricao", "")), fator)
    if sorted(niveis) != [1, 2, 3, 4, 5]:
        raise ErroMetodologia(f"'{nome}' deve ter exatamente os níveis 1 a 5")
    return niveis


def carregar(caminho: Path | str = CAMINHO_PADRAO) -> Metodologia:
    with open(caminho, encoding="utf-8") as f:
        d = yaml.safe_load(f)

    tipos = {}
    for cod, v in d["tipos_controle"].items():
        if v["natureza"] not in ("preventivo", "detectivo"):
            raise ErroMetodologia(f"tipo {cod}: natureza deve ser preventivo ou detectivo")
        tipos[str(cod)] = TipoControle(str(cod), v["rotulo"], v["natureza"], float(v["peso"]))

    metodo = d.get("metodo_residual", "proporcional")
    if metodo not in ("proporcional", "natureza"):
        raise ErroMetodologia("metodo_residual deve ser 'proporcional' ou 'natureza'")

    faixas = [Faixa(float(f["minimo"]), f["rotulo"], f["cor"], float(f["maximo"]))
              for f in d["faixas_risco"]]
    faixas.sort(key=lambda f: f.minimo)

    return Metodologia(
        versao=str(d.get("versao", "")),
        descricao=str(d.get("descricao", "")).strip(),
        probabilidade=_niveis(d["probabilidade"], "probabilidade"),
        impacto=_niveis(d["impacto"], "impacto"),
        desenho=_niveis(d["desenho"], "desenho", exige_fator=True),
        operacao=_niveis(d["operacao"], "operacao", exige_fator=True),
        tipos_controle=tipos,
        metodo_residual=metodo,
        efetividade_maxima=float(d.get("efetividade_maxima", 0.95)),
        classificacao_controle=[Faixa(float(f["minimo"]), f["rotulo"], f["cor"])
                                for f in d["classificacao_controle"]],
        faixas_risco=faixas,
        areas=list(d.get("areas", [])),
        categorias_risco=list(d.get("categorias_risco", [])),
        frequencias_controle=list(d.get("frequencias_controle", [])),
        sugestao_operacao=[(float(r["taxa_falha_max"]), int(r["nota"]))
                           for r in d.get("sugestao_operacao", [])],
    )
