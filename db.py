"""Persistência local em SQLite (data/avaliacoes.db).

Hierarquia: avaliação (área + período) → riscos → controles.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .config import RAIZ

CAMINHO_DB = Path(os.environ.get("RISCOS_DB", RAIZ / "data" / "avaliacoes.db"))

ESQUEMA = """
CREATE TABLE IF NOT EXISTS avaliacao (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    area                TEXT NOT NULL,
    periodo             TEXT NOT NULL,
    avaliador           TEXT NOT NULL,
    descricao           TEXT,
    status              TEXT NOT NULL DEFAULT 'Em andamento',
    versao_metodologia  TEXT,
    criada_em           TEXT NOT NULL,
    atualizada_em       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS risco (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    avaliacao_id    INTEGER NOT NULL REFERENCES avaliacao(id) ON DELETE CASCADE,
    codigo          TEXT NOT NULL,
    processo        TEXT NOT NULL,
    descricao       TEXT NOT NULL,
    causa           TEXT,
    consequencia    TEXT,
    categoria       TEXT,
    responsavel     TEXT,
    probabilidade   INTEGER NOT NULL CHECK (probabilidade BETWEEN 1 AND 5),
    impacto         INTEGER NOT NULL CHECK (impacto BETWEEN 1 AND 5),
    justificativa   TEXT,
    criado_em       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS controle (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    risco_id        INTEGER NOT NULL REFERENCES risco(id) ON DELETE CASCADE,
    codigo          TEXT NOT NULL,
    descricao       TEXT NOT NULL,
    tipo            TEXT NOT NULL,
    frequencia      TEXT,
    responsavel     TEXT,
    evidencia       TEXT,
    desenho         INTEGER NOT NULL CHECK (desenho BETWEEN 1 AND 5),
    operacao        INTEGER NOT NULL CHECK (operacao BETWEEN 1 AND 5),
    amostra         INTEGER,
    falhas          INTEGER,
    observacao      TEXT,
    criado_em       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_risco_aval ON risco(avaliacao_id);
CREATE INDEX IF NOT EXISTS ix_controle_risco ON controle(risco_id);
"""


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def conectar(caminho: Path | str | None = None):
    caminho = Path(caminho or CAMINHO_DB)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(caminho)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        con.executescript(ESQUEMA)
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def _dicts(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def _tocar(con, avaliacao_id: int) -> None:
    con.execute("UPDATE avaliacao SET atualizada_em=? WHERE id=?", (_agora(), avaliacao_id))


# --- avaliações --------------------------------------------------------------
def criar_avaliacao(con, area, periodo, avaliador, descricao="", versao="") -> int:
    agora = _agora()
    cur = con.execute(
        "INSERT INTO avaliacao (area, periodo, avaliador, descricao, versao_metodologia,"
        " criada_em, atualizada_em) VALUES (?,?,?,?,?,?,?)",
        (area, periodo, avaliador, descricao, versao, agora, agora))
    return cur.lastrowid


def listar_avaliacoes(con) -> list[dict]:
    return _dicts(con.execute("""
        SELECT a.*,
               (SELECT COUNT(*) FROM risco r WHERE r.avaliacao_id = a.id) AS qtd_riscos,
               (SELECT COUNT(*) FROM controle c JOIN risco r ON r.id = c.risco_id
                 WHERE r.avaliacao_id = a.id) AS qtd_controles
        FROM avaliacao a ORDER BY a.atualizada_em DESC"""))


def obter_avaliacao(con, avaliacao_id: int) -> dict | None:
    r = con.execute("SELECT * FROM avaliacao WHERE id=?", (avaliacao_id,)).fetchone()
    return dict(r) if r else None


def atualizar_status(con, avaliacao_id: int, status: str) -> None:
    con.execute("UPDATE avaliacao SET status=? WHERE id=?", (status, avaliacao_id))
    _tocar(con, avaliacao_id)


def excluir_avaliacao(con, avaliacao_id: int) -> None:
    con.execute("DELETE FROM avaliacao WHERE id=?", (avaliacao_id,))


# --- riscos ------------------------------------------------------------------
CAMPOS_RISCO = ("processo", "descricao", "causa", "consequencia", "categoria",
                "responsavel", "probabilidade", "impacto", "justificativa")


def _proximo_codigo_risco(con, avaliacao_id: int) -> str:
    n = con.execute("SELECT COUNT(*) FROM risco WHERE avaliacao_id=?",
                    (avaliacao_id,)).fetchone()[0]
    existentes = {r[0] for r in con.execute(
        "SELECT codigo FROM risco WHERE avaliacao_id=?", (avaliacao_id,))}
    while f"R{n + 1:02d}" in existentes:
        n += 1
    return f"R{n + 1:02d}"


def criar_risco(con, avaliacao_id: int, **dados) -> int:
    valores = {k: dados.get(k) for k in CAMPOS_RISCO}
    cur = con.execute(
        f"INSERT INTO risco (avaliacao_id, codigo, {', '.join(CAMPOS_RISCO)}, criado_em)"
        f" VALUES (?, ?, {', '.join('?' * len(CAMPOS_RISCO))}, ?)",
        (avaliacao_id, _proximo_codigo_risco(con, avaliacao_id),
         *valores.values(), _agora()))
    _tocar(con, avaliacao_id)
    return cur.lastrowid


def atualizar_risco(con, risco_id: int, **dados) -> None:
    campos = [k for k in CAMPOS_RISCO if k in dados]
    con.execute(f"UPDATE risco SET {', '.join(f'{k}=?' for k in campos)} WHERE id=?",
                (*[dados[k] for k in campos], risco_id))
    av = con.execute("SELECT avaliacao_id FROM risco WHERE id=?", (risco_id,)).fetchone()
    if av:
        _tocar(con, av[0])


def excluir_risco(con, risco_id: int) -> None:
    con.execute("DELETE FROM risco WHERE id=?", (risco_id,))


def listar_riscos(con, avaliacao_id: int) -> list[dict]:
    return _dicts(con.execute(
        "SELECT * FROM risco WHERE avaliacao_id=? ORDER BY codigo", (avaliacao_id,)))


# --- controles ---------------------------------------------------------------
CAMPOS_CONTROLE = ("descricao", "tipo", "frequencia", "responsavel", "evidencia",
                   "desenho", "operacao", "amostra", "falhas", "observacao")


def criar_controle(con, risco_id: int, **dados) -> int:
    r = con.execute("SELECT codigo, avaliacao_id FROM risco WHERE id=?", (risco_id,)).fetchone()
    existentes = {x[0] for x in con.execute(
        "SELECT codigo FROM controle WHERE risco_id=?", (risco_id,))}
    n = len(existentes) + 1
    while f"{r['codigo']}-C{n:02d}" in existentes:
        n += 1
    valores = {k: dados.get(k) for k in CAMPOS_CONTROLE}
    cur = con.execute(
        f"INSERT INTO controle (risco_id, codigo, {', '.join(CAMPOS_CONTROLE)}, criado_em)"
        f" VALUES (?, ?, {', '.join('?' * len(CAMPOS_CONTROLE))}, ?)",
        (risco_id, f"{r['codigo']}-C{n:02d}", *valores.values(), _agora()))
    _tocar(con, r["avaliacao_id"])
    return cur.lastrowid


def atualizar_controle(con, controle_id: int, **dados) -> None:
    campos = [k for k in CAMPOS_CONTROLE if k in dados]
    con.execute(f"UPDATE controle SET {', '.join(f'{k}=?' for k in campos)} WHERE id=?",
                (*[dados[k] for k in campos], controle_id))


def excluir_controle(con, controle_id: int) -> None:
    con.execute("DELETE FROM controle WHERE id=?", (controle_id,))


def listar_controles(con, risco_id: int) -> list[dict]:
    return _dicts(con.execute(
        "SELECT * FROM controle WHERE risco_id=? ORDER BY codigo", (risco_id,)))


def listar_controles_avaliacao(con, avaliacao_id: int) -> list[dict]:
    return _dicts(con.execute("""
        SELECT c.*, r.codigo AS risco_codigo FROM controle c
        JOIN risco r ON r.id = c.risco_id
        WHERE r.avaliacao_id=? ORDER BY c.codigo""", (avaliacao_id,)))
