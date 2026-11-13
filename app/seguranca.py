"""Senha, proteção contra CSRF e limite de tentativas de login."""
import hmac
import secrets
import time
from collections import defaultdict

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()
# Hash de uma senha qualquer: conferido quando o e-mail não existe, para o tempo de resposta não revelar isso.
_HASH_FALSO = _hasher.hash(secrets.token_urlsafe(16))

TAMANHO_MINIMO_SENHA = 12


def gerar_hash(senha: str) -> str:
    if len(senha) < TAMANHO_MINIMO_SENHA:
        raise ValueError(f"a senha precisa de {TAMANHO_MINIMO_SENHA} caracteres ou mais")
    return _hasher.hash(senha)


def conferir_senha(senha_hash: str | None, senha: str) -> bool:
    try:
        return _hasher.verify(senha_hash or _HASH_FALSO, senha) and senha_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def token_csrf(sessao: dict) -> str:
    if "csrf" not in sessao:
        sessao["csrf"] = secrets.token_urlsafe(32)
    return sessao["csrf"]


def csrf_confere(sessao: dict, recebido: str | None) -> bool:
    esperado = sessao.get("csrf")
    return bool(esperado and recebido and hmac.compare_digest(esperado, recebido))


class LimiteTentativas:
    """Até `maximo` falhas por chave em `janela` segundos. Em memória: basta para um servidor só; com mais de um,
    trocar por um armazenamento compartilhado."""

    def __init__(self, maximo: int = 5, janela: int = 900, relogio=time.monotonic):
        self.maximo, self.janela, self._relogio = maximo, janela, relogio
        self._falhas: dict[str, list[float]] = defaultdict(list)

    def _recentes(self, chave: str) -> list[float]:
        agora = self._relogio()
        self._falhas[chave] = [t for t in self._falhas[chave] if agora - t < self.janela]
        return self._falhas[chave]

    def bloqueado(self, chave: str) -> bool:
        return len(self._recentes(chave)) >= self.maximo

    def registrar_falha(self, chave: str) -> None:
        self._recentes(chave).append(self._relogio())

    def limpar(self, chave: str) -> None:
        self._falhas.pop(chave, None)
