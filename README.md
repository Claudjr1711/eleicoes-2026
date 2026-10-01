# Eleições 2026 — Da Prática Política

## Publicar no GitHub Pages

1. Crie um repositório público chamado `eleicoes-2026`.
2. Envie o arquivo `index.html` deste pacote para a raiz do repositório.
3. No GitHub, abra **Settings → Pages**.
4. Em **Build and deployment**, selecione **Deploy from a branch**.
5. Escolha a branch `main` e a pasta `/ (root)`.
6. Salve e aguarde a publicação.
7. O GitHub fornecerá um endereço parecido com:
   `https://SEU-USUARIO.github.io/eleicoes-2026/`

## Colocar no Blogger

Abra **Páginas → Nova página**, mude o editor para **HTML** e cole o conteúdo de `blogger-iframe.html`.

Substitua:
`https://SEU-USUARIO.github.io/eleicoes-2026/`

pelo endereço real publicado no GitHub Pages.

## Domínio próprio

Se quiser usar:
`https://eleicoes2026.dapraticapolitica.com.br/`

é possível configurar um domínio personalizado no GitHub Pages e depois criar um registro DNS no provedor do domínio.

## Observação

O painel é uma interface de divulgação e deve ser mantido separado da apuração oficial. Os resultados eleitorais devem ser conferidos no Portal de Resultados do TSE.


## Pesquisas eleitorais — atualização automática

A seção **Pesquisas** não usa mais uma lista fixa no JavaScript. O arquivo `polls.json` é carregado pelo painel. O workflow `.github/workflows/update-polls.yml` roda diariamente e também pode ser executado manualmente em **Actions → Atualizar pesquisas eleitorais → Run workflow**.

Fontes: TSE/PesqEle para registros e metadados; páginas oficiais dos institutos para resultados divulgados. A coleta é conservadora: quando um resultado não puder ser extraído com segurança, o painel mantém o link da fonte oficial em vez de preencher números por estimativa.
