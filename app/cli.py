"""Tarefas de administração. Não há cadastro aberto: cada pessoa é convidada uma a uma.

  python -m app.cli criar-promotoria "Nome"         (o espaço de trabalho; as pessoas entram nele pelos comandos abaixo)
  python -m app.cli criar-usuario EMAIL "Nome" "Promotoria" [promotor|assessor]
                                                    (a senha é pedida no terminal; a promotoria precisa existir)
  python -m app.cli mover-usuario EMAIL "Promotoria" [promotor|assessor]
                                                    (passa a ver só a mesa da nova promotoria, na hora)
  python -m app.cli desligar-usuario EMAIL          (sai da promotoria e perde o acesso na hora)
  python -m app.cli acessos "Promotoria"            (registro de acessos: quem fez o quê, e quando)
  python -m app.cli semente                         (usuário e fila de demonstração, só dados fictícios)
  python -m app.cli limpar-autos                    (apaga os autos vencidos; para o agendador da hospedagem)
  python -m app.cli apagar-processo EMAIL NUMERO    (apaga da promotoria da pessoa o processo e tudo o que é dele)
"""
import getpass
import os
import secrets
import sys
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from . import autos, servicos
from .config import carregar
from .modelos import PAPEIS, Promotoria, Usuario, criar_banco
from .portas import ConexaoPlanilha, criar_motor
from .seguranca import gerar_hash

EMAIL_DEMO = "demonstracao@newmpsc.invalid"
FILA_FICTICIA = Path(__file__).parent.parent / "dados_ficticios" / "fila-sig-ficticia.csv"
AUTOS_FICTICIOS = FILA_FICTICIA.with_name("autos-ficticios.pdf")


def _nome_de_promotoria(nome: str) -> str:
    nome = " ".join(nome.split())[:160]
    if not nome:
        raise SystemExit("informe o nome da promotoria")
    return nome


def _promotoria(db, nome: str, criar: bool = False) -> Promotoria:
    """A promotoria com este nome exato. Só é criada quando quem chama pede: um erro de digitação ao convidar
    alguém não abre uma promotoria nova em silêncio."""
    nome = _nome_de_promotoria(nome)
    promotoria = db.scalar(select(Promotoria).where(Promotoria.nome == nome))
    if promotoria is None:
        if not criar:
            raise SystemExit(f"não há promotoria chamada {nome!r}; confira o nome ou crie com criar-promotoria")
        promotoria = Promotoria(nome=nome)
        db.add(promotoria)
        db.flush()
    return promotoria


def criar_promotoria(db, nome: str) -> Promotoria:
    nome = _nome_de_promotoria(nome)
    if db.scalar(select(Promotoria).where(Promotoria.nome == nome)):
        raise SystemExit(f"já existe promotoria chamada {nome!r}")
    promotoria = _promotoria(db, nome, criar=True)
    db.commit()
    return promotoria


def membros(db, promotoria: Promotoria) -> list[str]:
    return [f"{u.email} ({u.papel})" for u in db.scalars(
        select(Usuario).where(Usuario.promotoria_id == promotoria.id).order_by(Usuario.email))]


def _papel(papel: str) -> str:
    if papel not in PAPEIS:
        raise SystemExit(f"papel desconhecido: use {' ou '.join(PAPEIS)}")
    return papel


def _usuario(db, email: str) -> Usuario:
    usuario = db.scalar(select(Usuario).where(Usuario.email == email.strip().lower()))
    if usuario is None:
        raise SystemExit("não há usuário com esse e-mail")
    return usuario


def criar_usuario(db, email: str, nome: str, senha: str, cargo: str = "", promotoria: str = "",
                  papel: str = "promotor", criar_promotoria: bool = True) -> Usuario:
    """Sem `promotoria`, a pessoa ganha uma mesa só dela (nunca entra na de alguém por omissão). A linha de
    comando chama com `criar_promotoria=False`: lá a promotoria precisa existir."""
    email = email.strip().lower()
    if db.scalar(select(Usuario).where(Usuario.email == email)):
        raise SystemExit(f"já existe usuário com o e-mail {email}")
    espaco = _promotoria(db, promotoria or f"Mesa de {email}", criar=criar_promotoria or not promotoria)
    usuario = Usuario(email=email, nome=nome, cargo=cargo, promotoria=espaco.nome, espaco=espaco,
                      papel=_papel(papel), senha_hash=gerar_hash(senha))
    db.add(usuario)
    db.commit()
    servicos.registrar_acesso(db, usuario, f"administração: entrou como {usuario.papel}")
    return usuario


def mover_usuario(db, email: str, promotoria: str, papel: str | None = None) -> Usuario:
    """Passa a pessoa para outra promotoria. Vale na requisição seguinte: ela deixa de ver a mesa antiga, e o
    que ela trouxe ou escreveu fica com a promotoria de onde saiu."""
    usuario, espaco = _usuario(db, email), _promotoria(db, promotoria)
    papel = _papel(papel) if papel is not None else usuario.papel
    antiga = usuario.promotoria_id
    if antiga is not None and antiga != espaco.id:
        servicos.registrar_acesso(db, usuario, "administração: saiu (movido)", promotoria_id=antiga)
    usuario.espaco, usuario.promotoria, usuario.papel = espaco, espaco.nome, papel
    db.commit()
    servicos.registrar_acesso(db, usuario, f"administração: entrou como {papel}")
    return usuario


def desligar_usuario(db, email: str) -> Usuario:
    """Tira a pessoa da promotoria. Sem promotoria a conta não entra, e a sessão aberta cai na requisição
    seguinte. O trabalho dela fica com a promotoria."""
    usuario = _usuario(db, email)
    if usuario.promotoria_id is not None:
        servicos.registrar_acesso(db, usuario, "administração: desligado", promotoria_id=usuario.promotoria_id)
    usuario.espaco, usuario.promotoria = None, ""
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
        servicos.marcar_audiencia(db, usuario, numero, f"{quando:%Y-%m-%d}", f"{hora:02d}:30", tipo, motor,
                                  config.dados_ficticios)
    return senha


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["limpar-autos"] and not os.environ.get("NEWMPSC_SEGREDO"):
        # sem o segredo do servidor, a chave das impressões seria sorteada e um banco antigo seria convertido com ela
        raise SystemExit("defina NEWMPSC_SEGREDO igual ao do servidor antes de limpar os autos")
    config = carregar()
    _, Sessao = criar_banco(config.banco_url, config.chave_impressao)
    with Sessao() as db:
        if argv[:1] == ["criar-promotoria"] and len(argv) == 2:
            print(f"Promotoria criada: {criar_promotoria(db, argv[1]).nome}")
        elif argv[:1] == ["criar-usuario"] and len(argv) in (4, 5):
            papel = _papel(argv[4] if len(argv) == 5 else "promotor")
            _promotoria(db, argv[3])   # antes de pedir a senha: nome errado não cria nada
            senha = getpass.getpass("Senha (12 caracteres ou mais): ")
            usuario = criar_usuario(db, argv[1], argv[2], senha, promotoria=argv[3], papel=papel,
                                    criar_promotoria=False)
            print(f"Usuário criado em {usuario.espaco.nome}, como {usuario.papel}.")
            print("Quem vê esta mesa agora: " + ", ".join(membros(db, usuario.espaco)))
        elif argv[:1] == ["mover-usuario"] and len(argv) in (3, 4):
            usuario = mover_usuario(db, argv[1], argv[2], argv[3] if len(argv) == 4 else None)
            print(f"{usuario.email} agora está em {usuario.espaco.nome}, como {usuario.papel}.")
            print("Quem vê esta mesa agora: " + ", ".join(membros(db, usuario.espaco)))
        elif argv[:1] == ["desligar-usuario"] and len(argv) == 2:
            desligar_usuario(db, argv[1])
            print("Usuário desligado: não entra mais, e a sessão aberta cai no próximo clique.")
        elif argv[:1] == ["acessos"] and len(argv) == 2:
            espaco = _promotoria(db, argv[1])
            emails = dict(db.execute(select(Usuario.id, Usuario.email)).all())
            for a in servicos.acessos_da_promotoria(db, espaco.id):
                processo = f"processo {a.processo_id}" if a.processo_id else "-"
                print(f"{a.quando:%d/%m/%Y %H:%M}  {emails.get(a.usuario_id, a.usuario_id)}  {a.acao}  {processo}")
        elif argv == ["limpar-autos"]:
            # cartão C1: rodar por agendador (cron ou timer) na hospedagem; o servidor também limpa sozinho
            print(f"Arquivos de autos apagados por prazo: {servicos.apagar_autos_vencidos(db, datetime.now())}")
        elif argv[:1] == ["apagar-processo"] and len(argv) == 3:
            # dado que entrou por engano (guia do ensaio): sai o processo com minuta, autos, rascunho e audiências
            usuario = db.scalar(select(Usuario).where(Usuario.email == argv[1].strip().lower()))
            if usuario is None or not servicos.apagar_processo(db, usuario, argv[2].strip()):
                raise SystemExit("nada apagado: confira o e-mail e o número, escrito como aparece na mesa")
            print("Processo apagado, com minuta, autos, rascunho enviado e audiências.")
        elif argv == ["semente"]:
            senha = semente(db, config)
            print(f"Usuário de demonstração: {EMAIL_DEMO}\nSenha (guarde agora; não é mostrada de novo): {senha}")
        else:
            raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
