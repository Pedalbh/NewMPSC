"""Portas de troca. A aplicação fala com a IA só pela porta Motor e com o SIG só pela porta Conexão. Trocar o
motor de demonstração pela API do Claude, ou a planilha por uma integração oficial com o SIG, é escrever um
adaptador novo aqui, sem tocar nas telas nem nas regras."""
from dataclasses import dataclass
from typing import Protocol

from .nucleo import tabela

FECHO = "[COMARCA], data da assinatura digital.\n\nPromotor(a) de Justiça"


class MotorIndisponivel(Exception):
    """O motor não conseguiu escrever. A mensagem é a orientação mostrada ao usuário."""


@dataclass(frozen=True)
class PaginaDosAutos:
    arquivo: str
    pagina: int
    texto: str
    arquivo_id: int = 0   # distingue dois arquivos com o mesmo nome


@dataclass(frozen=True)
class DadosProcesso:
    numero: str
    classe: str = ""
    assunto: str = ""
    vista: str = ""
    reu_preso: bool = False
    autos: tuple[PaginaDosAutos, ...] = ()


def tipo_por_classe(classe: str) -> str:
    classe = (classe or "").lower()
    if "inquérito" in classe:
        return "Manifestação em inquérito policial"
    if "protetiva" in classe:
        return "Manifestação em medida protetiva"
    if "ação penal" in classe:
        return "Manifestação em ação penal"
    return "Manifestação"


class Motor(Protocol):
    nome: str
    usa_autos: bool   # True: só escreve com os autos do processo, a pedido do usuário, e pode demorar

    def elaborar_minuta(self, processo: DadosProcesso) -> dict:
        """Devolve {"tipo", "enderecamento", "autos", "paragrafos": [{"secao", "texto"}], "pedidos", "fecho"}.
        Levanta `MotorIndisponivel` com a orientação para o usuário."""

    def elaborar_ficha(self, numero: str, tipo: str) -> dict:
        """Devolve {"resumo", "pontos": [...], "perguntas": [...], "pendencias": [...]}."""


class MotorDemo:
    """Sem IA e sem ler autos: devolve um esqueleto marcado como demonstração, para exercitar as telas e o fluxo.
    Não traz conteúdo jurídico; os colchetes mostram onde o motor real escreverá."""

    nome = "demonstração"
    usa_autos = False

    def elaborar_minuta(self, processo: DadosProcesso) -> dict:
        tipo = tipo_por_classe(processo.classe)
        assunto = processo.assunto or "assunto não informado"
        return {
            "tipo": tipo,
            "enderecamento": "EXCELENTÍSSIMO(A) SENHOR(A) JUIZ(A) DE DIREITO DA VARA CRIMINAL DA COMARCA DE [COMARCA]",
            "autos": processo.numero,
            "paragrafos": [
                {"secao": "", "texto": "O Ministério Público do Estado de Santa Catarina, por seu Promotor de Justiça, "
                                       "vem aos autos se manifestar nos termos que seguem."},
                {"secao": "RELATÓRIO", "texto": f"[DEMONSTRAÇÃO] Resumo do que ocorreu desde a última manifestação do "
                                                f"Ministério Público. Classe: {processo.classe or 'não informada'}. "
                                                f"Assunto: {assunto}."},
                {"secao": "FUNDAMENTAÇÃO", "texto": "[DEMONSTRAÇÃO] Análise do caso. Aqui o motor de IA escreverá a "
                                                    "fundamentação a partir dos autos, com referência a evento e "
                                                    "página, e citações conferidas em fonte oficial."},
            ],
            "verbo": "requer",
            "pedidos": ["[DEMONSTRAÇÃO] o pedido que couber ao momento processual"],
            "fecho": FECHO,
        }

    def elaborar_ficha(self, numero: str, tipo: str) -> dict:
        return {
            "resumo": f"[DEMONSTRAÇÃO] Resumo do caso para a audiência de {tipo.lower()} nos autos {numero}.",
            "pontos": ["[DEMONSTRAÇÃO] Fato imputado e capitulação", "[DEMONSTRAÇÃO] Prova já produzida",
                       "[DEMONSTRAÇÃO] Pontos controvertidos"],
            "perguntas": ["[DEMONSTRAÇÃO] Pergunta sugerida à primeira testemunha",
                          "[DEMONSTRAÇÃO] Pergunta sugerida ao acusado"],
            "pendencias": ["[DEMONSTRAÇÃO] Diligência a conferir antes do ato"],
        }


def esqueleto(processo: DadosProcesso) -> dict:
    """Minuta de espera para o motor que só escreve com os autos: a estrutura da peça, sem conteúdo."""
    return {
        "tipo": tipo_por_classe(processo.classe),
        "enderecamento": "EXCELENTÍSSIMO(A) SENHOR(A) JUIZ(A) DE DIREITO DA VARA CRIMINAL DA COMARCA DE [COMARCA]",
        "autos": processo.numero,
        "paragrafos": [
            {"secao": "", "texto": "O Ministério Público do Estado de Santa Catarina, por seu Promotor de Justiça, "
                                   "vem aos autos se manifestar nos termos que seguem."},
            {"secao": "RELATÓRIO", "texto": "[ESCREVER: relatório]"},
            {"secao": "FUNDAMENTAÇÃO", "texto": "[ESCREVER: fundamentação]"},
        ],
        "verbo": "requer",
        "pedidos": ["[DEFINIR: pedido]"],
        "fecho": FECHO,
    }


def criar_motor(nome: str, modelo: str = "") -> Motor:
    if nome == "demo":
        return MotorDemo()
    if nome == "claude":
        from .motor_claude import MODELO_PADRAO, MotorClaude  # a biblioteca da API só é carregada se for usada
        return MotorClaude(modelo=modelo or MODELO_PADRAO)
    raise RuntimeError(f"motor desconhecido: {nome} (disponíveis: demo, claude)")


class ConexaoPlanilha:
    """Modo de hoje: o SIG entra pela planilha exportada e sai por arquivo .docx ou texto copiado.
    Uma integração oficial (API do SIG ou MNI do eproc) substitui esta classe."""

    nome = "planilha"
    Recusada = tabela.TabelaRecusada

    def ler_fila(self, dados: bytes, nome_arquivo: str | None) -> dict:
        return tabela.ler(dados, nome=nome_arquivo)
