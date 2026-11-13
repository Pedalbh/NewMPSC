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
    ambiente = env.get("MESA_AMBIENTE", "desenvolvimento")
    if ambiente not in AMBIENTES:
        raise RuntimeError(f"MESA_AMBIENTE inválido: use um de {AMBIENTES}")
    segredo = env.get("MESA_SEGREDO", "")
    if ambiente == "producao" and len(segredo) < 32:
        raise RuntimeError("MESA_SEGREDO com 32 caracteres ou mais é obrigatório em produção")
    return Config(
        ambiente=ambiente,
        segredo=segredo or secrets.token_urlsafe(32),
        banco_url=env.get("MESA_BANCO", "sqlite:///mesa.db"),
        motor=env.get("MESA_MOTOR", "demo"),
        # Enquanto não houver hospedagem e contrato institucionais, a aplicação só trabalha com dados fictícios.
        dados_ficticios=env.get("MESA_DADOS_FICTICIOS", "1") != "0",
    )
