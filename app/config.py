"""Configuração lida do ambiente (nenhum segredo no código)."""
import hashlib
import hmac
import logging
import os
import secrets
from dataclasses import dataclass

AMBIENTES = ("desenvolvimento", "teste", "producao")


@dataclass(frozen=True)
class Config:
    ambiente: str
    segredo: str
    banco_url: str
    motor: str
    dados_ficticios: bool
    modelo: str = ""

    @property
    def producao(self) -> bool:
        return self.ambiente == "producao"

    @property
    def chave_impressao(self) -> bytes:
        """Chave das impressões dos autos (C2), derivada do segredo do servidor. Trocar o segredo faz os arquivos
        já guardados deixarem de ser reconhecidos como repetidos."""
        return hmac.new(self.segredo.encode(), b"newmpsc/impressao-dos-autos", hashlib.sha256).digest()


def carregar(env=None) -> Config:
    env = os.environ if env is None else env
    ambiente = env.get("NEWMPSC_AMBIENTE", "desenvolvimento")
    if ambiente not in AMBIENTES:
        raise RuntimeError(f"NEWMPSC_AMBIENTE inválido: use um de {AMBIENTES}")
    segredo = env.get("NEWMPSC_SEGREDO", "")
    if ambiente == "producao" and len(segredo) < 32:
        raise RuntimeError("NEWMPSC_SEGREDO com 32 caracteres ou mais é obrigatório em produção")
    if ambiente == "producao" and env.get("ANTHROPIC_LOG"):
        raise RuntimeError("ANTHROPIC_LOG não pode estar ligado em produção: o registro traria o texto dos autos")
    motor = env.get("NEWMPSC_MOTOR", "demo")
    ficticios = env.get("NEWMPSC_DADOS_FICTICIOS", "1") != "0"
    if motor != "demo" and not ficticios:
        # Cartão C4: texto de processo real só vai para um serviço de IA depois de contrato institucional.
        raise RuntimeError("motor de IA só com dados fictícios: dado real depende de contrato institucional")
    if not segredo:
        logging.getLogger("newmpsc").warning(
            "NEWMPSC_SEGREDO não definido: sessões e impressões dos autos mudam a cada partida")
    return Config(
        ambiente=ambiente,
        segredo=segredo or secrets.token_urlsafe(32),
        banco_url=env.get("NEWMPSC_BANCO", "sqlite:///newmpsc.db"),
        motor=motor,
        # Enquanto não houver hospedagem e contrato institucionais, a aplicação só trabalha com dados fictícios.
        dados_ficticios=ficticios,
        modelo=env.get("NEWMPSC_MODELO", ""),
    )
