# Pedido à TI: integração do NewMPSC com o SIG

Rascunho para o titular levar à conversa com a TI (cartão C16, decidido em 16/11/2026). Só o titular apresenta; o coordenador ajusta o texto depois da conversa.

## O que é o NewMPSC
Uma aplicação web em que o promotor vê a fila de processos por prioridade, prepara a minuta num lugar só e acompanha a pauta de audiências. Hoje a fila entra por planilha exportada do SIG e a peça sai por arquivo. O protótipo, só com dados fictícios, está em `README.md` ("Ver o protótipo do envelope").

O NewMPSC não substitui o SIG. Não assina e não protocola.

## O que se pede
Duas operações, nesta ordem. A primeira já resolve metade do trabalho manual e pode vir sozinha.

| Operação | O que faz | O que não faz |
| --- | --- | --- |
| 1. Ler a fila | Devolve os processos que estão com a pessoa: os mesmos campos da planilha que o SIG já exporta | Não lê autos nem peças |
| 2. Depositar rascunho | Deixa, num processo da fila da pessoa, uma minuta como rascunho, sem assinatura | Não assina, não protocola, não movimenta o processo |

## Condições que o próprio projeto impõe
1. **Credencial da própria pessoa.** A integração age em nome de quem está usando, com autorização delegada por ela. Não se pede conta de serviço que enxergue várias promotorias.
2. **Registro de cada depósito.** O NewMPSC guarda quem depositou, quando e em qual processo, num registro que só acrescenta. Se a TI quiser, o mesmo registro pode ser enviado a ela.
3. **Revogação pela TI.** A TI pode cortar o acesso da aplicação ou de uma pessoa a qualquer momento, sem depender do projeto.
4. **Só por ato do usuário.** O depósito acontece quando a pessoa clica em enviar, processo a processo. Nada é enviado sozinho nem em lote.

## Detalhes técnicos que ajudam
- **Texto formatado.** Aceitar a minuta com formatação (o SIG define o formato), para a peça chegar no padrão do Manual de Redação.
- **Repetição sem duplicar.** Enviar de novo para o mesmo processo troca o rascunho, em vez de criar outro. A aplicação chama o SIG antes de gravar o recibo; se a gravação falhar, o reenvio não pode deixar dois rascunhos.
- **Desfazer.** Poder retirar o rascunho depositado, enquanto não foi assinado.
- **Recibo.** Cada depósito devolve um identificador, que o NewMPSC mostra à pessoa.
- **Ambiente de homologação.** Um SIG de teste, com dados fictícios, para desenvolver sem tocar a produção.

## Perguntas para a TI
1. O SIG tem interface de integração hoje, ou há previsão?
2. Qual forma de autenticação delegada a TI aceita?
3. Em que formato o SIG recebe texto de peça?
4. Existe ambiente de homologação com dados fictícios?
5. Que requisitos de segurança e de hospedagem a aplicação precisa cumprir para ser autorizada?

## Enquanto a integração não existe
O piloto (`docs/PILOTO.md`) funciona sem ela: a fila entra pela planilha e a peça sai por arquivo. Nada escreve no SIG.
