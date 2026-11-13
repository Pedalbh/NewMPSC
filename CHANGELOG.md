# Registro de mudanças

Formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versões em [SemVer](https://semver.org/lang/pt-BR/).

## [0.2.0] - 2026-11-13

### Adicionado
- Autos em PDF: na tela do processo, o PDF é enviado e lido página a página. Só o texto fica guardado; o arquivo, não.
- O resultado de cada envio aparece dentro do cartão dos autos. Página sem texto (digitalizada) e arquivo que não cita o número do processo ficam marcados na lista.
- Arquivo com senha para abrir, danificado, com mais de 50 MB, de 2.000 páginas ou com texto demais é recusado com orientação. PDF que só tem restrição de impressão é lido.
- Em servidor de dados fictícios, PDF com número de processo de dígito verificador válido não entra. É um alerta, não uma garantia: não enxerga página digitalizada, nomes nem CPF.

### Segurança
- O PDF é aberto num processo à parte, sem os segredos da aplicação, com teto de tempo, de memória e de processador. Em produção, não lê se o sistema não aplicar os tetos.
- Uma leitura por vez por usuário e duas no servidor; quem não acha vaga é avisado na hora, sem fila. A conexão do banco é devolvida durante a leitura.
- Cota de texto de autos por usuário. Texto removido é apagado também do arquivo do banco (SQLite).
- Teto para o tamanho de toda requisição: 60 MB para quem entrou, 64 KB para quem não entrou.
- FastAPI, Starlette, python-multipart e Jinja2 atualizados para versões sem falha conhecida no envio de arquivo.

### Corrigido
- A coluna lateral da tela do processo rola sozinha quando é mais alta que a janela; o foco do teclado na área de soltar arquivo fica visível.

## [0.1.0] - 2026-11-13

### Adicionado
- Login por convite, com sessão, proteção contra CSRF e limite de tentativas.
- Mesa de processos: importação da planilha do SIG ou colagem de números; fila por prioridade (réu preso, vista urgente, intimação).
- Minuta pronta a um clique, editável numa folha no padrão do Manual de Redação do MPSC, com salvamento automático, exportação .docx e cópia do texto.
- Pauta de audiências com ficha.
- Portas de troca para a IA (motor de demonstração) e para o SIG (planilha).
