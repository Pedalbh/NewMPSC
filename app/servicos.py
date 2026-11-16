"""Regras de trabalho: fila de processos, minutas e pauta. Toda consulta filtra pela promotoria de quem pede
(limite 3, cartão C18): quem é da mesma promotoria vê a mesma mesa; ninguém de fora vê."""
import logging
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from .autos import Leitura, impressao, limpar
from .modelos import (
    Acesso,
    ArquivoAutos,
    Audiencia,
    EntregaSig,
    Minuta,
    PaginaAutos,
    PedidoIA,
    Processo,
    TarefaMinuta,
    Usuario,
)
from .nucleo import documento
from .nucleo.tabela import dv_ok
from .portas import Conexao, DadosProcesso, Motor, MotorIndisponivel, PaginaDosAutos, esqueleto

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
COTA_TEXTO_AUTOS = 200_000_000   # caracteres de autos guardados por promotoria
GUARDA_DEPOIS_DE_CONCLUIDO = timedelta(days=30)   # cartão C1: o texto dos autos some sozinho depois disso
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
    recusados: int = 0   # em servidor de dados fictícios: número que não é claramente fictício não entra


def numero_real(numero: str, ficticio: bool) -> bool:
    """Limite 1 do projeto: em servidor de dados fictícios só vale o número claramente fictício, isto é, na
    máscara exata e com dígito verificador inválido. Todo o resto é tratado como real: dígito válido, número
    sem máscara, com espaços, sem os zeros da frente (o dígito de um número fora da máscara não é conferível).
    É um alerta, não uma garantia: número real digitado errado passa, e o texto da minuta não é examinado."""
    return ficticio and not (CNJ.fullmatch(numero or "") and not dv_ok(numero))


def _traz_numero_real(texto: str) -> bool:
    return any(dv_ok(n) for n in numeros_no_texto(texto))


def _dados(processo: Processo, com_autos: bool = False) -> DadosProcesso:
    # objeto talvez ainda não gravado: os valores padrão das colunas só existem depois do flush
    autos = tuple(PaginaDosAutos(a.nome, p.numero, p.texto, a.id) for a in processo.autos for p in a.paginas) \
        if com_autos else ()
    return DadosProcesso(processo.numero, processo.classe or "", processo.assunto or "", processo.vista or "",
                         bool(processo.reu_preso), autos)


def _versao_seguinte(processo: Processo) -> int:
    """A minuta que substitui outra continua a contagem dela. Se voltasse a zero, uma tela aberta na minuta
    antiga salvaria por cima da nova sem aviso (achado na revisão do C18)."""
    return (processo.minuta.versao or 0) + 1 if processo.minuta else 0


def _criar_minuta(processo: Processo, motor: Motor, versao: int = 0) -> None:
    """Primeira minuta do processo. O motor que precisa dos autos não é chamado aqui: fica a estrutura da peça,
    e o usuário pede a escrita depois de enviar os autos."""
    if motor.usa_autos:
        m, nome = esqueleto(_dados(processo)), ORIGEM_EM_BRANCO
    else:
        m, nome = motor.elaborar_minuta(_dados(processo)), motor.nome
    processo.minuta = Minuta(tipo=m["tipo"], blocos=documento.folha(m), motor=nome, versao=versao)


def conferir_versao(processo: Processo, versao: int | None) -> None:
    """Antes de apagar a minuta (refazer, escrever por cima): a tela de quem pede precisa ser a atual."""
    if versao is None:
        raise MinutaMudou("recarregue a página antes de trocar a minuta")
    if processo.minuta and (processo.minuta.versao or 0) != versao:
        raise MinutaMudou("outra pessoa alterou esta minuta; recarregue a página para ver a versão dela")


class EscritaRecusada(ValueError):
    """A mensagem é a orientação mostrada ao usuário."""


class SoPromotor(ValueError):
    """Ato que o assessor não pratica: o que toca o SIG é do promotor (cartão C18)."""


class MinutaMudou(ValueError):
    """Outra pessoa salvou a minuta depois que esta tela a carregou."""


EDICAO_NOVA = timedelta(minutes=30)   # a mesma pessoa voltando a editar depois disso ganha linha nova no registro


def registrar_acesso(db: Session, usuario: Usuario, acao: str, processo: Processo | None = None,
                     promotoria_id: int | None = None) -> None:
    """Uma linha no registro de acessos: quem, o quê, em qual processo, quando. Sem conteúdo. `promotoria_id` só
    é informado nos atos de administração, quando a pessoa ainda não está (ou já não está) na promotoria."""
    onde = promotoria_id if promotoria_id is not None else usuario.promotoria_id
    if onde is None:
        return
    db.add(Acesso(usuario_id=usuario.id, promotoria_id=onde, acao=acao[:60],
                  processo_id=processo.id if processo is not None else None))
    db.commit()


def edicao_a_registrar(processo: Processo, usuario: Usuario, agora: datetime) -> bool:
    """O registro não ganha uma linha a cada tecla: ganha quando muda quem edita ou a pessoa volta depois."""
    minuta = processo.minuta
    return minuta.editada_por != usuario.id or agora - minuta.atualizada_em > EDICAO_NOVA


def versao_da_tela(valor) -> int | None:
    """A versão da minuta que a tela mandou, se for um inteiro plausível; texto, fração ou booleano não valem."""
    if isinstance(valor, str) and valor.isdigit() and len(valor) < 10:
        valor = int(valor)
    if isinstance(valor, bool) or not isinstance(valor, int) or not 0 <= valor < 2**31:
        return None
    return valor


def acessos_da_promotoria(db: Session, promotoria_id: int, limite: int = 200) -> list[Acesso]:
    return list(db.scalars(select(Acesso).where(Acesso.promotoria_id == promotoria_id)
                           .order_by(Acesso.quando.desc(), Acesso.id.desc()).limit(limite)))


def escrevendo(processo: Processo) -> bool:
    return bool(processo.tarefa and processo.tarefa.estado == "escrevendo")


def _vencer(db: Session, tarefa: TarefaMinuta) -> None:
    tarefa.estado, tarefa.erro, tarefa.vista = "falhou", "a escrita demorou demais; peça de novo", False
    for pedido in db.scalars(select(PedidoIA).where(PedidoIA.chave == tarefa.chave, PedidoIA.resultado == "em curso")):
        pedido.resultado = "falhou"


def conferir_escrita(db: Session, processo: Processo) -> None:
    """Escrita que passou do prazo é dada como falha: nada fica preso em "escrevendo"."""
    if escrevendo(processo) and datetime.now() - processo.tarefa.iniciada_em > PRAZO_DA_ESCRITA:
        _vencer(db, processo.tarefa)
        db.commit()


def pedir_escrita(db: Session, processo: Processo, usuario: Usuario, motor: Motor, ficticio: bool,
                  confirmado: bool = False, versao: int | None = None) -> TarefaMinuta:
    """Marca que a minuta deste processo está sendo escrita pelo motor e registra o pedido em nome de quem pediu.
    Os limites são por pessoa. Levanta `EscritaRecusada` com a orientação."""
    if processo.promotoria_id != usuario.promotoria_id:   # a rota já filtra; aqui é a segunda barreira
        raise EscritaRecusada("processo de outra promotoria")
    if not motor.usa_autos:
        raise EscritaRecusada("o motor em uso não escreve a partir dos autos")
    if processo.situacao == "concluido":   # a limpeza do prazo de guarda (C1) não corre junto com uma escrita
        raise EscritaRecusada("o processo está concluído; devolva-o à fila para pedir o relatório")
    # Limite 1 do projeto: em servidor de dados fictícios, processo com número real não vai ao serviço de IA.
    if numero_real(processo.numero, ficticio):
        raise EscritaRecusada("este servidor só aceita dados fictícios, e o número deste processo é real")
    if not any(p.texto for a in processo.autos for p in a.paginas):
        raise EscritaRecusada("envie antes os autos em PDF, com texto para ler")
    if processo.minuta and processo.minuta.editada and not confirmado:
        raise EscritaRecusada("confirme que as alterações feitas na minuta podem ser apagadas")
    if processo.minuta and processo.minuta.editada:
        try:   # o relatório vai apagar o que foi escrito: a tela de quem confirma precisa ser a atual
            conferir_versao(processo, versao)
        except MinutaMudou as e:
            raise EscritaRecusada(str(e)) from None
    agora = datetime.now()
    with _tranca_escrita:
        for tarefa in db.scalars(select(TarefaMinuta).where(TarefaMinuta.estado == "escrevendo",
                                                             TarefaMinuta.iniciada_em < agora - PRAZO_DA_ESCRITA)):
            _vencer(db, tarefa)
        db.flush()
        if escrevendo(processo):
            raise EscritaRecusada("a minuta deste processo já está sendo escrita")
        em_curso = select(func.count()).select_from(TarefaMinuta).where(TarefaMinuta.estado == "escrevendo")
        meus_em_curso = select(func.count()).select_from(PedidoIA).where(
            PedidoIA.usuario_id == usuario.id, PedidoIA.resultado == "em curso")
        if db.scalar(meus_em_curso):
            raise EscritaRecusada("já há uma minuta sua sendo escrita; espere terminar")
        if db.scalar(em_curso) >= ESCRITAS_AO_MESMO_TEMPO:
            raise EscritaRecusada("o servidor está escrevendo outras minutas; tente de novo em instantes")
        feitos = select(func.count()).select_from(PedidoIA).where(PedidoIA.usuario_id == usuario.id)
        if db.scalar(feitos.where(PedidoIA.feito_em > agora - timedelta(hours=1))) >= ESCRITAS_POR_HORA:
            raise EscritaRecusada("você chegou ao limite de pedidos por hora; tente mais tarde")
        if db.scalar(feitos.where(PedidoIA.feito_em > agora - timedelta(days=1))) >= ESCRITAS_POR_DIA:
            raise EscritaRecusada("você chegou ao limite de pedidos por dia; tente amanhã")
        if processo.tarefa:
            db.delete(processo.tarefa)
            db.flush()
        chave = secrets.token_hex(8)
        processo.tarefa = TarefaMinuta(chave=chave)
        db.add(PedidoIA(usuario_id=usuario.id, processo_id=processo.id, chave=chave))
        try:
            db.commit()
        except IntegrityError:   # dois pedidos para o mesmo processo ao mesmo tempo, em servidores diferentes
            db.rollback()
            raise EscritaRecusada("a minuta deste processo já está sendo escrita") from None
    return processo.tarefa


def _minha_escrita(db: Session, processo_id: int, chave: str) -> Processo | None:
    """O processo, se a escrita em curso nele ainda é a de `chave`. Lê do banco de novo: entre o pedido e a
    resposta do motor a pessoa pode ter pedido outra escrita, ou o prazo pode ter vencido."""
    db.expire_all()
    processo = db.get(Processo, processo_id)
    if processo is None or not escrevendo(processo) or processo.tarefa.chave != chave:
        return None
    return processo


def escrever_minuta(db: Session, processo_id: int, chave: str, motor: Motor) -> None:
    """Roda fora da requisição: chama o motor com os autos e grava a minuta, ou o motivo da falha.
    Qualquer que seja o erro, a tarefa sai de "escrevendo". Resultado de escrita que já não vale é descartado."""
    estado, erro, m, blocos = "falhou", "a escrita falhou por um erro inesperado; tente de novo", None, None
    repetir = True
    try:
        processo = _minha_escrita(db, processo_id, chave)
        if processo is None:
            return
        dados = _dados(processo, com_autos=True)
        db.commit()   # devolve a conexão do banco enquanto o motor trabalha
        m = motor.elaborar_minuta(dados)
        blocos = documento.normalizar(documento.folha(m))
        estado, erro = "pronta", ""
    except MotorIndisponivel as e:
        erro, repetir = str(e)[:300], e.passageira
        m = {"modelo": e.modelos} if e.modelos else None
    except Exception as e:   # noqa: BLE001
        _registro.error("escrita da minuta falhou: %s", type(e).__name__)   # sem conteúdo dos autos
    for tentativa in range(3):
        try:
            db.rollback()
            _fechar_escrita(db, processo_id, chave, estado, erro, m, blocos, repetir)
            return
        except Exception as e:   # noqa: BLE001 (banco ocupado: tenta de novo; se não der, o prazo da escrita resolve)
            _registro.error("não gravou o fim da escrita (tentativa %d): %s", tentativa + 1, type(e).__name__)
            time.sleep(0.5 * (tentativa + 1))


def _fechar_escrita(db: Session, processo_id: int, chave: str, estado: str, erro: str, m: dict | None,
                    blocos, repetir: bool = True) -> None:
    processo = _minha_escrita(db, processo_id, chave)
    if processo is None:
        return   # a escrita venceu ou foi trocada por outra: este resultado não entra
    tarefa = processo.tarefa
    if estado == "pronta":
        versao = _versao_seguinte(processo)
        if processo.minuta:
            db.delete(processo.minuta)
            db.flush()
        processo.minuta = Minuta(tipo=m["tipo"], blocos=blocos, motor=ORIGEM_IA, versao=versao)
        tarefa.pontos = [str(p) for p in m.get("pontos") or []]
    tarefa.estado, tarefa.erro, tarefa.vista, tarefa.repetir = estado, erro, False, repetir
    for pedido in db.scalars(select(PedidoIA).where(PedidoIA.chave == chave, PedidoIA.resultado == "em curso")):
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


def importar_fila(db: Session, usuario: Usuario, dados: bytes, nome: str | None, conexao: Conexao,
                  motor: Motor, ficticio: bool) -> ResultadoImportacao:
    """Lê a tabela do SIG e atualiza a fila da promotoria. Processo novo já ganha a primeira minuta.
    Levanta `conexao.Recusada` com a orientação para o usuário."""
    return _atualizar_fila(db, usuario, conexao.ler_fila(dados, nome), motor, ficticio, "planilha")


def buscar_fila(db: Session, usuario: Usuario, conexao: Conexao, motor: Motor, ficticio: bool) -> ResultadoImportacao:
    """Pede a fila direto ao SIG, sem arquivo, e atualiza a fila da promotoria do mesmo jeito que a planilha."""
    return _atualizar_fila(db, usuario, conexao.buscar_fila(usuario.email), motor, ficticio, "sig")


def _atualizar_fila(db: Session, usuario: Usuario, fila: dict, motor: Motor, ficticio: bool,
                    origem: str) -> ResultadoImportacao:
    res = ResultadoImportacao()
    existentes = {p.numero: p for p in db.scalars(select(Processo).where(
        Processo.promotoria_id == usuario.promotoria_id))}
    for linha in fila["linhas"]:
        # classe e assunto são texto livre da planilha e seguem para o motor: também não levam número real
        if numero_real(linha["judiciario"], ficticio) or (
                ficticio and _traz_numero_real(f'{linha["classe"]} {linha["assunto"]} {linha["sig"]}')):
            res.recusados += 1
            continue
        entrada = datetime.fromisoformat(linha["entrada_iso"]) if linha["entrada_iso"] else None
        campos = dict(numero_sig=linha["sig"][:30], classe=linha["classe"][:200], assunto=linha["assunto"][:200],
                      vista=linha["vista"][:40], reu_preso=linha["reu_preso"], entrada=entrada, dv_ok=linha["dv_ok"],
                      grupo=grupo_de(linha["reu_preso"], linha["vista"]))
        p = existentes.get(linha["judiciario"])
        if p is None:
            p = Processo(usuario_id=usuario.id, promotoria_id=usuario.promotoria_id,
                         numero=linha["judiciario"][:25], origem=origem, **campos)
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
    return _gravar_fila(db, res)


def _gravar_fila(db: Session, res: ResultadoImportacao) -> ResultadoImportacao:
    try:
        db.commit()
    except IntegrityError:   # duas pessoas da promotoria trazendo a mesma fila ao mesmo tempo
        db.rollback()
        return ResultadoImportacao(conferir=["outra pessoa trouxe a fila ao mesmo tempo; nada mudou, tente de novo"])
    return res


def colar_numeros(db: Session, usuario: Usuario, texto: str, motor: Motor,
                  ficticio: bool) -> ResultadoImportacao:
    """Aceita números de processo colados em qualquer formato de texto (um por linha, com vírgulas, de um e-mail)."""
    res = ResultadoImportacao()
    numeros = list(dict.fromkeys(CNJ.findall(texto or "")))[:MAX_COLAGEM]
    if not numeros:
        res.conferir.append("nenhum número de processo reconhecido no texto colado")
        return res
    ja = numeros_da_mesa(db, usuario)
    for n in numeros:
        if numero_real(n, ficticio):
            res.recusados += 1
            continue
        if n in ja:
            res.atualizados += 1
            continue
        p = Processo(usuario_id=usuario.id, promotoria_id=usuario.promotoria_id, numero=n, origem="colagem",
                     dv_ok=dv_ok(n), entrada=datetime.now())
        _criar_minuta(p, motor)
        db.add(p)
        res.novos += 1
    return _gravar_fila(db, res)


def apagar_processo(db: Session, usuario: Usuario, numero: str) -> bool:
    """Apaga um processo da promotoria do usuário e tudo o que é dele: minuta, autos, rascunho enviado, escrita,
    registro de pedidos à IA e audiências com o mesmo número. Para dado que entrou por engano; só pela linha de
    comando. O registro de acessos fica: não tem conteúdo, e diz quem mexeu no que foi apagado."""
    if usuario.promotoria_id is None:   # conta desligada não alcança nada, nem linha órfã de banco antigo
        return False
    processo = db.scalar(select(Processo).where(Processo.promotoria_id == usuario.promotoria_id,
                                                Processo.numero == numero))
    audiencias = db.scalars(select(Audiencia).where(Audiencia.promotoria_id == usuario.promotoria_id,
                                                    Audiencia.numero == numero)).all()
    if processo is None and not audiencias:
        return False
    for a in audiencias:
        db.delete(a)
    if processo is not None:
        db.execute(delete(PedidoIA).where(PedidoIA.processo_id == processo.id))
        db.delete(processo)
    db.commit()
    return True


def fila(db: Session, usuario: Usuario, situacao: str = "a_fazer") -> list[Processo]:
    consulta = (select(Processo).where(Processo.promotoria_id == usuario.promotoria_id,
                                       Processo.situacao == situacao)
                .order_by(Processo.grupo, Processo.entrada.is_(None), Processo.entrada, Processo.numero))
    return list(db.scalars(consulta))


def processo_da_mesa(db: Session, usuario: Usuario, processo_id: int) -> Processo | None:
    return db.scalar(select(Processo).where(Processo.id == processo_id,
                                            Processo.promotoria_id == usuario.promotoria_id))


def salvar_minuta(db: Session, processo: Processo, blocos, usuario: Usuario, versao: int | None) -> Minuta:
    """Grava a folha, se `versao` (a que a tela carregou) ainda é a atual: duas pessoas na mesma minuta não se
    apagam em silêncio. Sem versão não grava. Levanta `MinutaMudou` com a orientação."""
    if escrevendo(processo):
        raise ValueError("a minuta está sendo escrita; espere terminar")
    if versao is None:
        raise MinutaMudou("recarregue a página antes de continuar a escrever")
    minuta, blocos = processo.minuta, documento.normalizar(blocos)
    # a conferência e o avanço da versão num comando só: de dois salvamentos juntos, um perde e é avisado
    mudou = db.execute(update(Minuta).where(Minuta.id == minuta.id, Minuta.versao == versao)
                       .values(versao=versao + 1)).rowcount
    if not mudou:
        db.rollback()
        raise MinutaMudou("outra pessoa alterou esta minuta; recarregue a página para ver a versão dela")
    db.refresh(minuta)
    minuta.blocos = blocos
    if processo.tarefa and processo.tarefa.estado == "falhou":
        db.delete(processo.tarefa)   # a pessoa seguiu à mão: o aviso da falha não fica para sempre
    minuta.editada = True
    minuta.atualizada_em = datetime.now()
    minuta.editada_por = usuario.id
    db.commit()
    return minuta


def refazer_minuta(db: Session, processo: Processo, motor: Motor, versao: int | None) -> None:
    if escrevendo(processo):
        raise ValueError("a minuta está sendo escrita; espere terminar")
    conferir_versao(processo, versao)
    seguinte = _versao_seguinte(processo)
    if processo.tarefa:
        db.delete(processo.tarefa)
    if processo.minuta:
        db.delete(processo.minuta)
        db.flush()
    _criar_minuta(processo, motor, seguinte)
    db.commit()


def definir_situacao(db: Session, processo: Processo, situacao: str, agora: datetime | None = None,
                     usuario: Usuario | None = None) -> None:
    if situacao not in ("a_fazer", "concluido"):
        raise ValueError("situação desconhecida")
    if situacao == "a_fazer" and processo.entrega and usuario is not None and usuario.papel != "promotor":
        raise SoPromotor("só o promotor tira o rascunho do SIG")
    if situacao == "concluido" and processo.situacao != "concluido":
        processo.concluido_em = agora or datetime.now()
    elif situacao == "a_fazer":
        processo.concluido_em = None   # voltou à fila: o prazo de guarda zera
        processo.entrega = None        # e o rascunho que estava no SIG sai de lá: a minuta voltou a ser trabalho
    processo.situacao = situacao
    db.commit()


# os mesmos trechos que a folha destaca (app.js): o que a pessoa ainda precisa completar, conferir ou definir
_MARCA = re.compile(r"\[(?:(?:CONFERIR|ESCREVER|DEFINIR)[^\]]*|COMARCA|DEMONSTRAÇÃO)\]")


def trechos_pendentes(blocos: list[dict]) -> int:
    return sum(len(_MARCA.findall(b.get("texto") or "")) for b in blocos)


def entregar_ao_sig(db: Session, processo: Processo, usuario: Usuario, conexao: Conexao, agora: datetime,
                    ficticio: bool) -> EntregaSig:
    """Deixa a minuta no SIG como rascunho, guarda o recibo e conclui o processo na mesa. Enviar de novo troca
    o rascunho. Quem assina e protocola é o usuário, no SIG (limite 2). Levanta ValueError com a orientação."""
    if processo.promotoria_id != usuario.promotoria_id:   # a rota já filtra; aqui é a segunda barreira
        raise ValueError("processo de outra promotoria")
    if usuario.papel != "promotor":
        raise SoPromotor("só o promotor envia ao SIG")
    if escrevendo(processo):
        raise ValueError("a minuta está sendo escrita; espere terminar")
    # Limite 1 do projeto, como nos autos e no pedido à IA: em servidor de dados fictícios, número real não sai.
    if numero_real(processo.numero, ficticio):
        raise ValueError("este servidor só aceita dados fictícios, e o número deste processo é real")
    blocos = [dict(b) for b in processo.minuta.blocos]   # cópia: o rascunho não muda se a minuta mudar depois
    recibo = conexao.entregar_rascunho(usuario.email, processo.numero, documento.texto_simples(blocos))
    try:
        if processo.entrega:
            db.delete(processo.entrega)
            db.flush()
        processo.entrega = EntregaSig(usuario_id=usuario.id, recibo=recibo[:40],
                                      tipo=processo.minuta.tipo, blocos=blocos,
                                      pendentes=trechos_pendentes(blocos), recebida_em=agora)
        definir_situacao(db, processo, "concluido", agora)
    except (IntegrityError, StaleDataError):   # o mesmo processo enviado duas vezes ao mesmo tempo (duas abas)
        db.rollback()
        raise ValueError("este processo já estava sendo enviado; confira em Concluídos") from None
    return processo.entrega


def mudou_depois_do_envio(processo: Processo) -> bool:
    """A minuta da mesa já não é a que está no SIG como rascunho."""
    return bool(processo.entrega and processo.minuta and processo.minuta.blocos != processo.entrega.blocos)


def entregas_da_mesa(db: Session, usuario: Usuario) -> list[EntregaSig]:
    return list(db.scalars(select(EntregaSig).join(Processo)
                           .where(Processo.promotoria_id == usuario.promotoria_id)
                           .order_by(EntregaSig.recebida_em.desc(), EntregaSig.id.desc())))


def numeros_da_mesa(db: Session, usuario: Usuario) -> set[str]:
    return set(db.scalars(select(Processo.numero).where(Processo.promotoria_id == usuario.promotoria_id)))


def autos_apagados_em(processo: Processo) -> datetime | None:
    """Quando o texto dos autos deste processo será apagado (cartão C1); None se não está contando."""
    if processo.situacao != "concluido" or processo.concluido_em is None:
        return None
    return processo.concluido_em + GUARDA_DEPOIS_DE_CONCLUIDO


def apagar_autos_vencidos(db: Session, agora: datetime) -> int:
    """Cartão C1: apaga o texto dos autos de processos concluídos há 30 dias ou mais, de todos os usuários,
    e os pontos a enfrentar que a IA tirou deles. A minuta fica (cartão C13). Devolve quantos arquivos saíram."""
    vencidos = db.scalars(select(ArquivoAutos).join(Processo).where(
        Processo.situacao == "concluido", Processo.concluido_em <= agora - GUARDA_DEPOIS_DE_CONCLUIDO)).all()
    apagados = 0
    for arquivo in vencidos:
        db.refresh(arquivo.processo, ["situacao", "concluido_em"])   # pode ter voltado à fila durante a limpeza
        if autos_apagados_em(arquivo.processo) is None or autos_apagados_em(arquivo.processo) > agora:
            continue
        tarefa = arquivo.processo.tarefa
        if escrevendo(arquivo.processo):
            if datetime.now() - tarefa.iniciada_em <= PRAZO_DA_ESCRITA:
                continue   # escrita em curso de verdade: fica para a próxima hora
            _vencer(db, tarefa)   # escrita presa não segura o apagamento
        if tarefa:
            tarefa.pontos = []
        db.execute(delete(PaginaAutos).where(PaginaAutos.arquivo_id == arquivo.id))   # sem carregar o texto
        db.expire(arquivo, ["paginas"])
        db.delete(arquivo)
        db.commit()   # um arquivo por vez: o banco não fica preso pela limpeza inteira
        apagados += 1
    db.commit()
    if apagados:
        _registro.info("guarda dos autos: %d arquivo(s) apagado(s) por prazo", apagados)
    return apagados


class AutosRecusados(ValueError):
    """A mensagem é a orientação mostrada ao usuário."""


def numeros_no_texto(texto: str) -> set[str]:
    """Números de processo achados no texto, postos na máscara do CNJ."""
    return {"{}-{}.{}.{}.{}.{}".format(*m.groups()) for m in _CNJ_SOLTO.finditer(texto or "")}


def nome_de_arquivo(nome: str | None) -> str:
    return limpar(nome or "")[:200] or "autos.pdf"


def arredondar_caracteres(n: int) -> int:
    """Para cima, em milhares: a cota continua valendo e o número exato não fica guardado."""
    return -(-n // 1000) * 1000


def autos_repetidos(processo: Processo, impressao: str) -> bool:
    return any(a.impressao == impressao for a in processo.autos)


def texto_guardado(db: Session, promotoria_id: int) -> int:
    soma = (select(func.coalesce(func.sum(ArquivoAutos.caracteres), 0)).join(Processo)
            .where(Processo.promotoria_id == promotoria_id))
    return db.scalar(soma)


def juntar_autos(db: Session, processo: Processo, nome: str, leitura: Leitura, ficticio: bool,
                 chave_impressao: bytes) -> ArquivoAutos:
    """Guarda o texto de um PDF dos autos, página a página, no processo (que já é da promotoria de quem envia).
    Levanta `AutosRecusados` com a orientação."""
    nome = nome_de_arquivo(nome)
    if escrevendo(processo):
        raise AutosRecusados("o relatório está sendo escrito com os autos atuais; espere terminar")
    db.refresh(processo, ["situacao"])   # pode ter sido concluído em outra aba durante a leitura do PDF
    if processo.situacao == "concluido":   # cartão C1: o prazo de guarda já está contando
        raise AutosRecusados("o processo está concluído; devolva-o à fila para enviar autos")
    marca = impressao(leitura.sha256, chave_impressao, processo.id)
    if autos_repetidos(processo, marca):
        raise AutosRecusados("este arquivo já está nos autos")
    if len(processo.autos) >= MAX_ARQUIVOS_AUTOS:
        raise AutosRecusados(f"o processo já tem {MAX_ARQUIVOS_AUTOS} arquivos; remova algum antes")
    if texto_guardado(db, processo.promotoria_id) + leitura.caracteres > COTA_TEXTO_AUTOS:
        raise AutosRecusados("a promotoria chegou ao limite de texto guardado; remova autos de processos concluídos")
    numeros = numeros_no_texto("\n".join(leitura.paginas))
    # Limite 1 do projeto. É um alerta, não uma garantia: não enxerga página digitalizada, nome nem CPF.
    if ficticio and any(dv_ok(n) for n in numeros | numeros_no_texto(nome)):
        raise AutosRecusados("este servidor só aceita dados fictícios, e o arquivo traz número de processo real")
    # cartão C2: nem o tamanho exato do arquivo nem a contagem exata de caracteres ficam; os dois juntos
    # identificariam um PDF conhecido tanto quanto o sha256
    arquivo = ArquivoAutos(nome=nome, tamanho=0, impressao=marca,
                           total_paginas=len(leitura.paginas), sem_texto=leitura.sem_texto,
                           caracteres=arredondar_caracteres(leitura.caracteres),
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
                     motor: Motor, ficticio: bool) -> Audiencia:
    achado = CNJ.search(numero or "")
    if not achado:
        raise ValueError("informe o número do processo no formato do eproc")
    if numero_real(achado.group(), ficticio):
        raise ValueError("este servidor só aceita dados fictícios, e o número deste processo é real")
    try:
        inicio = datetime.strptime(f"{data} {hora}", "%Y-%m-%d %H:%M")
    except ValueError:
        raise ValueError("informe a data e a hora da audiência") from None
    if tipo not in TIPOS_AUDIENCIA:
        raise ValueError("tipo de audiência desconhecido")
    a = Audiencia(usuario_id=usuario.id, promotoria_id=usuario.promotoria_id, numero=achado.group(), inicio=inicio,
                  tipo=tipo,
                  ficha=motor.elaborar_ficha(achado.group(), tipo), motor=motor.nome)
    db.add(a)
    db.commit()
    return a


def pauta(db: Session, usuario: Usuario, desde: datetime, dias: int | None = None) -> list[Audiencia]:
    consulta = select(Audiencia).where(Audiencia.promotoria_id == usuario.promotoria_id, Audiencia.inicio >= desde)
    if dias is not None:
        consulta = consulta.where(Audiencia.inicio < desde + timedelta(days=dias))
    return list(db.scalars(consulta.order_by(Audiencia.inicio)))


def audiencia_da_mesa(db: Session, usuario: Usuario, audiencia_id: int) -> Audiencia | None:
    return db.scalar(select(Audiencia).where(Audiencia.id == audiencia_id,
                                             Audiencia.promotoria_id == usuario.promotoria_id))


def remover_audiencia(db: Session, audiencia: Audiencia) -> None:
    db.delete(audiencia)
    db.commit()
