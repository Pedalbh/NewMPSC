"""Regras de trabalho: fila de processos, minutas e pauta. Toda consulta filtra pelo usuário."""
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .autos import Leitura, limpar
from .modelos import ArquivoAutos, Audiencia, Minuta, PaginaAutos, PedidoIA, Processo, TarefaMinuta, Usuario
from .nucleo import documento
from .nucleo.tabela import dv_ok
from .portas import ConexaoPlanilha, DadosProcesso, Motor, MotorIndisponivel, PaginaDosAutos, esqueleto

CNJ = re.compile(r"(?<!\d)\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}(?!\d)")
GRUPOS = ("Réu preso", "Vista urgente", "Intimação", "Outros")
MAX_COLAGEM = 200
MAX_ARQUIVOS_AUTOS = 30   # por processo
ESCRITAS_POR_HORA, ESCRITAS_POR_DIA = 20, 60   # pedidos ao serviço de IA, por usuário
ESCRITAS_AO_MESMO_TEMPO = 4                   # no servidor todo
PRAZO_DA_ESCRITA = timedelta(minutes=15)      # depois disso a escrita é dada como falha
ORIGEM_EM_BRANCO, ORIGEM_IA = "em branco", "IA, a conferir"
_registro = logging.getLogger("newmpsc")
_tranca_escrita = threading.Lock()   # um servidor só: pedidos simultâneos de escrita entram um de cada vez
COTA_TEXTO_AUTOS = 200_000_000   # caracteres de autos guardados por usuário
# o número como sai de um PDF: com ou sem máscara, com espaços ou quebra de linha no meio
_CNJ_SOLTO = re.compile(r"(?<!\d)(\d{7})[\s.\-/]{0,3}(\d{2})[\s.\-/]{0,3}(\d{4})[\s.\-/]{0,3}(\d)[\s.\-/]{0,3}(\d{2})"
                        r"[\s.\-/]{0,3}(\d{4})(?!\d)")
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


def _dados(processo: Processo, com_autos: bool = False) -> DadosProcesso:
    # objeto talvez ainda não gravado: os valores padrão das colunas só existem depois do flush
    autos = tuple(PaginaDosAutos(a.nome, p.numero, p.texto, a.id) for a in processo.autos for p in a.paginas) \
        if com_autos else ()
    return DadosProcesso(processo.numero, processo.classe or "", processo.assunto or "", processo.vista or "",
                         bool(processo.reu_preso), autos)


def _criar_minuta(processo: Processo, motor: Motor) -> None:
    """Primeira minuta do processo. O motor que precisa dos autos não é chamado aqui: fica a estrutura da peça,
    e o usuário pede a escrita depois de enviar os autos."""
    if motor.usa_autos:
        m, nome = esqueleto(_dados(processo)), ORIGEM_EM_BRANCO
    else:
        m, nome = motor.elaborar_minuta(_dados(processo)), motor.nome
    processo.minuta = Minuta(tipo=m["tipo"], blocos=documento.folha(m), motor=nome)


class EscritaRecusada(ValueError):
    """A mensagem é a orientação mostrada ao usuário."""


def escrevendo(processo: Processo) -> bool:
    return bool(processo.tarefa and processo.tarefa.estado == "escrevendo")


def conferir_escrita(db: Session, processo: Processo) -> None:
    """Escrita que passou do prazo é dada como falha: nada fica preso em "escrevendo"."""
    if escrevendo(processo) and datetime.now() - processo.tarefa.iniciada_em > PRAZO_DA_ESCRITA:
        processo.tarefa.estado, processo.tarefa.erro = "falhou", "a escrita demorou demais; peça de novo"
        processo.tarefa.vista = False
        db.commit()


def pedir_escrita(db: Session, processo: Processo, motor: Motor, ficticio: bool,
                  confirmado: bool = False) -> TarefaMinuta:
    """Marca que a minuta deste processo está sendo escrita pelo motor e registra o pedido.
    Levanta `EscritaRecusada` com a orientação."""
    if not motor.usa_autos:
        raise EscritaRecusada("o motor em uso não escreve a partir dos autos")
    # Limite 1 do projeto: em servidor de dados fictícios, processo com número real não vai ao serviço de IA.
    if ficticio and dv_ok(processo.numero):
        raise EscritaRecusada("este servidor só aceita dados fictícios, e o número deste processo é real")
    if not any(p.texto for a in processo.autos for p in a.paginas):
        raise EscritaRecusada("envie antes os autos em PDF, com texto para ler")
    if processo.minuta and processo.minuta.editada and not confirmado:
        raise EscritaRecusada("confirme que as suas alterações na minuta podem ser apagadas")
    agora = datetime.now()
    with _tranca_escrita:
        for tarefa in db.scalars(select(TarefaMinuta).where(TarefaMinuta.estado == "escrevendo",
                                                             TarefaMinuta.iniciada_em < agora - PRAZO_DA_ESCRITA)):
            tarefa.estado, tarefa.erro, tarefa.vista = "falhou", "a escrita demorou demais; peça de novo", False
        db.flush()
        if escrevendo(processo):
            raise EscritaRecusada("a minuta deste processo já está sendo escrita")
        em_curso = select(func.count()).select_from(TarefaMinuta).where(TarefaMinuta.estado == "escrevendo")
        if db.scalar(em_curso.join(Processo).where(Processo.usuario_id == processo.usuario_id)):
            raise EscritaRecusada("já há uma minuta sua sendo escrita; espere terminar")
        if db.scalar(em_curso) >= ESCRITAS_AO_MESMO_TEMPO:
            raise EscritaRecusada("o servidor está escrevendo outras minutas; tente de novo em instantes")
        feitos = select(func.count()).select_from(PedidoIA).where(PedidoIA.usuario_id == processo.usuario_id)
        if db.scalar(feitos.where(PedidoIA.feito_em > agora - timedelta(hours=1))) >= ESCRITAS_POR_HORA:
            raise EscritaRecusada("você chegou ao limite de pedidos por hora; tente mais tarde")
        if db.scalar(feitos.where(PedidoIA.feito_em > agora - timedelta(days=1))) >= ESCRITAS_POR_DIA:
            raise EscritaRecusada("você chegou ao limite de pedidos por dia; tente amanhã")
        if processo.tarefa:
            db.delete(processo.tarefa)
            db.flush()
        processo.tarefa = TarefaMinuta()
        db.add(PedidoIA(usuario_id=processo.usuario_id, processo_id=processo.id))
        try:
            db.commit()
        except IntegrityError:   # dois pedidos para o mesmo processo ao mesmo tempo, em servidores diferentes
            db.rollback()
            raise EscritaRecusada("a minuta deste processo já está sendo escrita") from None
    return processo.tarefa


def escrever_minuta(db: Session, processo_id: int, motor: Motor) -> None:
    """Roda fora da requisição: chama o motor com os autos e grava a minuta, ou o motivo da falha.
    Qualquer que seja o erro, a tarefa sai de "escrevendo"."""
    estado, erro, m, blocos = "falhou", "a escrita falhou por um erro inesperado; tente de novo", None, None
    try:
        processo = db.get(Processo, processo_id)
        if processo is None or not escrevendo(processo):
            return
        dados = _dados(processo, com_autos=True)
        db.commit()   # devolve a conexão do banco enquanto o motor trabalha
        m = motor.elaborar_minuta(dados)
        blocos = documento.normalizar(documento.folha(m))
        estado, erro = "pronta", ""
    except MotorIndisponivel as e:
        erro = str(e)[:300]
    except Exception as e:   # noqa: BLE001
        _registro.error("escrita da minuta falhou: %s", type(e).__name__)   # sem conteúdo dos autos
    for tentativa in range(3):
        try:
            db.rollback()
            _fechar_escrita(db, processo_id, estado, erro, m, blocos)
            return
        except Exception as e:   # noqa: BLE001 (banco ocupado: tenta de novo; se não der, o prazo da escrita resolve)
            _registro.error("não gravou o fim da escrita (tentativa %d): %s", tentativa + 1, type(e).__name__)
            time.sleep(0.5 * (tentativa + 1))


def _fechar_escrita(db: Session, processo_id: int, estado: str, erro: str, m: dict | None, blocos) -> None:
    processo = db.get(Processo, processo_id)
    if processo is None or not escrevendo(processo):
        return
    tarefa = processo.tarefa
    if estado == "pronta":
        if processo.minuta:
            db.delete(processo.minuta)
            db.flush()
        processo.minuta = Minuta(tipo=m["tipo"], blocos=blocos, motor=ORIGEM_IA)
        tarefa.pontos = [str(p) for p in m.get("pontos") or []]
    tarefa.estado, tarefa.erro, tarefa.vista = estado, erro, False
    pedido = db.scalar(select(PedidoIA).where(PedidoIA.processo_id == processo_id, PedidoIA.resultado == "em curso")
                       .order_by(PedidoIA.id.desc()))
    if pedido:
        pedido.resultado, pedido.modelo = estado, str((m or {}).get("modelo") or "")[:60]
    db.commit()


def marcar_resultado_como_visto(db: Session, processo: Processo) -> bool:
    """Diz se há resultado de escrita ainda não mostrado ao usuário, e marca como mostrado."""
    tarefa = processo.tarefa
    if tarefa is None or tarefa.estado == "escrevendo" or tarefa.vista:
        return False
    tarefa.vista = True
    db.commit()
    return True


def encerrar_escritas_interrompidas(db: Session) -> None:
    """Na partida do servidor: o que estava sendo escrito quando ele parou é marcado como falha."""
    for tarefa in db.scalars(select(TarefaMinuta).where(TarefaMinuta.estado == "escrevendo")):
        tarefa.estado, tarefa.erro = "falhou", "o servidor reiniciou durante a escrita; peça de novo"
    for pedido in db.scalars(select(PedidoIA).where(PedidoIA.resultado == "em curso")):
        pedido.resultado = "falhou"
    db.commit()


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
    if escrevendo(processo):
        raise ValueError("a minuta está sendo escrita; espere terminar")
    processo.minuta.blocos = documento.normalizar(blocos)
    if processo.tarefa and processo.tarefa.estado == "falhou":
        db.delete(processo.tarefa)   # a pessoa seguiu à mão: o aviso da falha não fica para sempre
    processo.minuta.editada = True
    processo.minuta.atualizada_em = datetime.now()
    db.commit()
    return processo.minuta


def refazer_minuta(db: Session, processo: Processo, motor: Motor) -> None:
    if escrevendo(processo):
        raise ValueError("a minuta está sendo escrita; espere terminar")
    if processo.tarefa:
        db.delete(processo.tarefa)
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


class AutosRecusados(ValueError):
    """A mensagem é a orientação mostrada ao usuário."""


def numeros_no_texto(texto: str) -> set[str]:
    """Números de processo achados no texto, postos na máscara do CNJ."""
    return {"{}-{}.{}.{}.{}.{}".format(*m.groups()) for m in _CNJ_SOLTO.finditer(texto or "")}


def nome_de_arquivo(nome: str | None) -> str:
    return limpar(nome or "")[:200] or "autos.pdf"


def autos_repetidos(processo: Processo, sha256: str) -> bool:
    return any(a.sha256 == sha256 for a in processo.autos)


def texto_guardado(db: Session, usuario_id: int) -> int:
    soma = (select(func.coalesce(func.sum(ArquivoAutos.caracteres), 0)).join(Processo)
            .where(Processo.usuario_id == usuario_id))
    return db.scalar(soma)


def juntar_autos(db: Session, processo: Processo, nome: str, leitura: Leitura, ficticio: bool) -> ArquivoAutos:
    """Guarda o texto de um PDF dos autos, página a página, no processo (que já é do usuário).
    Levanta `AutosRecusados` com a orientação."""
    nome = nome_de_arquivo(nome)
    if escrevendo(processo):
        raise AutosRecusados("o relatório está sendo escrito com os autos atuais; espere terminar")
    if autos_repetidos(processo, leitura.sha256):
        raise AutosRecusados("este arquivo já está nos autos")
    if len(processo.autos) >= MAX_ARQUIVOS_AUTOS:
        raise AutosRecusados(f"o processo já tem {MAX_ARQUIVOS_AUTOS} arquivos; remova algum antes")
    if texto_guardado(db, processo.usuario_id) + leitura.caracteres > COTA_TEXTO_AUTOS:
        raise AutosRecusados("você chegou ao limite de texto guardado; remova autos de processos já concluídos")
    numeros = numeros_no_texto("\n".join(leitura.paginas))
    # Limite 1 do projeto. É um alerta, não uma garantia: não enxerga página digitalizada, nome nem CPF.
    if ficticio and any(dv_ok(n) for n in numeros | numeros_no_texto(nome)):
        raise AutosRecusados("este servidor só aceita dados fictícios, e o arquivo traz número de processo real")
    arquivo = ArquivoAutos(nome=nome, tamanho=leitura.tamanho, sha256=leitura.sha256,
                           total_paginas=len(leitura.paginas), sem_texto=leitura.sem_texto,
                           caracteres=leitura.caracteres,
                           cita_processo=processo.numero in numeros or leitura.sem_texto == len(leitura.paginas),
                           paginas=[PaginaAutos(numero=i, texto=t) for i, t in enumerate(leitura.paginas, start=1)])
    processo.autos.append(arquivo)
    try:
        db.commit()
    except IntegrityError:   # o mesmo arquivo chegou duas vezes ao mesmo tempo
        db.rollback()
        raise AutosRecusados("este arquivo já está nos autos") from None
    return arquivo


def remover_autos(db: Session, processo: Processo, arquivo_id: int) -> bool:
    if escrevendo(processo):
        raise AutosRecusados("o relatório está sendo escrito com os autos atuais; espere terminar")
    arquivo = next((a for a in processo.autos if a.id == arquivo_id), None)
    if arquivo is None:
        return False
    processo.autos.remove(arquivo)
    db.commit()
    return True


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
