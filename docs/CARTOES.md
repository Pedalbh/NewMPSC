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

### C19 · Onde roda o ensaio da Fase 1, e a IA liga nele?
- **Por que é sua:** contrato e dinheiro (hospedagem) e destino novo de dado.
- **Contexto:** o C17 aprovou o piloto. A Fase 1 usa só processos fictícios, mas três promotorias precisam alcançar a aplicação, e hoje ela só roda no computador de quem desenvolve. Dois pontos pesam em qualquer opção:
  - **O servidor guarda dado pessoal real dos participantes:** nome, e-mail, cargo, promotoria, a senha (cifrada) e os endereços de rede nos registros do servidor e do provedor.
  - **A recusa de dado real é parcial.** A aplicação só aceita número de processo claramente fictício. Não examina o texto da minuta e não reconhece nome, documento nem PDF digitalizado: para isso existem o termo do participante e o comando que apaga o processo.
- **Opções:**
  - **A. Servidor pequeno contratado só para o ensaio, sem IA.** Motor de demonstração; nenhum texto sai do servidor. O contrato fica em seu nome, como pessoa, não da instituição. Quem opera (console e banco) é o coordenador, com a conta que você criar.
    **Depois da decisão:** o coordenador prepara a receita de instalação (HTTPS, convite pela linha de comando) com parecer de segurança, e traz em cartão curto dois ou três serviços com preço, país e região, e como cada um apaga cópias e snapshots no fim, para você escolher e contratar.
  - **B. O mesmo servidor, com o relatório por IA ligado sobre autos fictícios.** Os participantes veem o relatório no ensaio. Os dados do processo e o texto de cada página dos autos vão à API do Claude (Anthropic), processados fora do Brasil, pela sua chave pessoal (C8), sem contrato institucional. Um nome real que escape num PDF vai junto. Retenção e país: a conferir nos termos do fornecedor.
    **Depois da decisão:** o mesmo da opção A, mais o motor de IA ligado com a sua chave e o teto de gasto no painel do fornecedor; a conferência dos termos do fornecedor volta a você antes de ligar.
  - **C. Pedir à TI um servidor institucional já para o ensaio.** Demora mais, mas o dado dos participantes fica na instituição e a hospedagem da Fase 2 se adianta.
    **Depois da decisão:** o coordenador escreve os requisitos para a TI; a Fase 1 espera a resposta dela.
  - **D. Sem servidor.** O ensaio acontece em sessões guiadas, com a aplicação no computador de quem conduz, por compartilhamento de tela. Nenhum dado de participante sai desse computador.
    **Depois da decisão:** o coordenador adapta o roteiro para sessão guiada. O portão "cada participante faz o roteiro sem ajuda" fica mais fraco e é reescrito.
  - **E. Outro.** Você escreve o que prefere.
    **Depois da decisão:** o coordenador executa o que você escrever; se mudar o efeito descrito aqui, volta em cartão novo.
- **Recomendo:** A. Começa em dias, não envolve processo real nem IA, e o custo é o de um servidor pequeno por um mês. O preço é guardar, fora da instituição e por um mês, nome e e-mail de até nove pessoas, o que o termo passa a dizer.
- **O que espera:** o começo da Fase 1 com os participantes. Roteiro, guia e termo já estão em `docs/piloto/`.
- **O que você faz:** contratar o serviço escolhido (opções A e B) ou levar o pedido à TI (opção C).

### C20 · Registro de acessos: quem pode ler, e por quanto tempo fica?
- **Por que é sua:** dado e LGPD (prazo de guarda) e regras do projeto.
- **Hoje:** desde a 0.6.0 a aplicação anota quem entrou, abriu, editou, baixou ou enviou cada processo, as tentativas negadas e os atos de quem administra, com data e hora. Não guarda conteúdo nem endereço de rede. Ninguém lê pela tela: só quem opera o servidor, pela linha de comando (hoje, o coordenador; não há hospedagem institucional). As linhas não têm prazo: ficam para sempre, mesmo depois de o processo ou a pessoa sair. O registro diz o que cada pessoa fez e a que horas, então é dado pessoal de quem trabalha, e isso já vale no ensaio da Fase 1.
- **Opções:**
  - **A. O promotor lê o da sua promotoria; guarda de 1 ano.** Uma tela simples, só para o promotor. Ele passa a ver a que horas cada assessor abriu e editou cada processo: é acompanhamento do trabalho de colega, e o termo dos participantes precisa dizer isso. Linhas com mais de um ano são apagadas sozinhas.
    **Depois da decisão:** o coordenador constrói a tela e a limpeza, com teste de isolamento e os três revisores, e põe a leitura e o prazo no termo.
  - **B. Só quem opera o servidor lê; guarda de 1 ano.** Sem tela. O registro serve para apurar incidente, a pedido seu ou do encarregado de dados.
    **Depois da decisão:** o coordenador constrói só a limpeza e escreve quem pode pedir a consulta e como.
  - **C. Leitura por órgão de controle.** O promotor não lê; quem lê é quem a instituição indicar (encarregado de dados, controle interno ou Corregedoria).
    **Depois da decisão:** o coordenador leva a pergunta à pauta da Fase 0 e constrói o acesso quando houver a indicação; até lá vale a opção B.
  - **D. Deixar tudo para o parecer do encarregado.** Fica como está até a Fase 0.
    **Depois da decisão:** nada muda no código; a pergunta entra na pauta do encarregado.
  - **E. Outro.** Você escreve o que prefere.
    **Depois da decisão:** o coordenador executa o que você escrever; se mudar o efeito descrito aqui, volta em cartão novo.
- **Recomendo:** B agora, com a pergunta da opção C levada ao encarregado. O registro ainda é novo e serve para apurar incidente; dar ao promotor a leitura do horário de cada assessor é passo que merece o parecer antes. O prazo de um ano é proposta: não foi conferido na tabela de temporalidade do MPSC nem em ato do CNMP.
- **O que espera:** o texto final do termo dos participantes (já diz que o registro existe). Precisa estar decidido antes do primeiro dado real (Fase 2).

### C21 · O assessor pode pedir o relatório à IA?
- **Por que é sua:** dado e LGPD (quem manda texto de autos para fora) e dinheiro (cada pedido custa).
- **Hoje:** o C18 reservou ao promotor só o que toca o SIG. Pedir o relatório à IA ficou aberto aos dois papéis: o pedido envia o texto dos autos ao fornecedor. Os limites contam por pessoa (20 por hora, 60 por dia), então uma promotoria com um promotor e dois assessores pode mandar o triplo. Hoje só há dados fictícios, e o motor de IA nem liga com dado real.
- **Opções:**
  - **A. Os dois pedem; o limite passa a ser da promotoria.** O assessor prepara a minuta inteira, com o relatório. O volume que sai fica igual ao de uma pessoa só.
    **Depois da decisão:** o coordenador troca os limites por pessoa por limites por promotoria, com teste.
  - **B. Só o promotor pede.** Texto de autos só sai por ato do promotor, como o envio ao SIG.
    **Depois da decisão:** o coordenador restringe o pedido ao promotor (no serviço e na tela) e ajusta o guia.
  - **C. Deixar como está até o contrato da Fase 3.**
    **Depois da decisão:** nada muda; o ponto entra na pauta do contrato e do parecer (C4).
  - **D. Outro.** Você escreve o que prefere.
    **Depois da decisão:** o coordenador executa o que você escrever; se mudar o efeito descrito aqui, volta em cartão novo.
- **Recomendo:** A. O ganho do assessor está em entregar a minuta já com o relatório; o que precisa de trava é o volume, não a pessoa.
- **O que espera:** nada no ensaio. Precisa estar decidido antes da Fase 3.

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
