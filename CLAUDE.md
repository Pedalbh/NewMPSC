# NewMPSC: regras do repositório

Aplicação web do promotor (processos, minutas, audiências). Projeto **separado do Gabinete**: nada aqui altera aquele repositório; o que vem de lá entra por cópia registrada em `app/nucleo/ORIGEM.md`.

## Limites
1. **Só dados fictícios** no repositório, nos testes e no servidor de teste: número de processo com dígito verificador inválido (`-00`), nomes genéricos. Dado real só depois de hospedagem e contrato institucionais (decisão do titular).
2. **Humano no fim da linha:** a aplicação sugere; quem decide, assina e protocola é o usuário. Nada aqui escreve no SIG nem no eproc.
3. **Cada usuário vê só o que é seu.** Toda consulta filtra pelo usuário; mudança nisso exige teste de isolamento.
4. **Nenhum segredo no código.** Sem cadastro aberto: usuário entra por convite (`app.cli`).
5. Conteúdo jurídico gerado por IA só entra com verificação em fonte oficial; o motor de demonstração não traz conteúdo jurídico.

## Como se trabalha
- `main` é a versão estável. Toda mudança: ramo → PR com testes → CI verde → merge.
- `ruff check .` e `python -m pytest` verdes antes de qualquer PR; tela nova ou alterada entra na jornada de `testes/test_navegador.py`.
- Defeito achado em uso vira teste no mesmo PR da correção.
- Mudança visível sobe a versão (`app/__init__.py`, `pyproject.toml`) e ganha linha no `CHANGELOG.md`.
- Lógica em Python no servidor; JavaScript só na casca (`app/static/app.js`). Sem script nem estilo embutido no HTML (a política de conteúdo barra).
- IA e SIG só pelas portas de `app/portas.py`.
- Visual só pelos tokens de `app/static/app.css`. Textos de tela curtos, em linguagem simples.

## Equipe de agentes (`.claude/agents/`)
A sessão principal coordena e constrói. Quem faz não confere: a revisão é de um agente que não viu a construção.

| Agente | Quando chamar |
| --- | --- |
| `revisor-qualidade` | antes do merge de toda mudança média ou grande |
| `designer-ux` | toda mudança de tela e todo fluxo novo; olha os prints reais e conta os cliques |
| `seguranca-lgpd` | login, permissões, envio de arquivo, rede, dependência, hospedagem ou destino novo de dado |

Nível da tarefa, definido no início:
- **Simples** (texto de tela, ajuste pequeno): construir, testes verdes, merge.
- **Média** (função nova em área existente): testes primeiro, construir, `revisor-qualidade`; `designer-ux` se houver tela.
- **Grande ou sensível** (arquitetura, IA, dado, hospedagem): plano curto escrito no PR antes do código, depois os três revisores.

Os pareceres vão como comentário no PR. Defeito apontado é corrigido pela sessão principal e volta ao mesmo revisor. Agente novo só entra se um defeito real mostrar que falta um papel.
