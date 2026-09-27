"""Camada de serviço: junta dados do banco com o motor de cálculo."""
from __future__ import annotations

from dataclasses import dataclass

from . import db
from .calculo import EntradaControle, ResultadoRisco, avaliar_risco
from .config import Metodologia


@dataclass
class RiscoAvaliado:
    risco: dict
    controles: list[dict]
    resultado: ResultadoRisco


def avaliar_avaliacao(con, avaliacao_id: int, m: Metodologia) -> list[RiscoAvaliado]:
    """Calcula todos os riscos de uma avaliação, com seus controles."""
    saida = []
    for r in db.listar_riscos(con, avaliacao_id):
        ctrls = db.listar_controles(con, r["id"])
        res = avaliar_risco(
            r["probabilidade"], r["impacto"],
            [EntradaControle(c["tipo"], c["desenho"], c["operacao"]) for c in ctrls], m)
        saida.append(RiscoAvaliado(r, ctrls, res))
    return saida


def resumo(itens: list[RiscoAvaliado], m: Metodologia) -> dict:
    niveis = [f.rotulo for f in m.faixas_risco]
    inerente = {n: 0 for n in niveis}
    residual = {n: 0 for n in niveis}
    for it in itens:
        inerente[it.resultado.nivel_inerente] += 1
        residual[it.resultado.nivel_residual] += 1
    n_ctrl = sum(len(it.controles) for it in itens)
    ef_media = (sum(rc.efetividade for it in itens for rc in it.resultado.controles) / n_ctrl
                if n_ctrl else 0.0)
    return {
        "qtd_riscos": len(itens),
        "qtd_controles": n_ctrl,
        "riscos_sem_controle": sum(1 for it in itens if not it.controles),
        "efetividade_media": ef_media,
        "inerente_medio": sum(it.resultado.inerente for it in itens) / len(itens) if itens else 0,
        "residual_medio": sum(it.resultado.residual for it in itens) / len(itens) if itens else 0,
        "por_nivel_inerente": inerente,
        "por_nivel_residual": residual,
    }
