"""Portas de troca. A aplicação fala com a IA só pela porta Motor e com o SIG só pela porta Conexão. Trocar o
motor de demonstração pela API do Claude, ou a planilha por uma integração oficial com o SIG, é escrever um
adaptador novo aqui, sem tocar nas telas nem nas regras."""
from dataclasses import dataclass
from typing import Protocol

from .nucleo import tabela

FECHO = "[Comarca], data da assinatura digital.\n\nPromotor(a) de Justiça"


@dataclass(frozen=True)
class DadosProcesso:
    numero: str
    classe: str = ""
    assunto: str = ""
    vista: str = ""
    reu_preso: bool = False


class Motor(Protocol):
    nome: str

    def elaborar_minuta(self, processo: DadosProcesso) -> dict:
        """Devolve {"tipo", "enderecamento", "autos", "paragrafos": [{"secao", "texto"}], "pedidos", "fecho"}."""

    def elaborar_ficha(self, numero: str, tipo: str) -> dict:
        """Devolve {"resumo", "pontos": [...], "perguntas": [...], "pendencias": [...]}."""


class MotorDemo:
    """Sem IA e sem ler autos: devolve um esqueleto marcado como demonstração, para exercitar as telas e o fluxo.
    Não traz conteúdo jurídico; os colchetes mostram onde o motor real escreverá."""

    nome = "demonstração"

    def elaborar_minuta(self, processo: DadosProcesso) -> dict:
        classe = processo.classe.lower()
        if "inquérito" in classe:
            tipo = "Manifestação em inquérito policial"
        elif "protetiva" in classe:
            tipo = "Manifestação em medida protetiva"
        elif "ação penal" in classe:
            tipo = "Manifestação em ação penal"
        else:
            tipo = "Manifestação"
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


def criar_motor(nome: str) -> Motor:
    if nome == "demo":
        return MotorDemo()
    raise RuntimeError(f"motor desconhecido: {nome} (disponível: demo; o adaptador da API do Claude entra aqui)")


class ConexaoPlanilha:
    """Modo de hoje: o SIG entra pela planilha exportada e sai por arquivo .docx ou texto copiado.
    Uma integração oficial (API do SIG ou MNI do eproc) substitui esta classe."""

    nome = "planilha"
    Recusada = tabela.TabelaRecusada

    def ler_fila(self, dados: bytes, nome_arquivo: str | None) -> dict:
        return tabela.ler(dados, nome=nome_arquivo)
