"""Portas de troca. A aplicação fala com a IA só pela porta Motor e com o SIG só pela porta Conexão. Trocar o
motor de demonstração pela API do Claude, ou a planilha por uma integração oficial com o SIG, é escrever um
adaptador novo aqui, sem tocar nas telas nem nas regras."""
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .nucleo import tabela

FECHO = "[COMARCA], data da assinatura digital.\n\nPromotor(a) de Justiça"


class MotorIndisponivel(Exception):
    """O motor não conseguiu escrever. A mensagem é a orientação mostrada ao usuário.
    `passageira` diz se adianta tentar de novo sem mudar nada."""

    def __init__(self, mensagem: str, passageira: bool = True, modelos: str = ""):
        super().__init__(mensagem)
        self.passageira = passageira
        self.modelos = modelos   # quem recebeu os autos, quando já se sabe (vai para o registro do pedido)


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


class SigIndisponivel(Exception):
    """O SIG não respondeu à busca ou à entrega. A tela orienta a tentar de novo ou usar a planilha."""


class Conexao(Protocol):
    """A porta do SIG. `busca_direta` diz se a fila chega e a minuta volta sem arquivo no meio."""
    nome: str
    busca_direta: bool
    Recusada: type[Exception]

    def ler_fila(self, dados: bytes, nome_arquivo: str | None) -> dict:
        """A fila a partir da planilha exportada, no contrato sig-tabela (`linhas` e `conferir`)."""

    def buscar_fila(self, quem: str) -> dict:
        """A fila de `quem` (a pessoa que está usando) pedida direto ao SIG, no mesmo contrato. Só com
        `busca_direta`. Levanta `SigIndisponivel`."""

    def entregar_rascunho(self, quem: str, numero: str, texto: str) -> str:
        """Deixa a minuta no SIG como rascunho de `quem`, sem assinatura, e devolve o recibo. Só com
        `busca_direta`. Assinar e protocolar continuam sendo do usuário, no SIG. Levanta `SigIndisponivel`.

        `quem` existe para a integração oficial agir com a identidade da própria pessoa, e não com uma conta de
        serviço que enxergue várias promotorias: a fila é a dela e o rascunho fica em nome dela. Hoje é o e-mail;
        na integração oficial passa a ser a credencial delegada da pessoa (um token dela), não um nome que uma
        conta de serviço use para se passar por ela.

        A aplicação chama este método antes de gravar o recibo. O adaptador oficial precisa aceitar a repetição
        para o mesmo processo sem duplicar o rascunho (ou oferecer como desfazer): se a gravação do recibo falhar,
        ou dois envios chegarem juntos, não pode sobrar rascunho órfão no SIG."""


class ConexaoPlanilha:
    """Modo de hoje: o SIG entra pela planilha exportada e sai por arquivo .docx ou texto copiado.
    Uma integração oficial (API do SIG ou MNI do eproc) substitui esta classe."""

    nome = "planilha"
    busca_direta = False
    Recusada = tabela.TabelaRecusada

    def ler_fila(self, dados: bytes, nome_arquivo: str | None) -> dict:
        return tabela.ler(dados, nome=nome_arquivo)

    def buscar_fila(self, quem: str) -> dict:
        raise NotImplementedError("a planilha não busca a fila sozinha")

    def entregar_rascunho(self, quem: str, numero: str, texto: str) -> str:
        raise NotImplementedError("a planilha não recebe minuta")


FILA_DO_SIG_SIMULADO = Path(__file__).parent.parent / "dados_ficticios" / "fila-sig-ficticia.csv"


class ConexaoSigSimulado(ConexaoPlanilha):
    """Protótipo do envelope: faz o papel do SIG com dados fictícios, para mostrar o fluxo sem arquivo.
    Não fala com o SIG de verdade nem com o eproc, e a aplicação só parte com ele em ambiente de dados
    fictícios. A fila é sempre a do arquivo fictício; o rascunho entregue fica guardado na própria aplicação
    (`entregas_sig`), que o mostra na tela "SIG simulado". A integração oficial, se o MPSC abrir, é outra classe
    com estes mesmos três métodos, agindo com a identidade de `quem` pede."""

    nome = "SIG simulado"
    busca_direta = True

    def __init__(self, fila: Path = FILA_DO_SIG_SIMULADO):
        self._fila = fila

    def buscar_fila(self, quem: str) -> dict:
        try:   # a mesma fila fictícia para todos: o simulado não tem promotorias
            return tabela.ler(self._fila.read_bytes(), nome=self._fila.name)
        except OSError:
            raise SigIndisponivel from None

    def entregar_rascunho(self, quem: str, numero: str, texto: str) -> str:
        return f"SIM-{secrets.token_hex(4).upper()}"   # o recibo que um SIG devolveria; nada sai da aplicação


def criar_conexao(nome: str) -> Conexao:
    if nome == "planilha":
        return ConexaoPlanilha()
    if nome == "simulado":
        return ConexaoSigSimulado()
    raise RuntimeError(f"conexão desconhecida: {nome} (disponíveis: planilha, simulado)")
