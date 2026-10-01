#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Coletor de pesquisas eleitorais 2026.
FONTE DAS PESQUISAS: exclusivamente sites oficiais dos institutos.
O TSE NÃO é consultado para obter resultados de pesquisas.

Saída:
  polls.json                 -> base compacta consumida pelo site
  data/poll_sources.json     -> páginas oficiais encontradas/checadas

A coleta é conservadora: quando não consegue identificar com segurança
candidato + percentual, não inventa o dado e registra a página para revisão.
"""

from __future__ import annotations
import json, re, time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "polls.json"
SOURCES_OUT = ROOT / "data" / "poll_sources.json"

HEADERS = {
    "User-Agent": "Da-Pratica-Politica-Eleicoes-2026/1.0 (+https://claudjr1711.github.io/eleicoes-2026/)"
}
TIMEOUT = 25

SOURCES = [
    {
        "institute": "Datafolha",
        "index": "https://datafolha.folha.uol.com.br/eleicoes/indice-2.shtml",
        "domain": "datafolha.folha.uol.com.br",
        "kind": "datafolha",
    },
    {
        "institute": "Quaest",
        "index": "https://quaest.com.br/categoria/analises-de-pesquisas/",
        "domain": "quaest.com.br",
        "kind": "quaest",
    },
    {
        "institute": "AtlasIntel",
        "index": "https://atlasintel.org/polls/general-release-polls",
        "domain": "atlasintel.org",
        "kind": "atlas",
    },
    {
        "institute": "AtlasIntel",
        "index": "https://atlasintel.org/polls/exclusive-polls",
        "domain": "atlasintel.org",
        "kind": "atlas",
    },
    {
        "institute": "Paraná Pesquisas",
        "index": "https://paranapesquisas.com.br/",
        "domain": "paranapesquisas.com.br",
        "kind": "parana",
    },
]

def get(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text

def soup_text(html: str) -> str:
    s = BeautifulSoup(html, "html.parser")
    for tag in s(["script", "style", "noscript", "svg"]):
        tag.decompose()
    return re.sub(r"\s+", " ", s.get_text(" ", strip=True))

def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def date_from_text(text: str) -> str:
    m = re.search(r"\b(\d{1,2})[./](\d{1,2})[./](2026)\b", text)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    months = {
        "jan":1,"fev":2,"mar":3,"abr":4,"mai":5,"jun":6,
        "jul":7,"ago":8,"set":9,"out":10,"nov":11,"dez":12
    }
    m = re.search(r"\b(\d{1,2})\s*[./]?\s*(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)[a-z]*\.?\s*2026\b", text, re.I)
    if m:
        d, mon = m.groups()
        return f"2026-{months[mon.lower()]:02d}-{int(d):02d}"
    return ""

def extract_field(text: str) -> str:
    patterns = [
        r"realizad[ao]s?\s+(?:entre|nos dias)\s+([0-9]{1,2}\s*(?:a|-)\s*[0-9]{1,2}\s+de\s+[a-zç]+(?:\s+de)?\s+2026)",
        r"entre\s+([0-9]{1,2}\s*(?:e|a|-)\s*[0-9]{1,2}\s+de\s+[a-zç]+(?:\s+de)?\s+2026)",
        r"coleta(?: de dados)?\s*:\s*([0-9/\-]+)"
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m: return clean(m.group(1))
    return ""

def extract_sample(text: str):
    for p in [
        r"([\d\.]+)\s+entrevistas?",
        r"amostra(?: de)?\s+([\d\.]+)",
        r"sample size[:\s]+([\d\.]+)"
    ]:
        m = re.search(p, text, re.I)
        if m:
            return int(m.group(1).replace(".", ""))
    return None

def extract_moe(text: str):
    for p in [
        r"margem(?: de erro)?[^0-9]{0,50}(?:de\s+)?([0-9]+(?:[,.][0-9]+)?)\s*(?:pontos?|%)",
        r"\+/-\s*([0-9]+(?:[,.][0-9]+)?)\s*%"
    ]:
        m = re.search(p, text, re.I)
        if m:
            return float(m.group(1).replace(",", "."))
    return None

def extract_confidence(text: str):
    m = re.search(r"([0-9]{2})%\s*(?:de\s+)?confiança|nível de confiança[^0-9]*([0-9]{2})%", text, re.I)
    if m: return int(next(g for g in m.groups() if g))
    return None

def extract_registration(text: str):
    vals = re.findall(r"\b(?:BR|SP|MG|RJ|BA|PR|RS|PE|CE|DF|GO|PA|MA|SC|ES|PB|RN|AL|SE|PI|MT|MS|RO|AM|AC|AP|RR|TO)-\d{4,6}/2026\b", text, re.I)
    return ", ".join(dict.fromkeys(vals))

# Partidos e siglas ajudam a evitar que percentuais de outros trechos
# (aprovação, rejeição, economia etc.) sejam confundidos com intenção de voto.
PARTY_RE = r"(?:PT|PL|PSD|PSDB|MDB|PP|PDT|PSB|REPUBLICANOS|REPUBLICANOS|NOVO|AVANTE|MISSÃO|MISS[AÃ]O|UP|PCB|PCO|PSTU|PRTB|DEMOCRATA|UNI[AÃ]O|PV|PSOL|REDE|CIDADANIA|SOLIDARIEDADE|AGIR|DC|PRD|PODE|MOBILIZA|PRTB)"

def extract_candidate_values(text: str):
    # Procura padrões como "Lula (PT) tem 40%" ou "Ronaldo Caiado (PSD), com 4%".
    pat = re.compile(
        rf"([A-ZÀ-Ý][A-Za-zÀ-ÿ]+(?:\s+[A-ZÀ-Ý][A-Za-zÀ-ÿ'-]+){{0,4}})\s*\(({PARTY_RE})\)"
        rf".{{0,55}}?\b(\d{{1,2}}(?:[,.]\d+)?)\s*%",
        re.I
    )
    found = []
    seen = set()
    for m in pat.finditer(text):
        name = clean(m.group(1))
        party = m.group(2).upper()
        value = float(m.group(3).replace(",", "."))
        key = (name.lower(), party, value)
        if key not in seen and 0 <= value <= 100:
            seen.add(key)
            found.append({"candidate": name, "party": party, "value": value})
    return found

def split_turns(text: str):
    # Primeiro bloco até a primeira referência clara ao segundo turno.
    markers2 = list(re.finditer(r"\b2[ºo°]\s*turno\b|\bsegundo turno\b", text, re.I))
    first = text[:markers2[0].start()] if markers2 else text
    second = text[markers2[0].start():] if markers2 else ""
    return first, second

def scope_from_url_title(title: str, url: str) -> str:
    x = (title + " " + url).lower()
    states = [
        ("acre","AC"),("alagoas","AL"),("amapá","AP"),("amazonas","AM"),
        ("bahia","BA"),("ceará","CE"),("distrito federal","DF"),
        ("espírito santo","ES"),("goiás","GO"),("maranhão","MA"),
        ("mato grosso","MT"),("mato grosso do sul","MS"),("minas gerais","MG"),
        ("pará","PA"),("paraíba","PB"),("paraná","PR"),("pernambuco","PE"),
        ("piaui","PI"),("piauí","PI"),("rio de janeiro","RJ"),
        ("rio grande do norte","RN"),("rio grande do sul","RS"),
        ("rondônia","RO"),("roraima","RR"),("santa catarina","SC"),
        ("são paulo","SP"),("sergipe","SE"),("tocantins","TO")
    ]
    for name, uf in states:
        if name in x: return uf
    return "Brasil"

def discover_links(index_url: str, domain: str, html: str, limit=25):
    s = BeautifulSoup(html, "html.parser")
    links = []
    for a in s.find_all("a", href=True):
        href = urljoin(index_url, a["href"])
        if urlparse(href).netloc.endswith(domain):
            title = clean(a.get_text(" ", strip=True))
            if href.startswith("http") and href not in {x["url"] for x in links}:
                links.append({"url": href, "title": title})
        if len(links) >= limit:
            break
    return links

def parse_page(inst: str, url: str, anchor_title: str):
    html = get(url)
    text = soup_text(html)
    if "2026" not in text and "2026" not in anchor_title:
        return [], {"url": url, "institute": inst, "status": "ignored", "title": anchor_title}

    title = clean(anchor_title)
    h1 = BeautifulSoup(html, "html.parser").find("h1")
    if h1:
        title = clean(h1.get_text(" ", strip=True)) or title

    # Exige sinais de pesquisa eleitoral para reduzir falsos positivos.
    if not re.search(r"intenção de voto|intencao de voto|eleiç|elei[cç][aã]o|presidenc|governador|senador", text, re.I):
        return [], {"url": url, "institute": inst, "status": "ignored", "title": title}

    date = date_from_text(title + " " + text[:2500])
    field = extract_field(text)
    sample = extract_sample(text)
    moe = extract_moe(text)
    conf = extract_confidence(text)
    reg = extract_registration(text)
    scope = scope_from_url_title(title, url)

    first, second = split_turns(text)
    records = []

    def make_record(turn, block):
        vals = extract_candidate_values(block)
        # Conservador: só publica se houver pelo menos dois candidatos.
        if len(vals) < 2:
            return None
        # Limita a candidatos mais diretamente associados ao cenário inicial.
        vals = vals[:15]
        return {
            "i": inst,
            "date": date,
            "field": field,
            "scope": scope,
            "cargo": "presidente",
            "turn": turn,
            "sample": sample,
            "moe": moe,
            "confidence": conf,
            "reg": reg,
            "results": vals,
            "sourceUrl": url,
            "sourceType": "site_oficial_instituto",
            "title": title
        }

    r1 = make_record(1, first)
    if r1: records.append(r1)
    r2 = make_record(2, second)
    if r2: records.append(r2)

    status = "ok" if records else "manual_review"
    return records, {
        "url": url, "institute": inst, "status": status,
        "title": title, "date": date, "records": len(records)
    }

def dedupe(records):
    out, seen = [], set()
    for r in records:
        key = (
            r["i"], r.get("date"), r.get("scope"), r.get("turn"),
            r["sourceUrl"], tuple((x["candidate"], x["value"]) for x in r["results"][:8])
        )
        if key not in seen:
            seen.add(key); out.append(r)
    out.sort(key=lambda x: (x.get("date",""), x["i"]), reverse=True)
    return out

def main():
    records = []
    source_log = []
    for src in SOURCES:
        try:
            html = get(src["index"])
            links = discover_links(src["index"], src["domain"], html)
            # A própria página de índice também pode conter uma pesquisa.
            links.insert(0, {"url": src["index"], "title": src["institute"]})
            for link in links[:26]:
                try:
                    recs, log = parse_page(src["institute"], link["url"], link["title"])
                    records.extend(recs)
                    source_log.append(log)
                    time.sleep(0.15)
                except Exception as e:
                    source_log.append({
                        "url": link["url"], "institute": src["institute"],
                        "status": "error", "error": str(e)[:240]
                    })
        except Exception as e:
            source_log.append({
                "url": src["index"], "institute": src["institute"],
                "status": "error", "error": str(e)[:240]
            })

    records = dedupe(records)
    # Mantém somente pesquisas de 2026 e no máximo 120 registros.
    records = [r for r in records if r.get("date","").startswith("2026-")][:120]

    OUT.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    SOURCES_OUT.write_text(json.dumps({
        "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "source_policy": "Somente sites oficiais dos institutos. TSE não é fonte de resultados de pesquisas.",
        "sources": source_log
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{len(records)} registros gravados em {OUT}")
    print(f"{len(source_log)} páginas verificadas; log em {SOURCES_OUT}")

if __name__ == "__main__":
    main()
