"""Regras de trabalho: fila de processos, minutas e pauta. Toda consulta filtra pelo usuário."""
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .modelos import Audiencia, Minuta, Processo, Usuario
from .nucleo import documento
from .nucleo.tabela import dv_ok
from .portas import ConexaoPlanilha, DadosProcesso, Motor

CNJ = re.compile(r"(?<!\d)\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}(?!\d)")
GRUPOS = ("Réu preso", "Vista urgente", "Intimação", "Outros")
MAX_COLAGEM = 200
TIPOS_AUDIENCIA = ("Instrução e julgamento", "Custódia", "Preliminar", "Justificação", "Plenário do júri", "Outra")


def grupo_de(reu_preso: bool, vista: str) -> int:
    """Prioridade da fila (decisão do titular): réu preso, vista urgente, intimação, demais."""
    v = (vista or "").strip().lower()
    return 0 if reu_preso else 1 if v == "urgente" else 2 if v == "intimação" else 3


@dataclass
class ResultadoImportacao:
    novos: int = 0
    atualizados: int = 0
    conferir: list[str] = field(default_factory=list)


def _criar_minuta(processo: Processo, motor: Motor) -> None:
    # objeto ainda não gravado: os valores padrão das colunas só existem depois do flush
    m = motor.elaborar_minuta(DadosProcesso(processo.numero, processo.classe or "", processo.assunto or "",
                                            processo.vista or "", bool(processo.reu_preso)))
    processo.minuta = Minuta(tipo=m["tipo"], blocos=documento.folha(m), motor=motor.nome)


def importar_fila(db: Session, usuario: Usuario, dados: bytes, nome: str | None, conexao: ConexaoPlanilha,
                  motor: Motor, ficticio: bool) -> ResultadoImportacao:
    """Lê a tabela do SIG e atualiza a fila do usuário. Processo novo já ganha a primeira minuta.
    Levanta `conexao.Recusada` com a orientação para o usuário."""
    fila = conexao.ler_fila(dados, nome)
    res = ResultadoImportacao()
    existentes = {p.numero: p for p in db.scalars(select(Processo).where(Processo.usuario_id == usuario.id))}
    for linha in fila["linhas"]:
        entrada = datetime.fromisoformat(linha["entrada_iso"]) if linha["entrada_iso"] else None
        campos = dict(numero_sig=linha["sig"][:30], classe=linha["classe"][:200], assunto=linha["assunto"][:200],
                      vista=linha["vista"][:40], reu_preso=linha["reu_preso"], entrada=entrada, dv_ok=linha["dv_ok"],
                      grupo=grupo_de(linha["reu_preso"], linha["vista"]))
        p = existentes.get(linha["judiciario"])
        if p is None:
            p = Processo(usuario_id=usuario.id, numero=linha["judiciario"][:25], origem="planilha", **campos)
            _criar_minuta(p, motor)
            db.add(p)
            res.novos += 1
        else:
            for k, v in campos.items():
                setattr(p, k, v)
            res.atualizados += 1
    for c in fila["conferir"]:
        # em ambiente de dados fictícios, todo número tem dígito verificador inválido de propósito
        if ficticio and "dígito verificador" in c["motivo"]:
            continue
        res.conferir.append(f"linha {c['linha']}: {c['motivo']}")
    db.commit()
    return res


def colar_numeros(db: Session, usuario: Usuario, texto: str, motor: Motor) -> ResultadoImportacao:
    """Aceita números de processo colados em qualquer formato de texto (um por linha, com vírgulas, de um e-mail)."""
    res = ResultadoImportacao()
    numeros = list(dict.fromkeys(CNJ.findall(texto or "")))[:MAX_COLAGEM]
    if not numeros:
        res.conferir.append("nenhum número de processo reconhecido no texto colado")
        return res
    ja = set(db.scalars(select(Processo.numero).where(Processo.usuario_id == usuario.id)))
    for n in numeros:
        if n in ja:
            res.atualizados += 1
            continue
        p = Processo(usuario_id=usuario.id, numero=n, origem="colagem", dv_ok=dv_ok(n), entrada=datetime.now())
        _criar_minuta(p, motor)
        db.add(p)
        res.novos += 1
    db.commit()
    return res


def fila(db: Session, usuario: Usuario, situacao: str = "a_fazer") -> list[Processo]:
    consulta = (select(Processo).where(Processo.usuario_id == usuario.id, Processo.situacao == situacao)
                .order_by(Processo.grupo, Processo.entrada.is_(None), Processo.entrada, Processo.numero))
    return list(db.scalars(consulta))


def processo_do_usuario(db: Session, usuario: Usuario, processo_id: int) -> Processo | None:
    return db.scalar(select(Processo).where(Processo.id == processo_id, Processo.usuario_id == usuario.id))


def salvar_minuta(db: Session, processo: Processo, blocos) -> Minuta:
    processo.minuta.blocos = documento.normalizar(blocos)
    processo.minuta.editada = True
    processo.minuta.atualizada_em = datetime.now()
    db.commit()
    return processo.minuta


def refazer_minuta(db: Session, processo: Processo, motor: Motor) -> None:
    if processo.minuta:
        db.delete(processo.minuta)
        db.flush()
    _criar_minuta(processo, motor)
    db.commit()


def definir_situacao(db: Session, processo: Processo, situacao: str) -> None:
    if situacao not in ("a_fazer", "concluido"):
        raise ValueError("situação desconhecida")
    processo.situacao = situacao
    db.commit()


def marcar_audiencia(db: Session, usuario: Usuario, numero: str, data: str, hora: str, tipo: str,
                     motor: Motor) -> Audiencia:
    achado = CNJ.search(numero or "")
    if not achado:
        raise ValueError("informe o número do processo no formato do eproc")
    try:
        inicio = datetime.strptime(f"{data} {hora}", "%Y-%m-%d %H:%M")
    except ValueError:
        raise ValueError("informe a data e a hora da audiência") from None
    if tipo not in TIPOS_AUDIENCIA:
        raise ValueError("tipo de audiência desconhecido")
    a = Audiencia(usuario_id=usuario.id, numero=achado.group(), inicio=inicio, tipo=tipo,
                  ficha=motor.elaborar_ficha(achado.group(), tipo), motor=motor.nome)
    db.add(a)
    db.commit()
    return a


def pauta(db: Session, usuario: Usuario, desde: datetime, dias: int | None = None) -> list[Audiencia]:
    consulta = select(Audiencia).where(Audiencia.usuario_id == usuario.id, Audiencia.inicio >= desde)
    if dias is not None:
        consulta = consulta.where(Audiencia.inicio < desde + timedelta(days=dias))
    return list(db.scalars(consulta.order_by(Audiencia.inicio)))


def audiencia_do_usuario(db: Session, usuario: Usuario, audiencia_id: int) -> Audiencia | None:
    return db.scalar(select(Audiencia).where(Audiencia.id == audiencia_id, Audiencia.usuario_id == usuario.id))


def remover_audiencia(db: Session, audiencia: Audiencia) -> None:
    db.delete(audiencia)
    db.commit()
