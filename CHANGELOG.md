# Registro de mudanças

Formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versões em [SemVer](https://semver.org/lang/pt-BR/).

## [0.2.0] - 2026-11-13

### Adicionado
- Autos em PDF: na tela do processo, o PDF é enviado e lido página a página. Só o texto fica guardado; o arquivo, não.
- O PDF é aberto num processo à parte, com teto de tempo e de memória. Arquivo com senha, danificado, com mais de 50 MB ou de 2.000 páginas é recusado com orientação.
- Servidor de dados fictícios recusa PDF com número de processo real (dígito verificador válido).
- Aviso de página digitalizada (sem texto) e de arquivo que não cita o número do processo.

### Segurança
- Teto para o tamanho de toda requisição: 60 MB para quem entrou, 64 KB para quem não entrou.

## [0.1.0] - 2026-11-13

### Adicionado
- Login por convite, com sessão, proteção contra CSRF e limite de tentativas.
- Mesa de processos: importação da planilha do SIG ou colagem de números; fila por prioridade (réu preso, vista urgente, intimação).
- Minuta pronta a um clique, editável numa folha no padrão do Manual de Redação do MPSC, com salvamento automático, exportação .docx e cópia do texto.
- Pauta de audiências com ficha.
- Portas de troca para a IA (motor de demonstração) e para o SIG (planilha).
