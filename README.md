# Eleições 2026 — Apuração

Projeto limpo para divulgação dos resultados oficiais das Eleições 2026.

Fonte exclusiva: Tribunal Superior Eleitoral (TSE), por meio dos arquivos públicos de divulgação de resultados em JSON.

Não há módulo de pesquisas eleitorais.

A página `index.html` consulta a configuração oficial e os arquivos de resultados diretamente da infraestrutura do TSE. O TSE informa que esses arquivos são atualizados conforme a evolução da totalização e que o ambiente oficial usa `https://resultados.tse.jus.br`. 

Antes da votação, alguns arquivos de produção podem ainda não estar disponíveis. O portal mostra uma mensagem de espera nesses casos.
