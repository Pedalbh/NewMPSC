# Central de cartões

Cada decisão que é do titular vira um cartão aqui. O resto o coordenador decide e segue, deixando registrado no PR. A régua está no `CLAUDE.md`.

Como responder: diga na conversa o número do cartão e a opção (por exemplo, "C1: A"). A resposta já é a ordem de execução: o coordenador registra a decisão aqui, com a data, e executa na hora o que está em **Depois da decisão** da opção escolhida, sem nova pergunta. O caminho é o de sempre: ramo, PR com testes, revisores do nível da tarefa, CI verde, merge.

O coordenador só volta a perguntar se, durante a execução, aparecer fato novo que mude o efeito descrito na opção (isso vira cartão novo, e o resto da execução segue). Passo que só o titular pode dar (chave de API, contrato, conversa institucional) fica listado em **O que você faz**; o coordenador executa tudo o que não depende dele.

## Estrutura de cada cartão
- **Título:** a pergunta numa frase.
- **Por que é sua:** qual item da régua do `CLAUDE.md` o traz para cá.
- **Hoje** ou **Contexto:** como está agora e o que se sabe.
- **Opções:** cada uma com o efeito e, logo abaixo, **Depois da decisão:** o que o coordenador executa sozinho se ela for escolhida.
- **Recomendo:** a opção e o porquê, numa linha.
- **O que espera:** o que fica parado sem resposta.
- **O que você faz** (só quando há): passo que só o titular pode dar.

## Abertos

### C19 · Onde roda o ensaio da Fase 1, e a IA liga nele?
- **Por que é sua:** contrato e dinheiro (hospedagem) e destino novo de dado, ainda que fictício.
- **Contexto:** o C17 aprovou o piloto. A Fase 1 usa só dados fictícios, mas três promotorias precisam alcançar a aplicação, e hoje ela só roda no computador de quem desenvolve. A aplicação já recusa número de processo real na planilha, na colagem, na pauta, nos autos, no pedido à IA e no envio. Não reconhece nome nem documento: para isso existe o termo do participante.
- **Opções:**
  - **A. Servidor pequeno contratado só para o ensaio, sem IA.** Dados fictícios, motor de demonstração, apagado ao fim da fase.
    **Depois da decisão:** o coordenador prepara a receita de instalação (HTTPS, convite pela linha de comando, banco apagado no fim) com parecer de segurança, e traz em cartão curto dois ou três serviços com preço e país, para você escolher e contratar.
  - **B. O mesmo servidor, com o relatório por IA ligado sobre autos fictícios.** Os participantes veem o relatório no ensaio. O texto dos autos fictícios vai à API do Claude.
    **Depois da decisão:** o mesmo da opção A, mais o motor de IA ligado com a sua chave (C8) e o teto de gasto no painel do fornecedor.
  - **C. Pedir à TI um servidor institucional já para o ensaio.** Demora mais, mas adianta a hospedagem da Fase 2.
    **Depois da decisão:** o coordenador escreve os requisitos para a TI; a Fase 1 espera a resposta dela.
  - **D. Sem servidor.** O ensaio acontece em sessões guiadas, com a aplicação no computador de quem conduz, por compartilhamento de tela.
    **Depois da decisão:** o coordenador adapta o roteiro para sessão guiada. O portão "cada participante faz o roteiro sem ajuda" fica mais fraco e é reescrito.
- **Recomendo:** A. Começa em dias, não envolve dado real nem IA, e o custo é o de um servidor pequeno por um mês.
- **O que espera:** o começo da Fase 1 com os participantes. Roteiro, guia e termo já estão em `docs/piloto/`.
- **O que você faz:** contratar o serviço escolhido (opções A e B) ou levar o pedido à TI (opção C).

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
| C18 · Promotor e assessor da mesma promotoria veem os mesmos processos | A: espaço da promotoria; só o promotor envia ao SIG | 16/11/2026 | em construção, em PR próprio com os três revisores; o limite 3 do `CLAUDE.md` muda nesse PR |
