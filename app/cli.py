"""Tarefas de administração. Não há cadastro aberto: cada pessoa é convidada uma a uma.

  python -m app.cli criar-usuario EMAIL "Nome"      (a senha é pedida no terminal)
  python -m app.cli semente                         (usuário e fila de demonstração, só dados fictícios)
"""
import getpass
import secrets
import sys
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from . import autos, servicos
from .config import carregar
from .modelos import Usuario, criar_banco
from .portas import ConexaoPlanilha, criar_motor
from .seguranca import gerar_hash

EMAIL_DEMO = "demonstracao@newmpsc.invalid"
FILA_FICTICIA = Path(__file__).parent.parent / "dados_ficticios" / "fila-sig-ficticia.csv"
AUTOS_FICTICIOS = FILA_FICTICIA.with_name("autos-ficticios.pdf")


def criar_usuario(db, email: str, nome: str, senha: str, cargo: str = "", promotoria: str = "") -> Usuario:
    email = email.strip().lower()
    if db.scalar(select(Usuario).where(Usuario.email == email)):
        raise SystemExit(f"já existe usuário com o e-mail {email}")
    usuario = Usuario(email=email, nome=nome, cargo=cargo, promotoria=promotoria, senha_hash=gerar_hash(senha))
    db.add(usuario)
    db.commit()
    return usuario


def semente(db, config, senha: str | None = None) -> str:
    """Cria o usuário de demonstração com a fila, os autos de um processo e a pauta fictícios.
    Devolve a senha gerada."""
    if not config.dados_ficticios:
        raise SystemExit("a semente só roda em ambiente de dados fictícios")
    senha = senha or secrets.token_urlsafe(12)
    motor = criar_motor(config.motor)
    usuario = criar_usuario(db, EMAIL_DEMO, "Promotor de Demonstração", senha, "Promotor de Justiça",
                            "1ª Promotoria de Justiça (fictícia)")
    servicos.importar_fila(db, usuario, FILA_FICTICIA.read_bytes(), FILA_FICTICIA.name, ConexaoPlanilha(), motor, True)
    primeiro = servicos.fila(db, usuario)[0]   # o PDF fictício é deste processo
    servicos.juntar_autos(db, primeiro, AUTOS_FICTICIOS.name, autos.ler(AUTOS_FICTICIOS.read_bytes()), True,
                          config.chave_impressao)
    base = datetime.now().replace(minute=0, second=0, microsecond=0)
    pauta = (("0000102-00.2026.8.24.0000", 1, 14, "Instrução e julgamento"),
             ("0000105-00.2026.8.24.0000", 1, 16, "Custódia"),
             ("0000108-00.2026.8.24.0000", 3, 13, "Instrução e julgamento"))
    for numero, dias, hora, tipo in pauta:
        quando = base + timedelta(days=dias)
        servicos.marcar_audiencia(db, usuario, numero, f"{quando:%Y-%m-%d}", f"{hora:02d}:30", tipo, motor)
    return senha


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    config = carregar()
    _, Sessao = criar_banco(config.banco_url, config.chave_impressao)
    with Sessao() as db:
        if argv[:1] == ["criar-usuario"] and len(argv) == 3:
            senha = getpass.getpass("Senha (12 caracteres ou mais): ")
            criar_usuario(db, argv[1], argv[2], senha)
            print("Usuário criado.")
        elif argv == ["semente"]:
            senha = semente(db, config)
            print(f"Usuário de demonstração: {EMAIL_DEMO}\nSenha (guarde agora; não é mostrada de novo): {senha}")
        else:
            raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
