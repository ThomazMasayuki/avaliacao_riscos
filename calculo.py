"""Motor de cálculo de risco inerente, efetividade de controles e risco residual.

Funções puras: recebem números e a metodologia, devolvem resultados.
As mesmas regras são reproduzidas em fórmulas no Excel exportado (excel.py),
então qualquer alteração aqui deve ser espelhada lá.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import prod

from .config import Metodologia


def arred(x: float) -> int:
    """Arredondamento meio-para-cima (igual ao ROUND do Excel para positivos)."""
    return int(x + 0.5)


@dataclass(frozen=True)
class EntradaControle:
    tipo: str        # código em metodologia.tipos_controle (PA, PM, DA, DM)
    desenho: int     # 1..5
    operacao: int    # 1..5


@dataclass(frozen=True)
class ResultadoControle:
    fator_desenho: float
    fator_operacao: float
    peso_tipo: float
    natureza: str
    efetividade: float
    classificacao: str
    cor: str


@dataclass(frozen=True)
class ResultadoRisco:
    probabilidade: int
    impacto: int
    inerente: int
    nivel_inerente: str
    cor_inerente: str
    efetividade_combinada: float
    efetividade_preventiva: float
    efetividade_detectiva: float
    prob_residual: float
    impacto_residual: float
    residual: float
    nivel_residual: str
    cor_residual: str
    reducao: float               # % de redução do inerente para o residual
    controles: tuple[ResultadoControle, ...]

    @property
    def posicao_inerente(self) -> tuple[int, int]:
        return self.probabilidade, self.impacto

    @property
    def posicao_residual(self) -> tuple[int, int]:
        return max(1, arred(self.prob_residual)), max(1, arred(self.impacto_residual))


def _validar_escala(valor: int, nome: str) -> int:
    v = int(valor)
    if not 1 <= v <= 5:
        raise ValueError(f"{nome} deve estar entre 1 e 5 (recebido {valor})")
    return v


def avaliar_controle(c: EntradaControle, m: Metodologia) -> ResultadoControle:
    if c.tipo not in m.tipos_controle:
        raise ValueError(f"Tipo de controle desconhecido: {c.tipo}")
    tipo = m.tipos_controle[c.tipo]
    fd = m.desenho[_validar_escala(c.desenho, "desenho")].fator
    fo = m.operacao[_validar_escala(c.operacao, "operação")].fator
    ef = fd * fo * tipo.peso
    cls = m.classificacao(ef)
    return ResultadoControle(fd, fo, tipo.peso, tipo.natureza, ef, cls.rotulo, cls.cor)


def combinar(efetividades: list[float], teto: float) -> float:
    """Controles independentes: 1 - Π(1 - e). Limitado ao teto da metodologia."""
    if not efetividades:
        return 0.0
    return min(teto, 1 - prod(1 - e for e in efetividades))


def _reduzir(nivel: int, efetividade: float) -> float:
    """Reduz um eixo (1..5) em direção a 1, proporcionalmente à efetividade."""
    return 1 + (nivel - 1) * (1 - efetividade)


def avaliar_risco(probabilidade: int, impacto: int,
                  controles: list[EntradaControle], m: Metodologia) -> ResultadoRisco:
    p = _validar_escala(probabilidade, "probabilidade")
    i = _validar_escala(impacto, "impacto")
    rcs = tuple(avaliar_controle(c, m) for c in controles)

    teto = m.efetividade_maxima
    ef_total = combinar([r.efetividade for r in rcs], teto)
    ef_prev = combinar([r.efetividade for r in rcs if r.natureza == "preventivo"], teto)
    ef_det = combinar([r.efetividade for r in rcs if r.natureza == "detectivo"], teto)

    if m.metodo_residual == "natureza":
        p_res, i_res = _reduzir(p, ef_prev), _reduzir(i, ef_det)
    else:  # proporcional
        p_res, i_res = _reduzir(p, ef_total), _reduzir(i, ef_total)

    inerente = p * i
    residual = p_res * i_res
    fi, fr = m.faixa_risco(inerente), m.faixa_risco(residual)

    return ResultadoRisco(
        probabilidade=p, impacto=i, inerente=inerente,
        nivel_inerente=fi.rotulo, cor_inerente=fi.cor,
        efetividade_combinada=ef_total,
        efetividade_preventiva=ef_prev, efetividade_detectiva=ef_det,
        prob_residual=p_res, impacto_residual=i_res, residual=residual,
        nivel_residual=fr.rotulo, cor_residual=fr.cor,
        reducao=1 - residual / inerente,
        controles=rcs,
    )
