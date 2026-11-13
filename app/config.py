"""Configuração lida do ambiente (nenhum segredo no código)."""
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

    @property
    def producao(self) -> bool:
        return self.ambiente == "producao"


def carregar(env=None) -> Config:
    env = os.environ if env is None else env
    ambiente = env.get("NEWMPSC_AMBIENTE", "desenvolvimento")
    if ambiente not in AMBIENTES:
        raise RuntimeError(f"NEWMPSC_AMBIENTE inválido: use um de {AMBIENTES}")
    segredo = env.get("NEWMPSC_SEGREDO", "")
    if ambiente == "producao" and len(segredo) < 32:
        raise RuntimeError("NEWMPSC_SEGREDO com 32 caracteres ou mais é obrigatório em produção")
    return Config(
        ambiente=ambiente,
        segredo=segredo or secrets.token_urlsafe(32),
        banco_url=env.get("NEWMPSC_BANCO", "sqlite:///newmpsc.db"),
        motor=env.get("NEWMPSC_MOTOR", "demo"),
        # Enquanto não houver hospedagem e contrato institucionais, a aplicação só trabalha com dados fictícios.
        dados_ficticios=env.get("NEWMPSC_DADOS_FICTICIOS", "1") != "0",
    )
