import csv
import io
import json
import os
import re
import zipfile
from datetime import datetime, timezone
from urllib.request import Request, urlopen


TSE_API = (
    "https://dadosabertos.tse.jus.br/api/3/action/"
    "package_show?id=pesquisas-eleitorais-2026"
)

OUTPUT_POLLS = "polls.json"
OUTPUT_TSE = "data/tse_pesquisas.json"


def baixar(url):
    req = Request(
        url,
        headers={
            "User-Agent": "Da-Pratica-Politica-Eleicoes-2026/1.0"
        },
    )
    with urlopen(req, timeout=120) as response:
        return response.read()


def normalizar(texto):
    if texto is None:
        return ""

    texto = str(texto).strip().lower()

    substituicoes = {
        "á": "a",
        "à": "a",
        "ã": "a",
        "â": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
    }

    for antigo, novo in substituicoes.items():
        texto = texto.replace(antigo, novo)

    return re.sub(r"\s+", " ", texto)


def encontrar_recurso(recursos):
    candidatos = []

    for recurso in recursos:
        nome = normalizar(recurso.get("name", ""))
        formato = normalizar(recurso.get("format", ""))

        if "pesquisas eleitorais" in nome:
            candidatos.append(recurso)

        elif formato == "csv":
            candidatos.append(recurso)

        elif "zip" in formato:
            candidatos.append(recurso)

    if not candidatos:
        raise RuntimeError(
            "Não foi encontrado o recurso de pesquisas eleitorais no TSE."
        )

    return candidatos[0]


def ler_csv_do_conteudo(conteudo):
    textos = []

    for encoding in ("utf-8-sig", "latin-1", "cp1252"):
        try:
            textos.append(conteudo.decode(encoding))
            break
        except UnicodeDecodeError:
            continue

    if not textos:
        raise RuntimeError("Não foi possível decodificar o arquivo do TSE.")

    texto = textos[0]

    primeira_linha = texto.splitlines()[0] if texto.splitlines() else ""

    if primeira_linha.count(";") >= primeira_linha.count(","):
        delimitador = ";"
    else:
        delimitador = ","

    leitor = csv.DictReader(
        io.StringIO(texto),
        delimiter=delimitador,
    )

    registros = []

    for linha in leitor:
        registro = {}

        for chave, valor in linha.items():
            if chave is None:
                continue

            chave = str(chave).strip()
            valor = "" if valor is None else str(valor).strip()

            registro[chave] = valor

        if any(valor for valor in registro.values()):
            registros.append(registro)

    return registros


def extrair_registros(conteudo):
    # O TSE pode disponibilizar o recurso como ZIP.
    if conteudo[:2] == b"PK":
        registros = []

        with zipfile.ZipFile(io.BytesIO(conteudo)) as arquivo_zip:
            nomes = arquivo_zip.namelist()

            csvs = [
                nome
                for nome in nomes
                if nome.lower().endswith(".csv")
            ]

            for nome in csvs:
                dados = arquivo_zip.read(nome)

                try:
                    registros.extend(ler_csv_do_conteudo(dados))
                except Exception as erro:
                    print(
                        f"Aviso: não foi possível ler {nome}: {erro}"
                    )

        return registros

    return ler_csv_do_conteudo(conteudo)


def obter_dados_tse():
    resposta = json.loads(baixar(TSE_API).decode("utf-8"))

    if not resposta.get("success"):
        raise RuntimeError(
            "A API de Dados Abertos do TSE não retornou sucesso."
        )

    recursos = resposta["result"]["resources"]

    recurso = encontrar_recurso(recursos)

    print("Recurso TSE encontrado:")
    print(recurso.get("name"))
    print(recurso.get("url"))

    conteudo = baixar(recurso["url"])

    registros = extrair_registros(conteudo)

    return registros, recurso


def procurar_valor(registro, palavras):
    for chave, valor in registro.items():
        chave_norm = normalizar(chave)

        for palavra in palavras:
            if palavra in chave_norm:
                return valor

    return ""


def transformar(registros, recurso):
    pesquisas = []

    for registro in registros:
        numero = procurar_valor(
            registro,
            [
                "numero",
                "registro",
                "pesquisa",
            ],
        )

        instituto = procurar_valor(
            registro,
            [
                "instituto",
                "empresa",
            ],
        )

        contratante = procurar_valor(
            registro,
            [
                "contratante",
            ],
        )

        cargo = procurar_valor(
            registro,
            [
                "cargo",
                "eleicao",
            ],
        )

        uf = procurar_valor(
            registro,
            [
                "uf",
                "estado",
            ],
        )

        data_registro = procurar_valor(
            registro,
            [
                "data registro",
                "data de registro",
                "registro",
            ],
        )

        data_inicio = procurar_valor(
            registro,
            [
                "inicio",
                "data inicio",
                "periodo inicial",
            ],
        )

        data_fim = procurar_valor(
            registro,
            [
                "fim",
                "data fim",
                "periodo final",
            ],
        )

        amostra = procurar_valor(
            registro,
            [
                "amostra",
                "entrevistas",
            ],
        )

        margem = procurar_valor(
            registro,
            [
                "margem",
            ],
        )

        confianca = procurar_valor(
            registro,
            [
                "confianca",
                "confiança",
            ],
        )

        pesquisa = {
            "registro_tse": numero,
            "instituto": instituto,
            "contratante": contratante,
            "cargo": cargo,
            "uf": uf,
            "data_registro": data_registro,
            "inicio_campo": data_inicio,
            "fim_campo": data_fim,
            "amostra": amostra,
            "margem_erro": margem,
            "nivel_confianca": confianca,

            # O TSE registra a pesquisa,
            # mas não substitui a publicação do resultado
            # pelo instituto responsável.
            "resultado_publicado": False,
            "resultados": [],

            "fonte": "TSE / PesqEle",
            "fonte_url": (
                "https://www.tse.jus.br/"
                "eleicoes/pesquisas-eleitorais"
            ),

            "dados_brutos": registro,
        }

        pesquisas.append(pesquisa)

    return pesquisas


def main():
    os.makedirs("data", exist_ok=True)

    print("Consultando dados oficiais do TSE...")

    registros, recurso = obter_dados_tse()

    print(f"Registros encontrados: {len(registros)}")

    pesquisas = transformar(registros, recurso)

    agora = datetime.now(timezone.utc).isoformat()

    documento_tse = {
        "fonte": "TSE / PesqEle",
        "ano": 2026,
        "atualizado_em": agora,
        "frequencia": "diaria",
        "recurso_tse": recurso.get("url"),
        "total_registros": len(pesquisas),
        "pesquisas": pesquisas,
    }

    with open(
        OUTPUT_TSE,
        "w",
        encoding="utf-8",
    ) as arquivo:
        json.dump(
            documento_tse,
            arquivo,
            ensure_ascii=False,
            indent=2,
        )

    # O arquivo consumido pelo site.
    documento_site = {
        "atualizado_em": agora,
        "fonte_registros": "TSE / PesqEle",
        "observacao": (
            "Os registros são obtidos do TSE. "
            "Percentuais de intenção de voto devem ser "
            "confirmados na publicação oficial do instituto."
        ),
        "pesquisas": pesquisas,
    }

    with open(
        OUTPUT_POLLS,
        "w",
        encoding="utf-8",
    ) as arquivo:
        json.dump(
            documento_site,
            arquivo,
            ensure_ascii=False,
            indent=2,
        )

    print("Base atualizada com sucesso.")
    print(f"Arquivo: {OUTPUT_POLLS}")
    print(f"Arquivo: {OUTPUT_TSE}")


if __name__ == "__main__":
    main()
