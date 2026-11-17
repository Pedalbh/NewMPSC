# Central de cartões

Cada decisão que é do titular vira um cartão aqui. O resto o coordenador decide e segue, deixando registrado no PR. A régua está no `CLAUDE.md`.

Como responder: na página de cartões, ou na conversa, com o número do cartão e a opção (por exemplo, "C1: A"). A resposta já é a ordem de execução: o coordenador registra a decisão aqui, com a data, e executa na hora o que está em **Depois da decisão** da opção escolhida, sem nova pergunta. O caminho é o de sempre: ramo, PR com testes, revisores do nível da tarefa, CI verde, merge.

O coordenador só volta a perguntar se, durante a execução, aparecer fato novo que mude o efeito descrito na opção (isso vira cartão novo, e o resto da execução segue). Passo que só o titular pode dar (chave de API, contrato, conversa institucional) fica listado em **O que você faz**; o coordenador executa tudo o que não depende dele.

## Estrutura de cada cartão
- **Título:** a pergunta numa frase.
- **Por que é sua:** qual item da régua do `CLAUDE.md` o traz para cá.
- **Hoje** ou **Contexto:** como está agora e o que se sabe.
- **Opções:** cada uma com o efeito e, logo abaixo, **Depois da decisão:** o que o coordenador executa sozinho se ela for escolhida. A última é sempre **Outro**: o titular escreve o que prefere.
- **Recomendo:** a opção e o porquê, numa linha.
- **O que espera:** o que fica parado sem resposta.
- **O que você faz** (só quando há): passo que só o titular pode dar.

## Abertos

### C22 · Com autos reais, onde o sistema roda?
- **Por que é sua:** dado real e hospedagem. O limite 1 diz que dado real só entra depois de hospedagem e contrato institucionais.
- **Contexto:** no C19 você respondeu que a IA fica como porta para depois e que os autos poderão ser reais. A aplicação já funciona sem IA (é o padrão) e com o SIG por planilha. Falta decidir onde ela roda quando o dado é real. Hoje o código recusa número de processo real em servidor de ensaio, e essa trava só sai por configuração de quem instala.
- **Opções:**
  - **A. Só em servidor da instituição.** Você leva à TI o pedido de servidor; até lá, o ensaio segue com dados fictícios, em sessões guiadas.
    **Depois da decisão:** o coordenador escreve os requisitos de hospedagem para a TI e segue nos itens de segurança que faltam antes do primeiro dado real (lista em `docs/PILOTO.md`).
  - **B. No computador de trabalho de cada promotoria, sem servidor.** O dado real não sai da máquina institucional. Promotor e assessor só compartilham a mesa se usarem a mesma máquina, e não há cópia de segurança central.
    **Depois da decisão:** o coordenador prepara um instalador simples e o guia, com parecer de segurança, e traz em cartão o que muda no plano do piloto.
  - **C. Em servidor contratado por você, já com dado real.** Mais rápido, mas põe dado de processo fora da instituição, sem contrato institucional nem parecer do encarregado. Exige mudar o limite 1.
    **Depois da decisão:** o coordenador muda o limite 1 no `CLAUDE.md` e traz em cartão os serviços, com preço, país e contrato.
  - **D. Outro.** Você escreve o que prefere.
    **Depois da decisão:** o coordenador executa o que você escrever; se mudar o efeito descrito aqui, volta em cartão novo.
- **Recomendo:** A. É o único caminho que serve a várias promotorias sem tirar dado de processo da instituição. A opção B serve de ponte se a TI demorar.
- **O que espera:** qualquer uso com autos reais. O desenvolvimento segue com dados fictícios.

## Decididos

Cada linha diz também como ficou a execução: o PR que a cumpriu, "nada a executar" ou o que ainda falta.

| Cartão | Decisão | Quando | Execução |
| --- | --- | --- | --- |
| Motor de IA | API do Claude direta | 13/11/2026 | PR #5 |
| Fonte de jurisprudência | JuriBase | 13/11/2026 | falta o acesso da aplicação (C6) |
| Merge | Com os revisores aprovando e o CI verde, o coordenador faz o merge sem perguntar | 13/11/2026 | nada a executar |
| Onde vivem os cartões | Neste arquivo; o coordenador traz cada cartão aberto na conversa | 13/11/2026 | PR #4 |
| Execução depois da decisão | A resposta ao cartão já é a ordem: o coordenador executa sem nova pergunta | 14/11/2026 | PR #6 |
| C1 · Por quanto tempo o texto dos autos fica guardado | A: apaga sozinho o texto dos autos 30 dias depois de o processo ser concluído | 14/11/2026 | PR #8 |
| C2 · A impressão digital do arquivo original continua guardada | B: impressão do arquivo com chave do servidor | 14/11/2026 | PR #8 |
| C3 · Quanto texto de autos cada usuário pode guardar | A: números provisórios mantidos; revisão com autos reais | 14/11/2026 | nada a executar agora |
| C4 · O que precisa existir antes de texto real ir para a API do Claude | A, com observação: etapa 2 só com dados fictícios; dado real barrado até o contrato; resumo para TI e encarregado | 14/11/2026 | resumo em `docs/RESUMO-C4.md`; a observação virou o C10 |
| C5 · Qual fonte de legislação vigente a aplicação consulta | A: na etapa 3 só jurisprudência é conferida; citação de lei sai "não conferida" | 14/11/2026 | entra na etapa 3, com a avaliação de Planalto e LexML trazida em cartão |
| C6 · Como a aplicação passa a acessar o JuriBase | B: o coordenador levanta o que o JuriBase publica | 14/11/2026 | levantamento feito; virou o C12 |
| C7 · O que o motor de IA escreve antes de existir a verificação de fontes | A: o motor escreve só o relatório até existir a verificação de fontes | 14/11/2026 | nada a executar: já está assim |
| C8 · Qual modelo o motor usa, e com que teto de gasto | A: modelo padrão mantido; custo medido nos primeiros testes | 14/11/2026 | no primeiro teste com a API, que espera a chave |
| C9 · O que fazer quando o modelo declina um pedido, e onde ele processa | B: troca de modelo só para uma lista aprovada | 14/11/2026 | PR #11, com a reserva escolhida no C14 |
| C10 · Os "pequenos testes sem contrato" usam dado real | A: testes com autos fictícios feitos para parecer reais | 14/11/2026 | autos em `dados_ficticios/teste-api/`, neste PR |
| C11 · Para quais modelos o pedido pode passar quando o primeiro declina | A, com observação: só `claude-sonnet-5-5`; pediu as opções de lista | 14/11/2026 | a API não aceita esse modelo como reserva; virou o C14 |
| C12 · Em que condições a aplicação usa o JuriBase | C, com observação: procurar outra fonte de jurisprudência | 14/11/2026 | pesquisa feita; virou o C15 |
| C13 · Por quanto tempo fica a minuta escrita pela IA a partir dos autos | A: a minuta fica | 14/11/2026 | nada a executar |
| C14 · Para qual modelo o pedido passa quando o modelo atual declina | A: só `claude-opus-5`, pela troca do próprio serviço | 14/11/2026 | PR #11; falta confirmar com a chave (C8) que a API aceita essa reserva |
| C15 · De onde a aplicação tira a jurisprudência, no lugar do JuriBase | A: base própria com os dados abertos do STJ | 14/11/2026 | avaliação dos arquivos em curso; volta como cartão com o plano da base |
| C16 · Com integração oficial, o NewMPSC pode deixar a minuta no SIG como rascunho | A: sim, só rascunho, por ato do usuário, pela integração oficial | 16/11/2026 | limite 2 ajustado no `CLAUDE.md`; pedido em `docs/PEDIDO-TI.md`, para o titular levar à TI |
| C17 · O piloto: quais promotorias, e quando o plano vai à Administração | A: plano aprovado com três promotorias | 16/11/2026 | roteiro, guia e termo em `docs/piloto/`; recusa de número real na planilha, na colagem e na pauta; servidor de ensaio virou o C19; itens da Fase 2 em construção, a começar pelo espaço da promotoria |
| C18 · Promotor e assessor da mesma promotoria veem os mesmos processos | A: espaço da promotoria; só o promotor envia ao SIG | 16/11/2026 | feito na 0.6.0: espaço, papéis, registro de acessos, regra de saída e passagem do que era de cada conta; limite 3 ajustado no `CLAUDE.md`. Quem lê o registro e por quanto tempo fica virou o C20; se o assessor pede relatório à IA virou o C21 |
| C19 · Onde roda o ensaio da Fase 1, e a IA liga nele | Outro: "a utilização de IA seja uma porta a ser utilizada no futuro (provavelmente via API). Os autos poderão ser reais, não apenas fictícios. O ideal é ter um sistema programado, escalável, que consiga fazer esse envelopamento do SIG" | 17/11/2026 | sem IA por ora: já é o padrão, e o motor fica atrás da porta de `app/portas.py`; onde o sistema roda com autos reais muda o efeito do cartão e virou o C22 |
| C20 · Registro de acessos: quem pode ler, e por quanto tempo fica | A, com observação: o promotor lê o da sua promotoria; guarda de 1 ano; sem acréscimo no termo ("tudo será institucional no final") | 17/11/2026 | feito na 0.7.0: tela "Registro" e limpeza por prazo |
| C21 · O assessor pode pedir o relatório à IA | A, com observação: os dois pedem; limite da promotoria; "isso é para o futuro" | 17/11/2026 | feito na 0.7.0: o limite de pedidos passou a contar por promotoria |
