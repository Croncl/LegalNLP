# ────────────────────────────────────────────────────────────────────────────────────────────────
# O QUE FAZ: Grava o módulo de apoio rag_cgu_pipeline.py no ambiente do Colab. Ele reúne o que o
#           curso não traz pronto: (1) extração e limpeza de PDF com PyMuPDF (cabeçalho/rodapé,
#           sumário, notas de rodapé, hífens, caracteres de controle, ligaduras); (2)
#           segmentação por estilo de fonte em seções com trilha hierárquica e metadados
#           (build_sections); (3) detecção de provedores de LLM, escolha automática de modelo e
#           classificação de erros de cota/chave (candidates, check_providers, _classify).
# POR QUÊ : Os PDFs da CGU têm cabeçalhos repetidos, sumário com pontilhado, notas de rodapé e
#           palavras partidas por hífen suave; o loader do curso (PDFPlumberLoader) devolve esse
#           ruído. O módulo também isola a lógica de provedores para o FallbackLLM do notebook
#           usar.
# AÇÃO    : Nenhuma: só rodar. O restante do notebook importa este módulo (import
#           rag_cgu_pipeline as rag). Se editar o código abaixo, rode a célula de novo e, na
#           célula de imports, o módulo é recarregado.
# ────────────────────────────────────────────────────────────────────────────────────────────────
#!/usr/bin/env python3
"""
rag_cgu_pipeline.py - PDFs (URL ou arquivo) -> chunks estruturados -> SQLite (FTS5 + embeddings)

Etapas (todas incrementais e idempotentes):
  ingest   baixa/le PDFs, extrai texto (PyMuPDF), segmenta por estrutura e grava no banco
  enrich   (opcional) resumo, palavras-chave, perguntas e contexto por chunk (LLM com fallback entre provedores, ou heuristica)
  providers  testa cada chave/provedor configurado (OK, sem saldo, invalida...)
  models   lista os modelos que cada chave enxerga (para escolher o nome exato)
  embed    (opcional) gera embeddings multilingues dos chunks ainda sem vetor
  search   busca hibrida (BM25 + vetorial, fusao RRF)
  stats    resumo do banco
  qualidade  relatório de limpeza: ruído residual, tamanho dos chunks, cobertura de páginas e metadados
  export   exporta JSONL para outro vetor-DB (Chroma, pgvector, Qdrant...)

Uso rapido:
  pip install pymupdf requests sentence-transformers numpy
  python rag_cgu_pipeline.py ingest --urls fontes.txt --enrich llm --embed
  python rag_cgu_pipeline.py search "competencia para apurar servidor cedido"

Novos links depois? Basta acrescentar em fontes.txt e rodar 'ingest' de novo: PDFs ja
processados (mesmo SHA-256) sao ignorados; PDFs alterados sao reprocessados reaproveitando
enriquecimento/embeddings dos trechos cujo texto nao mudou.
"""
import argparse, hashlib, json, os, re, sqlite3, sys, time, unicodedata
from collections import Counter
from pathlib import Path

DB_PATH = os.getenv("RAG_DB", "rag_cgu.db")
EMB_MODEL = os.getenv("RAG_EMB_MODEL", "intfloat/multilingual-e5-small")
MAX_CHARS, OVERLAP = 3500, 400

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS documents(
  id INTEGER PRIMARY KEY, url TEXT UNIQUE, sha256 TEXT, titulo TEXT, n_paginas INTEGER,
  resumo TEXT, topicos TEXT, ingerido_em TEXT);
CREATE TABLE IF NOT EXISTS chunks(
  id INTEGER PRIMARY KEY,
  doc_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  ordem INTEGER, tipo TEXT,                       -- secao | preambulo | indice
  secao TEXT NOT NULL DEFAULT '', titulo TEXT NOT NULL DEFAULT '', trilha TEXT NOT NULL DEFAULT '',
  nota_tecnica TEXT NOT NULL DEFAULT '', data_aprovacao TEXT NOT NULL DEFAULT '',
  link_fonte TEXT NOT NULL DEFAULT '', pag_ini INTEGER, pag_fim INTEGER,
  texto TEXT NOT NULL DEFAULT '', texto_hash TEXT, conclusoes TEXT NOT NULL DEFAULT '',
  normas TEXT NOT NULL DEFAULT '[]',
  resumo TEXT NOT NULL DEFAULT '', palavras_chave TEXT NOT NULL DEFAULT '',
  perguntas TEXT NOT NULL DEFAULT '', contexto TEXT NOT NULL DEFAULT '',
  embedding BLOB);
CREATE INDEX IF NOT EXISTS ix_chunks_doc ON chunks(doc_id);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  titulo, texto, resumo, palavras_chave, perguntas, contexto,
  content='chunks', content_rowid='id', tokenize='unicode61 remove_diacritics 2');
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
  INSERT INTO chunks_fts(rowid,titulo,texto,resumo,palavras_chave,perguntas,contexto)
  VALUES(new.id,new.titulo,new.texto,new.resumo,new.palavras_chave,new.perguntas,new.contexto);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts,rowid,titulo,texto,resumo,palavras_chave,perguntas,contexto)
  VALUES('delete',old.id,old.titulo,old.texto,old.resumo,old.palavras_chave,old.perguntas,old.contexto);
END;
CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE OF titulo,texto,resumo,palavras_chave,perguntas,contexto ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts,rowid,titulo,texto,resumo,palavras_chave,perguntas,contexto)
  VALUES('delete',old.id,old.titulo,old.texto,old.resumo,old.palavras_chave,old.perguntas,old.contexto);
  INSERT INTO chunks_fts(rowid,titulo,texto,resumo,palavras_chave,perguntas,contexto)
  VALUES(new.id,new.titulo,new.texto,new.resumo,new.palavras_chave,new.perguntas,new.contexto);
END;
"""

STOP = set("""a o as os de da do das dos e em no na nos nas um uma uns umas para por com sem sob sobre que se
ao aos à às é são foi ser como mais mas ou não nem já pela pelo pelas pelos seu sua seus suas este esta estes
estas esse essa esses essas isso isto entre até quando onde cujo cuja deve devem pode podem possui há art
nº lei decreto caso forma desde após ante bem também dessa desse nesta neste nessa nesse sendo tendo considerando""".split())


def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(SCHEMA)
    _migrar(con)
    return con


# --------------------------------------------------------------------------- extração e limpeza
def fetch(src: str) -> bytes:
    if re.match(r"https?://", src):
        import requests
        r = requests.get(src, timeout=180, headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=True)
        r.raise_for_status()
        return r.content
    return Path(src).read_bytes()


SOFT = "\u00ad"  # hífen suave: no fim da linha marca palavra quebrada (é removido ao juntar a linha seguinte)
LIGATURAS = str.maketrans({"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"})
ESPACOS = dict.fromkeys(map(ord, "\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000\t"), " ")
HIFENS = {ord(c): "-" for c in "\u2010\u2011\u2012\u2212"}
# controles (inclui \x08, usado como "líder" nos sumários), zero-width, marcas bidi, U+FFFD e áreas de uso privado
LIXO_RE = re.compile("[\x00-\x08\x0b-\x1f\x7f-\x9f\u200b-\u200f\u2028\u2029\u202a-\u202e\u2060\ufeff\ufffd\ue000-\uf8ff]")
BULLET_RE = re.compile("^[•▪▫●○◦■□◆◇►▶➢✓✔·\uf0b7\uf0a7]\\s*(?=\\S)")
PONTILHADO_RE = re.compile(r"\.{4,}|…{2,}|(?:\. ){4,}")
NUM_PAGINA_RE = re.compile(r"(?:p[áa]g(?:ina)?\.?\s*)?\d{1,4}(?:\s*(?:/|de)\s*\d{1,4})?", re.I)
INSTITUCIONAL_RE = re.compile(r"^(controladoria|corregedoria|minist[eé]rio|governo|presid[eê]ncia|cgu\b)", re.I)


def clean_line(s: str) -> str:
    """Normaliza uma linha: Unicode, ligaduras, espaços exóticos, caracteres de controle, marcadores, pontilhado de sumário."""
    s = unicodedata.normalize("NFC", s).translate(LIGATURAS).translate(ESPACOS).translate(HIFENS)
    s = LIXO_RE.sub("", s)
    quebra = s.rstrip().endswith(SOFT)
    s = s.replace(SOFT, "")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\b([nN])°", r"\1º", s)          # n° -> nº
    s = re.sub(r"(?<=\d)°", "º", s)              # 1° -> 1º
    s = BULLET_RE.sub("- ", s)
    s = PONTILHADO_RE.sub(" ", s).strip()
    return s + SOFT if quebra and s else s


def _negrito(nome: str) -> bool:
    return bool(re.search(r"bold|black|heavy|semi|medium|extra", nome, re.I))


def extract_doc(data: bytes) -> dict:
    """Extrai o PDF já limpo. Remove: imagens, cabeçalhos/rodapés repetidos, numeração de página, páginas de sumário,
    marcadores de nota (sobrescrito), caracteres de controle e hífens suaves. Separa as notas de rodapé do corpo."""
    import fitz  # PyMuPDF
    doc = fitz.open(stream=data, filetype="pdf")
    npag = len(doc)
    paginas, n_img = [], 0
    for pno, page in enumerate(doc, 1):
        H, W = (page.rect.height or 1), (page.rect.width or 1)
        linhas = []
        for b in page.get_text("dict")["blocks"]:
            if b["type"] != 0:           # bloco de imagem: ignorado (logotipos, figuras)
                n_img += 1
                continue
            for l in b["lines"]:
                spans = [s for s in l["spans"] if s["text"]]
                tam = max((s["size"] for s in spans if s["text"].strip()), default=0)
                if not tam:
                    continue
                partes, neg, tot = [], 0, 0
                for s in spans:
                    t = s["text"]
                    if (s["flags"] & 1) or (s["size"] < 0.75 * tam and t.strip().isdigit()):
                        continue          # sobrescrito = chamada de nota de rodapé
                    partes.append(t)
                    k = len(t.strip())
                    tot += k
                    italico = (s["flags"] & 2) or re.search(r"italic|oblique", s["font"], re.I)
                    if (_negrito(s["font"]) or (s["flags"] & 16)) and not italico:   # citações em negrito-itálico não são títulos
                        neg += k
                bruto = "".join(partes)
                if not bruto.strip():
                    continue
                linhas.append(dict(
                    t=clean_line(bruto), pg=pno, y0=l["bbox"][1] / H, y1=l["bbox"][3] / H, x1=l["bbox"][2] / W,
                    size=tam, neg=tot > 0 and neg / tot >= 0.6,
                    toc=("\x08" in bruto) or bool(PONTILHADO_RE.search(bruto))))
        paginas.append(linhas)

    todas = [l for pl in paginas for l in pl]
    cont = Counter()
    for l in todas:
        cont[round(l["size"])] += len(l["t"])
    corpo = cont.most_common(1)[0][0] if cont else 11
    usa_neg = sum(len(l["t"]) for l in todas if l["neg"]) / (sum(cont.values()) or 1) < 0.30
    for l in todas:
        l["forte"] = round(l["size"]) >= corpo + 1 or (usa_neg and l["neg"])

    # --- título do documento (capa): linhas do título + edição + ano, sem órgão/data/edição soltos
    cabeca = paginas[0] if paginas else []
    p1 = [l["t"] for l in cabeca if len(l["t"]) > 3 and not (INSTITUCIONAL_RE.match(l["t"]) and (_upper(l["t"]) or re.match(r"controladoria", l["t"], re.I)))
          and not re.match(r"Bras[ií]lia", l["t"], re.I) and not re.search(r"edi[cç][ãa]o", l["t"], re.I)][:4]
    titulo = " ".join(p1).strip()[:200]
    txt1 = " ".join(l["t"] for l in cabeca)
    ed = re.search(r"(\d+)\s*[ªaº°]?\s*edi[cç][ãa]o", txt1, re.I)
    if ed:
        titulo += f" ({ed.group(1)}ª edição)"
    ano = re.search(r"Bras[ií]lia[^\d]{0,30}(20\d\d)", txt1)
    if ano:
        titulo += f" ({ano.group(1)})"

    # --- cabeçalhos/rodapés: linhas das margens que se repetem em muitas páginas, e numeração de página
    em_zona = lambda l: l["y1"] < 0.10 or l["y0"] > 0.90
    freq = Counter()
    for pl in paginas:
        for t in {l["t"].lower() for l in pl if em_zona(l) and l["t"]}:
            freq[t] += 1
    lim = max(3, int(0.12 * npag))
    cab_rod, corpo_pg, notas_pg = Counter(), [], []
    for pl in paginas:
        corpo_l, notas_l = [], []
        for l in pl:
            t = l["t"]
            if not t or not re.search(r"\w", t):
                continue
            if em_zona(l) and (NUM_PAGINA_RE.fullmatch(t) or freq[t.lower()] >= lim):
                cab_rod[t] += 1
                continue
            if round(l["size"]) <= corpo - 2 and l["y0"] > 0.5:   # fonte bem menor no pé da página = nota de rodapé
                notas_l.append(l)
            else:
                corpo_l.append(l)
        corpo_pg.append(corpo_l)
        notas_pg.append(notas_l)

    # --- páginas de sumário (linhas com pontilhado / líder \x08 / número de página no fim)
    toc_pgs = set()
    for pno, pl in enumerate(corpo_pg, 1):
        if len(pl) >= 6:
            marcas = sum(1 for l in pl if l["toc"] or (HEAD.match(l["t"]) and TOC_END.search(l["t"])))
            if marcas / len(pl) >= 0.25:
                toc_pgs.add(pno)

    lines, notas = [], []
    for pno, (pl, nl) in enumerate(zip(corpo_pg, notas_pg), 1):
        if pno in toc_pgs:
            continue
        ref = sorted(l["x1"] for l in pl if len(l["t"]) > 40)
        borda = ref[int(0.85 * (len(ref) - 1))] if ref else 1.0   # margem direita do texto justificado
        for l in pl:
            lines.append((l["t"], pno, bool(l["forte"]), l["x1"] < borda - 0.05))
        notas += [(l["t"], pno) for l in nl]

    stats = dict(
        paginas=npag, paginas_sumario=len(toc_pgs), imagens_ignoradas=n_img,
        linhas_cabecalho_rodape=sum(cab_rod.values()), cabecalhos_distintos=[t for t, _ in cab_rod.most_common(4) if not NUM_PAGINA_RE.fullmatch(t)],
        linhas_nota_rodape=len(notas), palavras_quebradas_unidas=sum(1 for t, _, _, _ in lines if t.endswith(SOFT)) + sum(
            1 for (a, _, _, _), (b, _, _, _) in zip(lines, lines[1:]) if re.search(r"[a-zà-ú]-$", a) and b[:1].islower()),
        tamanho_corpo_pt=corpo, usa_negrito=usa_neg)
    return dict(titulo=titulo, n_paginas=npag, lines=lines, notas=notas, stats=stats)


def extract(data: bytes):
    d = extract_doc(data)
    return d["titulo"], d["n_paginas"], d["lines"]


# --------------------------------------------------------------------------- segmentação
HEAD = re.compile(r"^(\d{1,2}(?:\.\d{1,3}){0,5})\.?\s+(\S.*)$")
DOCREF = re.compile(r"^(Nota Técnica|Despacho|Parecer)\b")
TOC_END = re.compile(r"\s\d{1,3}$")
NT_RE = re.compile(r"(Nota Técnica n[ºo°]?\s*[\w./-]+|Despacho\s+(?:[A-Za-z]+\s+)?n?[ºo°]?\s*\d[\w./-]*)")
DATA_RE = re.compile(r"\bem (\d{2}/\d{2}/\d{4})")
LINK_RE = re.compile(r"https?://\S+")
NORMAS_RE = re.compile(
    r"\b(?:Lei(?: Complementar)?|Decreto(?:-Lei)?|Portaria(?: Normativa)?(?: \w+)?|Instrução Normativa(?: \w+)?|"
    r"Emenda Constitucional|Medida Provisória|Súmula Vinculante)\s+n[ºo°]\s*[\d.]+(?:/\d{2,4}|,\s*de\s*\d{4})?")
ITEM_RE = re.compile(r"^(?:[-•]\s|\d{1,3}\.\d{1,3}\.?\s|\(?[a-z]\)\s|\(?[ivx]{1,5}\)\s|[IVX]{1,5}\s*[-–.)]\s|\d{1,3}[.)]\s|§\s*\d|Art\.\s*\d|"
                     r"Parágrafo único|Conclusões acerca|Nota Técnica n|Despacho|Acessível)")
PREFIXOS = {"ex", "vice", "pré", "pós", "pró", "anti", "auto", "contra", "extra", "inter", "intra", "semi", "sub", "super",
            "sobre", "ultra", "infra", "hiper", "neo", "pan", "pseudo", "não", "sócio", "micro", "macro", "co", "mini", "multi",
            "agro", "bio", "geo", "eletro", "ante", "circum", "pluri", "tele", "audio", "video"}
CLITICOS = {"se", "me", "te", "lhe", "lhes", "nos", "vos", "lo", "la", "los", "las", "o", "a", "os", "as"}
MINUSCULAS = {"da", "de", "do", "das", "dos", "e", "o", "a", "os", "as", "em", "no", "na", "nos", "nas", "ao", "aos", "por",
              "com", "sem", "para", "ou", "um", "uma", "sobre", "sob", "ante", "após", "até", "entre"}


def _upper(s):
    letters = [c for c in s if c.isalpha()]
    return len(letters) >= 4 and sum(c.isupper() for c in letters) / len(letters) >= 0.7


def caixa_titulo(s, siglas=frozenset()):
    """Título em CAIXA ALTA -> caixa de frase. Mantém em maiúsculas só as siglas que o próprio documento escreve assim."""
    if not _upper(s):
        return s
    out = []
    for i, w in enumerate(s.split()):
        nucleo = re.sub(r"^\W+|\W+$", "", w)
        if nucleo in siglas:
            out.append(w)
        elif w.lower() in MINUSCULAS and i > 0:
            out.append(w.lower())
        else:
            out.append(w.capitalize() if i == 0 else w.lower())
    return " ".join(out)


def segment(lines):
    """Divide o corpo em seções. Títulos = linha numerada em fonte de destaque (negrito/maior); no ementário, o título
    de item é seguido da referência 'Nota Técnica ...'. Sem informação de estilo, cai na heurística antiga."""
    n = len(lines)
    txt = lambda i: lines[i][0]
    forte = lambda i: lines[i][2]
    # siglas: palavras em maiúsculas (2 a 6 letras) que aparecem ≥3 vezes em linhas que NÃO estão em caixa alta
    contagem = Counter(w for l in lines if not _upper(l[0]) for w in re.findall(r"\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,6}\b", l[0]))
    siglas = frozenset(w for w, k in contagem.items() if k >= 3 and w.lower() not in MINUSCULAS)
    estilo = sum(1 for i in range(n) if forte(i) and HEAD.match(txt(i))) >= 5
    ok = lambda i: bool(HEAD.match(txt(i))) and (
        (forte(i) and not HEAD.match(txt(i)).group(2)[:1].islower()) if estilo else not TOC_END.search(txt(i)))

    def lookahead(i):  # título pode quebrar em até 5 linhas antes de "Nota Técnica ..."
        for k in range(5):
            j = i + k + 1
            if j >= n:
                return None
            if DOCREF.match(txt(j)):
                return k
            if ok(j):
                return None
        return None

    def continuacao(i):  # linhas seguintes também em destaque (título quebrado em várias linhas)
        k = 0
        while k < 4 and i + k + 1 < n and forte(i + k + 1) and not HEAD.match(txt(i + k + 1)) \
                and not DOCREF.match(txt(i + k + 1)) and len(txt(i + k + 1)) < 150:
            k += 1
        return k

    modo = "ementario" if sum(1 for i in range(n) if ok(i) and lookahead(i) is not None) >= 3 else "generico"
    marks, i = [], 0  # (inicio, fim_titulo, numero, titulo, nivel, kind)
    while i < n:
        if ok(i):
            m = HEAD.match(txt(i))
            num, tit = m.group(1), m.group(2)
            nivel = num.count(".") + 1
            k = lookahead(i) if not (_upper(tit) and nivel <= 2 and modo == "ementario") else None
            if k is not None:
                kind = "item"
            elif estilo:
                k, kind = continuacao(i), "secao"
            elif (modo == "generico" and len(txt(i)) < 120 and tit[0].isupper() and nivel <= 3
                  and not txt(i).endswith((".", ";", ",", ":")) and i + 1 < n and not txt(i + 1)[:1].islower()):
                k, kind = 0, "secao"
            elif _upper(tit) and nivel <= 2 and len(txt(i)) < 150:
                k, kind = 0, "secao"
            else:
                i += 1
                continue
            titulo = " ".join([tit] + [txt(j) for j in range(i + 1, i + k + 1)]).replace(SOFT + " ", "").replace(SOFT, "")
            marks.append((i, i + k, num, caixa_titulo(titulo.strip(), siglas), nivel, kind))
            i += k + 1
            continue
        i += 1

    segs, crumbs = [], {}
    primeiro = marks[0][0] if marks else n
    if primeiro > 0:
        segs.append(dict(tipo="preambulo", kind="preambulo", secao="", titulo="Preâmbulo", trilha="", lines=lines[:primeiro]))
    for idx, (ini, fim, num, tit, nivel, kind) in enumerate(marks):
        fim_corpo = marks[idx + 1][0] if idx + 1 < len(marks) else n
        crumbs = {l: t for l, t in crumbs.items() if l < nivel}
        trilha = " > ".join(crumbs[l] for l in sorted(crumbs))
        if kind == "secao":
            crumbs[nivel] = tit
        corpo = lines[fim + 1:fim_corpo]
        if not corpo:
            continue
        segs.append(dict(tipo="secao", kind=kind, secao=num, titulo=tit, trilha=trilha, lines=corpo))
    return segs


# --------------------------------------------------------------------------- parágrafos e chunks
def reflow(lines):
    """Junta as linhas em parágrafos: une palavras quebradas (hífen suave), une linhas do mesmo parágrafo e separa
    itens/alíneas e fins de parágrafo (linha curta terminada em pontuação)."""
    pars = []  # [texto, pg_ini, pg_fim, curta]
    for t, pg, _, curta in lines:
        if pars:
            ant = pars[-1]
            if ant[0].endswith(SOFT):
                ant[0] = ant[0][:-1] + t
                ant[1:] = [ant[1], pg, curta]
                continue
            m = re.search(r"([A-Za-zÀ-ÿ]+)-$", ant[0])
            if m and not ITEM_RE.match(t) and t[:1].isalpha():     # palavra partida com hífen comum no fim da linha
                prox = re.match(r"[a-zà-ú]+", t)
                if t[:1].islower():
                    manter = m.group(1).lower() in PREFIXOS or (prox and prox.group(0) in CLITICOS)   # ex-servidor, considerar-se
                    ant[0] = ant[0] + t if manter else ant[0][:-1] + t                              # x esclare-cimento
                else:
                    ant[0] = ant[0] + t                                                          # Corregedoria-Geral
                ant[1:] = [ant[1], pg, curta]
                continue
            fim_par = ant[3] and re.search(r"[.!?:;”\")»]$", ant[0])
            if not ITEM_RE.match(t) and not fim_par:
                ant[0] = ant[0] + " " + t
                ant[2], ant[3] = pg, curta
                continue
        pars.append([t, pg, pg, curta])
    out = []
    for p in pars:
        p[0] = p[0].replace(SOFT, "")
        out.append(p[:3])
    return out


def _sentencas(texto):
    return re.split(r"(?<=[.!?;:])\s+", texto)


def _quebra_longo(p, limite):
    if len(p[0]) <= limite:
        return [p]
    out, atual = [], ""
    for s in _sentencas(p[0]):
        while len(s) > limite:                       # sentença gigante: corta em espaço
            corte = s.rfind(" ", 0, limite)
            if corte <= 0:
                corte = limite
            out.append([(atual + " " + s[:corte]).strip(), p[1], p[2]]); atual, s = "", s[corte:].strip()
        if len(atual) + len(s) + 1 > limite and atual:
            out.append([atual, p[1], p[2]]); atual = s
        else:
            atual = (atual + " " + s).strip()
    if atual:
        out.append([atual, p[1], p[2]])
    return out


def _cauda(texto, n):
    acc, tam = [], 0
    for s in reversed(_sentencas(texto)):
        tam += len(s) + 1
        if tam > n * 1.5 or (tam > n and acc):
            break
        acc.insert(0, s)
    return " ".join(acc)


def split_paragrafos(pars):
    """Agrupa parágrafos em pedaços de até MAX_CHARS (sem cortar parágrafo/sentença), funde sobra pequena e
    repete ao início do pedaço seguinte a cauda (OVERLAP caracteres) do anterior."""
    reserva = int(min(OVERLAP * 1.5, MAX_CHARS // 3)) if OVERLAP else 0   # espaço para a cauda repetida: o chunk final fica ≤ MAX_CHARS
    limite = MAX_CHARS - reserva
    pecas, cur, tam = [], [], 0
    for p in pars:
        for sub in _quebra_longo(p, limite):
            if tam + len(sub[0]) + 2 > limite and cur:
                pecas.append(cur); cur, tam = [], 0
            cur.append(sub); tam += len(sub[0]) + 2
    if cur:
        pecas.append(cur)
    minimo = max(300, limite // 8)
    if len(pecas) > 1 and sum(len(p[0]) + 2 for p in pecas[-1]) < minimo \
            and sum(len(p[0]) + 2 for p in pecas[-2] + pecas[-1]) <= limite:
        ultima = pecas.pop()
        pecas[-1] += ultima
    if OVERLAP:
        for i in range(len(pecas) - 1, 0, -1):
            c = _cauda(pecas[i - 1][-1][0], OVERLAP)
            if len(c) > 40:
                pecas[i] = [[c, pecas[i - 1][-1][2], pecas[i - 1][-1][2]]] + pecas[i]
    return pecas


def agrupar_notas(notas):
    """Notas de rodapé: cada nota começa em 'N. texto'; linhas seguintes são continuação."""
    out = []
    for t, pg in notas:
        if out and not re.match(r"^\d{1,3}[.)]\s", t):
            out[-1][0] += " " + t.replace(SOFT, "")
        else:
            out.append([t.replace(SOFT, ""), pg])
    return out


def is_toc(piece):
    """(compatibilidade) detecta bloco de sumário residual: muitas linhas terminando em número de página/pontilhado."""
    ls = piece if isinstance(piece, list) else str(piece).splitlines()
    ls = [x[0] if isinstance(x, (tuple, list)) else x for x in ls]
    if len(ls) < 8:
        return False
    return sum(1 for t in ls if TOC_END.search(t) or PONTILHADO_RE.search(t)) / len(ls) >= 0.3


def build_chunks(lines, notas=()):
    out, ordem = [], 0
    notas_por_pg = {}
    for texto, pg in agrupar_notas(notas):
        notas_por_pg.setdefault(pg, []).append(texto)
    for s in segment(lines):
        pars = reflow(s["lines"])
        nt = dt = lk = None
        if s["kind"] == "item":      # só no ementário: a referência da Nota Técnica é o parágrafo logo após o título
            ref = next((p[0] for p in pars[:3] if DOCREF.match(p[0])), "")
            nt, dt, lk = NT_RE.search(ref), DATA_RE.search(ref), LINK_RE.search(ref)
        completo = "\n".join(p[0] for p in pars)
        normas = list(dict.fromkeys(re.sub(r"\s+", " ", x) for x in NORMAS_RE.findall(completo)))
        for peca in split_paragrafos(pars):
            texto = "\n\n".join(p[0] for p in peca)
            tipo = s["tipo"]
            if tipo == "preambulo" and is_toc([p[0] for p in peca]):
                tipo = "indice"
            concl = ""
            if "Conclusões acerca da matéria" in texto:
                concl = texto.split("Conclusões acerca da matéria", 1)[1].lstrip(": \n")
            pag_ini, pag_fim = peca[0][1], peca[-1][2]
            out.append(dict(
                ordem=ordem, tipo=tipo, secao=s["secao"], titulo=s["titulo"], trilha=s["trilha"],
                nota_tecnica=nt.group(1).strip() if nt else "", data_aprovacao=dt.group(1) if dt else "",
                link_fonte=lk.group(0).rstrip(".,;)") if lk else "",
                pag_ini=pag_ini, pag_fim=pag_fim, texto=texto,
                texto_hash=hashlib.sha1(texto.encode()).hexdigest(), conclusoes=concl,
                normas=json.dumps(normas, ensure_ascii=False), notas_rodape="", _pgs=(pag_ini, pag_fim)))
            ordem += 1
    for pg, ns in notas_por_pg.items():      # cada nota vai para o primeiro chunk que cobre a página dela
        alvo = next((c for c in out if c["_pgs"][0] <= pg <= c["_pgs"][1]), None)
        if alvo:
            alvo["notas_rodape"] = (alvo["notas_rodape"] + "\n" + "\n".join(ns)).strip()
    for c in out:
        c.pop("_pgs", None)
    return out


def build_sections(lines, notas=()):
    """Seções inteiras e limpas (sem cortar por tamanho), prontas para virar Document do LangChain.
    O corte em chunks fica a cargo do RecursiveCharacterTextSplitter, o cortador do curso."""
    notas_por_pg = {}
    for texto, pg in agrupar_notas(notas):
        notas_por_pg.setdefault(pg, []).append(texto)
    out = []
    for s in segment(lines):
        pars = reflow(s["lines"])
        if not pars:
            continue
        nt = dt = lk = None
        if s["kind"] == "item":      # só no ementário: a referência da Nota Técnica vem logo após o título
            ref = next((p[0] for p in pars[:3] if DOCREF.match(p[0])), "")
            nt, dt, lk = NT_RE.search(ref), DATA_RE.search(ref), LINK_RE.search(ref)
        texto = "\n\n".join(p[0] for p in pars)
        normas = list(dict.fromkeys(re.sub(r"\s+", " ", x) for x in NORMAS_RE.findall(texto)))
        out.append(dict(
            tipo=s["tipo"], kind=s["kind"], secao=s["secao"], titulo=s["titulo"], trilha=s["trilha"],
            nota_tecnica=nt.group(1).strip() if nt else "", data_aprovacao=dt.group(1) if dt else "",
            link_fonte=lk.group(0).rstrip(".,;)") if lk else "", normas="; ".join(normas),
            pag_ini=min(p[1] for p in pars), pag_fim=max(p[2] for p in pars), texto=texto, notas_rodape=""))
    for pg, ns in notas_por_pg.items():      # cada nota vai para a primeira seção que cobre a página dela
        alvo = next((c for c in out if c["pag_ini"] <= pg <= c["pag_fim"]), None)
        if alvo:
            alvo["notas_rodape"] = (alvo["notas_rodape"] + "\n" + "\n".join(ns)).strip()
    return out


# --------------------------------------------------------------------------- ingestão
def ingest(con, src, force=False):
    data = fetch(src)
    h = hashlib.sha256(data).hexdigest()
    row = con.execute("SELECT id, sha256, limpeza FROM documents WHERE url=?", (src,)).fetchone()
    if row and row["sha256"] == h and row["limpeza"] and not force:   # sem 'limpeza' = ingerido por versão antiga: refaz
        print(f"= ignorado (sem mudanças): {src}"); return
    reuse = {}
    if row:  # preserva enriquecimento/embeddings de trechos idênticos
        for r in con.execute("SELECT texto_hash,resumo,palavras_chave,perguntas,contexto,embedding FROM chunks WHERE doc_id=?", (row["id"],)):
            reuse[r["texto_hash"]] = r
        con.execute("DELETE FROM documents WHERE id=?", (row["id"],))
    d = extract_doc(data)
    titulo, npag, stats = d["titulo"], d["n_paginas"], d["stats"]
    chunks = build_chunks(d["lines"], d["notas"])
    stats["chunks"] = len(chunks)
    doc_id = con.execute("INSERT INTO documents(url,sha256,titulo,n_paginas,ingerido_em,limpeza) VALUES(?,?,?,?,datetime('now'),?)",
                         (src, h, titulo, npag, json.dumps(stats, ensure_ascii=False))).lastrowid
    for c in chunks:
        old = reuse.get(c["texto_hash"])
        con.execute(
            """INSERT INTO chunks(doc_id,ordem,tipo,secao,titulo,trilha,nota_tecnica,data_aprovacao,link_fonte,pag_ini,pag_fim,
               texto,texto_hash,conclusoes,normas,notas_rodape,resumo,palavras_chave,perguntas,contexto,embedding)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (doc_id, c["ordem"], c["tipo"], c["secao"], c["titulo"], c["trilha"], c["nota_tecnica"], c["data_aprovacao"],
             c["link_fonte"], c["pag_ini"], c["pag_fim"], c["texto"], c["texto_hash"], c["conclusoes"], c["normas"],
             c["notas_rodape"],
             old["resumo"] if old else "", old["palavras_chave"] if old else "", old["perguntas"] if old else "",
             old["contexto"] if old else "", old["embedding"] if old else None))
    con.commit()
    k = Counter(c["tipo"] for c in chunks)
    print(f"+ {titulo[:60]!r}: {npag} págs, {len(chunks)} chunks {dict(k)} | limpeza: {stats['paginas_sumario']} pág. de sumário, "
          f"{stats['linhas_cabecalho_rodape']} linhas de cabeçalho/rodapé, {stats['linhas_nota_rodape']} de nota de rodapé, "
          f"{stats['palavras_quebradas_unidas']} palavras reunidas")


def _migrar(con):
    """Bancos criados por versões anteriores ganham as colunas novas."""
    if "notas_rodape" not in {r[1] for r in con.execute("PRAGMA table_info(chunks)")}:
        con.execute("ALTER TABLE chunks ADD COLUMN notas_rodape TEXT NOT NULL DEFAULT ''")
    if "limpeza" not in {r[1] for r in con.execute("PRAGMA table_info(documents)")}:
        con.execute("ALTER TABLE documents ADD COLUMN limpeza TEXT")
    con.commit()


RUIDOS = {
    "cabeçalho/rodapé": re.compile(r"EMENTÁRIO DE NOTAS TÉCNICAS •|MANUAL DE PAD •|^CGU$", re.M),
    "hífen suave": re.compile("\u00ad"),
    "caractere de controle": re.compile("[\x00-\x08\x0b-\x1f\x7f-\x9f\u200b-\u200f\ufeff\ufffd\ue000-\uf8ff]"),
    "pontilhado de sumário": re.compile(r"\.{4,}"),
    "palavra partida (hífen no meio do texto)": re.compile(r"[a-zà-ú]- [a-zà-ú]"),
    "ligadura": re.compile("[ﬁﬂﬀﬃﬄ]"),
}


def quality_report(con):
    """Qualidade do que foi indexado: ruído residual por tipo, tamanho dos chunks e cobertura de metadados/páginas."""
    import statistics
    rel = []
    for d in con.execute("SELECT id,titulo,n_paginas,limpeza FROM documents ORDER BY id").fetchall():
        rows = con.execute("SELECT tipo,texto,nota_tecnica,link_fonte,pag_ini,pag_fim,notas_rodape FROM chunks WHERE doc_id=?", (d["id"],)).fetchall()
        util = [r for r in rows if r["tipo"] != "indice"]
        tam = [len(r["texto"]) for r in util] or [0]
        paginas = set()
        for r in util:
            paginas.update(range(r["pag_ini"], r["pag_fim"] + 1))
        itens = [r for r in util if r["nota_tecnica"]]
        rel.append(dict(
            doc=d["id"], titulo=d["titulo"][:60], paginas=d["n_paginas"], chunks=len(util),
            tam_mediano=int(statistics.median(tam)), tam_min=min(tam), tam_max=max(tam),
            curtos_300=sum(1 for t in tam if t < 300), paginas_cobertas=len(paginas),
            com_nota_tecnica=len(itens), com_link=sum(1 for r in itens if r["link_fonte"]),
            com_notas_rodape=sum(1 for r in util if r["notas_rodape"]),
            ruido={k: sum(1 for r in util if rx.search(r["texto"])) for k, rx in RUIDOS.items()},
            limpeza=json.loads(d["limpeza"]) if d["limpeza"] else None))
    return rel


# --------------------------------------------------------------------------- enriquecimento
def top_terms(text, n=8):
    w = [x for x in re.findall(r"[a-zà-ú]{4,}", text.lower()) if x not in STOP]
    return [t for t, _ in Counter(w).most_common(n)]


def heuristic_enrich(r):
    base = r["conclusoes"] or r["texto"]
    resumo = re.sub(r"\s+", " ", base)
    if len(resumo) > 320:
        resumo = resumo[:320].rsplit(" ", 1)[0] + "…"
    return dict(resumo=resumo, palavras_chave="; ".join(top_terms(r["texto"])), perguntas="",
                contexto=" — ".join(x for x in (r["trilha"], f'{r["secao"]} {r["titulo"]}'.strip(), r["nota_tecnica"]) if x))


SYS_PROMPT = "Você indexa documentos jurídico-administrativos brasileiros para RAG. Responda SOMENTE com JSON válido."

# Todos os provedores abaixo expõem a API compatível com OpenAI (/chat/completions e /models).
# nome: (base_url, [modelos preferidos, do mais novo ao mais antigo], parametros_extras)
# O modelo usado é o primeiro da lista que a SUA chave enxerga em /models (veja resolve_model), então
# nomes que o provedor desligou são pulados sozinhos. Para forçar um modelo, defina RAG_MODEL_<NOME>.
PROVIDERS = {
    "modelscope": ("https://api-inference.modelscope.cn/v1",
                   ["Qwen/Qwen3.8-27B", "Qwen/Qwen3-235B-A22B-Instruct-2507", "deepseek-ai/DeepSeek-V4-Pro",
                    "Qwen/Qwen2.5-72B-Instruct"],
                   {"enable_thinking": False}),
    "openrouter": ("https://openrouter.ai/api/v1",
                   ["anthropic/claude-haiku-5.5", "anthropic/claude-haiku-4.5"], {}),
    "groq": ("https://api.groq.com/openai/v1",
             ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"],
             {"reasoning_effort": "low", "include_reasoning": False}),
    "openai": ("https://api.openai.com/v1", ["gpt-4.1-mini", "gpt-4o-mini"], {}),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai",
               ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.6-flash", "gemini-3.8-flash"],
               {"reasoning_effort": "low"}),
    "cerebras": ("https://api.cerebras.ai/v1", ["gpt-oss-120b", "llama-3.3-70b"], {}),
    "deepseek": ("https://api.deepseek.com/v1", ["deepseek-chat"], {}),
    "mistral": ("https://api.mistral.ai/v1", ["mistral-small-latest"], {}),
    "together": ("https://api.together.xyz/v1", ["meta-llama/Llama-3.3-70B-Instruct-Turbo"], {}),
}
DEFAULT_ORDER = "modelscope,openrouter,groq,openai,gemini,cerebras,deepseek,mistral,together"
PLACEHOLDERS = {"", "sk-...", "...", "xxx", "cole_aqui"}
QUOTA_WORDS = ("quota", "insufficient", "credit", "balance", "billing", "exhausted", "per day", "tpd", "daily")
# Modelos de raciocínio gastam parte de max_tokens "pensando": com limite baixo a resposta vem vazia.
MIN_TOKENS = {"groq": 2048, "gemini": 2048, "cerebras": 2048, "modelscope": 1024}

_STATE = {}          # (provedor, chave) -> instante até o qual fica indisponível (inf = esgotada/inválida)
_USO = Counter()     # respostas bem-sucedidas por provedor
_MODELOS = {}        # (provedor, chave) -> ids vistos em /models (None = não deu para listar)
_SEM_EXTRAS = set()  # provedores cujo modelo recusou os parâmetros extras (reasoning_effort etc.)
_AVISOS = set()


class LLMIndisponivel(Exception):
    pass


def _mask(k):
    return k[:4] + "…" + k[-3:] if len(k) > 8 else "***"


def _aviso(msg):
    if msg not in _AVISOS:
        _AVISOS.add(msg)
        print("  aviso:", msg, file=sys.stderr)


def clean_key(prov, k):
    """Corrige erros comuns ao colar a chave: aspas, espaços e o placeholder 'sk-...' grudado no começo."""
    antes = k.strip()
    k = antes.strip("\"'").strip()
    k = re.sub(r"^(?:sk-)?\.{3}", "", k)            # "sk-...sk-or-v1-abc" vira "sk-or-v1-abc"
    if k != antes:
        _aviso(f"{prov}: a chave tinha sobras (aspas ou 'sk-...' no começo); usei {_mask(k)}")
    if prov == "openrouter" and k and not k.startswith("sk-or-"):
        _aviso("openrouter: chaves do OpenRouter começam com 'sk-or-'; confira se copiou a chave certa")
    return k


def _ordem():
    ordem = os.getenv("RAG_PROVIDER_ORDER", DEFAULT_ORDER).split(",")
    return list(dict.fromkeys(p.strip().lower() for p in ordem if p.strip().lower() in PROVIDERS))


def _chaves(prov):
    """Chaves válidas de um provedor (o campo aceita várias, separadas por vírgula)."""
    out = []
    for bruta in re.split(r"[,\n;]+", os.getenv(f"{prov.upper()}_API_KEY", "")):
        if bruta.strip().lower() in PLACEHOLDERS:
            continue
        k = clean_key(prov, bruta)
        if not k or k.lower() in PLACEHOLDERS:
            continue
        if "…" in k or "..." in k:
            _aviso(f"{prov}: a chave {_mask(k)} parece truncada (tem '...'); cole a chave completa")
            continue
        out.append(k)
    return out


def list_models(prov, key):
    """Ids de modelos que esta chave enxerga (GET /models). None se o provedor não deixar listar."""
    import requests
    if (prov, key) not in _MODELOS:
        ids = None
        try:
            r = requests.get(f"{PROVIDERS[prov][0]}/models", headers={"Authorization": f"Bearer {key}"}, timeout=30)
            if r.status_code == 200:
                ids = [str(m["id"]).removeprefix("models/") for m in r.json().get("data", []) if m.get("id")]
        except (requests.RequestException, ValueError, AttributeError):
            ids = None
        _MODELOS[(prov, key)] = ids
    return _MODELOS[(prov, key)]


def resolve_model(prov, key):
    """Modelo a usar: o forçado em RAG_MODEL_<NOME> ou o primeiro preferido que a chave enxerga.
    Devolve None se a lista existe e nenhum dos preferidos está nela."""
    forcado = os.getenv(f"RAG_MODEL_{prov.upper()}")
    if forcado:
        return forcado
    prefs = PROVIDERS[prov][1]
    ids = list_models(prov, key)
    if not ids:
        return prefs[0]                    # não deu para listar: tenta o primeiro e deixa o erro aparecer
    por_minuscula = {i.lower(): i for i in ids}
    for m in prefs:
        if m.lower() in por_minuscula:
            return por_minuscula[m.lower()]
    return None


def candidates():
    """Lista (provedor, chave, modelo) na ordem de prioridade, só com o que dá para chamar."""
    return [(p, k, m) for p in _ordem() for k in _chaves(p) for m in [resolve_model(p, k)] if m]


def llm_ok():
    return bool(candidates())


def _classify(r):
    """Retorna (rotulo, segundos_indisponivel). inf = esgotada/inválida nesta sessão."""
    body = r.text[:400].lower()
    if r.status_code in (401, 403):
        return "chave inválida/sem permissão", float("inf")
    if r.status_code == 402 or (r.status_code == 429 and any(w in body for w in QUOTA_WORDS)):
        return "sem saldo/cota esgotada", float("inf")
    if r.status_code == 404:
        return "modelo ou endereço não encontrado", float("inf")
    if r.status_code == 429:
        try:
            return "limite de taxa", min(float(r.headers.get("retry-after", 30)), 120)
        except ValueError:
            return "limite de taxa", 30
    if r.status_code >= 500:
        return "erro do provedor", 30
    return f"requisição recusada ({r.status_code})", 0


def _detalhe(r, key=""):
    """Mensagem de erro devolvida pelo provedor (sem a chave), para diagnóstico."""
    try:
        j = r.json()
        if isinstance(j, list) and j:
            j = j[0]
        e = j.get("error", j) if isinstance(j, dict) else j
        msg = (e.get("message") if isinstance(e, dict) else str(e)) or r.text
    except ValueError:
        msg = r.text
    msg = re.sub(r"\s+", " ", str(msg)).strip()
    return (msg.replace(key, "***") if key else msg)[:220]


def _post(prov, key, model, msgs, max_tokens):
    import requests
    base, _, extra = PROVIDERS[prov]

    def chamar(ex):
        corpo = {"model": model, "max_tokens": max(max_tokens, MIN_TOKENS.get(prov, 0)),
                 "temperature": 0.2, "messages": msgs, **ex}
        return requests.post(f"{base}/chat/completions", json=corpo, timeout=120,
                             headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})

    ex = {} if prov in _SEM_EXTRAS else extra
    r = chamar(ex)
    if r.status_code == 400 and ex:        # o modelo não aceitou um parâmetro extra: tenta de novo sem eles
        r2 = chamar({})
        if r2.status_code == 200:
            _SEM_EXTRAS.add(prov)
        return r2
    return r


def llm_call(prompt, system=None, max_tokens=700):
    """Chama o primeiro provedor/chave disponível; se estiver sem tokens, inválido ou limitado, passa para o próximo."""
    import requests
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    cands = candidates()
    if not cands:
        raise LLMIndisponivel("nenhuma chave de API configurada")
    for rodada in range(2):
        for prov, key, model in cands:
            if _STATE.get((prov, key), 0) > time.time():
                continue
            try:
                r = _post(prov, key, model, msgs, max_tokens)
            except requests.RequestException as e:
                _STATE[(prov, key)] = time.time() + 30
                print(f"  ! {prov} ({_mask(key)}): {type(e).__name__}; tentando o próximo", file=sys.stderr)
                continue
            if r.status_code == 200:
                try:
                    txt = r.json()["choices"][0]["message"]["content"]
                except (KeyError, IndexError, ValueError, TypeError):
                    txt = None
                if txt:
                    _USO[prov] += 1
                    return txt
                _STATE[(prov, key)] = time.time() + 30
                print(f"  ! {prov} ({_mask(key)}): resposta vazia -> próximo", file=sys.stderr)
                continue
            rotulo, espera = _classify(r)
            if espera:
                _STATE[(prov, key)] = time.time() + espera
            print(f"  ! {prov} ({_mask(key)}, {model}): {rotulo} [{_detalhe(r, key)[:120]}] -> próximo", file=sys.stderr)
        pend = [v - time.time() for v in _STATE.values() if time.time() < v < float("inf")]
        if rodada == 0 and pend:
            time.sleep(min(min(pend), 60) + 1)
        else:
            break
    raise LLMIndisponivel("todos os provedores/chaves estão indisponíveis (sem saldo, inválidos ou limitados)")


def check_providers():
    """Testa cada chave com uma requisição mínima e imprime o status e a mensagem do provedor."""
    import requests
    rows, achou = [], False
    for prov in _ordem():
        for key in _chaves(prov):
            achou = True
            model = resolve_model(prov, key)
            if model is None:
                ids = list_models(prov, key) or []
                print(f"{prov:11s} {_mask(key):10s} nenhum modelo preferido está disponível para esta chave")
                print(f"{'':11s} ↳ exemplos que ela enxerga: {', '.join(ids[:8])}")
                print(f"{'':11s} ↳ escolha um e defina em MODELOS['{prov}'] (veja a célula 'Ver modelos disponíveis')")
                rows.append(dict(provedor=prov, chave=_mask(key), modelo=None, http=0, status="sem modelo", ms=0))
                continue
            t0 = time.time()
            detalhe = ""
            try:
                r = _post(prov, key, model, [{"role": "user", "content": "Responda apenas: ok"}], 64)
                code = r.status_code
                if code == 200:
                    try:
                        txt = r.json()["choices"][0]["message"]["content"] or ""
                    except (KeyError, IndexError, ValueError, TypeError):
                        txt = ""
                    status = "OK" if txt.strip() else "responde, mas a resposta veio vazia (modelo de raciocínio?)"
                else:
                    status, detalhe = _classify(r)[0], _detalhe(r, key)
            except requests.RequestException as e:
                status, code = f"falha de conexão ({type(e).__name__})", 0
            ms = int((time.time() - t0) * 1000)
            rows.append(dict(provedor=prov, chave=_mask(key), modelo=model, http=code, status=status, ms=ms))
            print(f"{prov:11s} {_mask(key):10s} {model[:38]:38s} {status} ({ms} ms)")
            if detalhe:
                print(f"{'':11s} ↳ resposta do provedor: {detalhe}")
    if not achou:
        print("Nenhuma chave configurada.")
    return rows


def show_models(filtro=""):
    """Lista os ids de modelo que cada chave configurada enxerga (para escolher o nome exato)."""
    for prov in _ordem():
        for key in _chaves(prov):
            ids = list_models(prov, key)
            if ids is None:
                print(f"\n{prov} ({_mask(key)}): não foi possível listar (chave inválida ou provedor sem /models)")
                continue
            sel = sorted(i for i in ids if filtro.lower() in i.lower())
            print(f"\n{prov} ({_mask(key)}): {len(sel)} modelo(s)" + (f" contendo '{filtro}'" if filtro else ""))
            for i in sel[:60]:
                print("  ", i)
            if len(sel) > 60:
                print(f"   ... (+{len(sel) - 60}; use o filtro para refinar)")


def llm_enrich_one(r, doc_titulo):
    prompt = f"""Documento: {doc_titulo}
Trilha: {r['trilha']}
Seção: {r['secao']} {r['titulo']}
Referência: {r['nota_tecnica']}

Trecho:
{r['texto'][:6000]}

Gere JSON com as chaves:
"resumo": no máximo 2 frases, fiel ao texto, destacando a tese/conclusão;
"palavras_chave": lista de 5 a 10 termos;
"perguntas": lista de 3 perguntas que um servidor faria e que este trecho responde;
"contexto": 1 frase situando o trecho no documento (para melhorar a recuperação).
Não invente informações."""
    for tent in range(3):
        try:
            txt = llm_call(prompt, SYS_PROMPT)
            j = json.loads(txt[txt.index("{"): txt.rindex("}") + 1])
            return dict(resumo=str(j.get("resumo", "")).strip(),
                        palavras_chave="; ".join(map(str, j.get("palavras_chave", []))),
                        perguntas="\n".join(map(str, j.get("perguntas", []))),
                        contexto=str(j.get("contexto", "")).strip())
        except LLMIndisponivel:
            raise
        except Exception as e:  # noqa
            print(f"  ! tentativa {tent + 1} falhou: {e}", file=sys.stderr)
            time.sleep(2 ** tent)
    return None


def enrich_pending(con, mode="llm", limit=None):
    use_llm = mode == "llm"
    if use_llm and not llm_ok():
        print("Nenhuma chave de API válida: usando modo heurístico."); mode, use_llm = "heuristic", False
    elif use_llm:
        print("Modo llm; ordem:", " > ".join(dict.fromkeys(p for p, _, _ in candidates())))
    rows = con.execute("""SELECT c.*, d.titulo AS doc_titulo FROM chunks c JOIN documents d ON d.id=c.doc_id
                          WHERE c.tipo!='indice' AND c.resumo='' ORDER BY c.id LIMIT ?""", (limit or -1,)).fetchall()
    interrompido = False
    for n, r in enumerate(rows, 1):
        try:
            e = llm_enrich_one(r, r["doc_titulo"]) if use_llm else None
        except LLMIndisponivel as ex:
            print(f"  ! {ex}. Parando: {len(rows) - n + 1} chunks seguem pendentes (rode de novo com saldo/novas chaves).")
            interrompido = True
            break
        e = e or heuristic_enrich(r)
        con.execute("UPDATE chunks SET resumo=?,palavras_chave=?,perguntas=?,contexto=? WHERE id=?",
                    (e["resumo"], e["palavras_chave"], e["perguntas"], e["contexto"], r["id"]))
        if n % 20 == 0:
            con.commit(); print(f"  enriquecidos {n}/{len(rows)}")
    con.commit()
    if not interrompido:  # resumo por documento (a partir da estrutura)
        for d in con.execute("SELECT id,titulo FROM documents WHERE resumo IS NULL OR resumo=''").fetchall():
            tit = [r[0] for r in con.execute("SELECT trilha||' | '||secao||' '||titulo FROM chunks WHERE doc_id=? AND tipo='secao' LIMIT 120", (d["id"],))]
            topicos = list(dict.fromkeys(t.split(" | ")[0].split(" > ")[0] for t in tit if t.strip(" |")))[:12]
            resumo = f"{d['titulo']} — {len(tit)} seções. Temas: {'; '.join(topicos)}"
            if use_llm:
                try:
                    resumo = llm_call(f"Em até 3 frases, descreva o documento '{d['titulo']}' a partir destes títulos de seção:\n" + "\n".join(tit), max_tokens=400).strip()
                except Exception as e:  # noqa
                    print("  ! resumo do documento falhou:", e, file=sys.stderr)
            con.execute("UPDATE documents SET resumo=?, topicos=? WHERE id=?", (resumo, "; ".join(topicos), d["id"]))
        con.commit()
    feitos = n if interrompido is False and rows else (n - 1 if rows else 0)
    print(f"enriquecimento {'interrompido' if interrompido else 'concluído'} ({mode}): {feitos}/{len(rows)} chunks"
          + (f" | respostas por provedor: {dict(_USO)}" if _USO else ""))


# --------------------------------------------------------------------------- embeddings / busca
_model = None


def emb_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMB_MODEL)
    return _model


def embed_text(r):
    head = " | ".join(x for x in (r["trilha"], r["titulo"], r["contexto"], r["resumo"]) if x)
    return head + "\n" + r["texto"][:2000]


def embed_pending(con, batch=32):
    import numpy as np
    cur = con.execute("SELECT v FROM meta WHERE k='emb_model'").fetchone()
    if cur and cur["v"] != EMB_MODEL:
        sys.exit(f"Banco já usa o modelo {cur['v']}; limpe os embeddings antes de trocar para {EMB_MODEL}.")
    con.execute("INSERT OR REPLACE INTO meta VALUES('emb_model',?)", (EMB_MODEL,))
    rows = con.execute("SELECT id,trilha,titulo,contexto,resumo,texto FROM chunks WHERE tipo!='indice' AND embedding IS NULL").fetchall()
    m = emb_model()
    for i in range(0, len(rows), batch):
        b = rows[i:i + batch]
        vecs = m.encode(["passage: " + embed_text(r) for r in b], normalize_embeddings=True, batch_size=batch)
        con.executemany("UPDATE chunks SET embedding=? WHERE id=?",
                        [(np.asarray(v, dtype="float32").tobytes(), r["id"]) for r, v in zip(b, vecs)])
        con.commit()
    print(f"embeddings gerados: {len(rows)}")


def search(con, q, k=5, dense=True):
    toks = [t for t in re.findall(r"\w+", q.lower()) if t not in STOP and len(t) > 2]
    bm = []
    if toks:
        fq = " OR ".join(f'"{t}"' for t in toks)
        bm = [r[0] for r in con.execute(
            """SELECT chunks_fts.rowid FROM chunks_fts JOIN chunks c ON c.id=chunks_fts.rowid
               WHERE chunks_fts MATCH ? AND c.tipo!='indice' ORDER BY bm25(chunks_fts) LIMIT 30""", (fq,))]
    dn = []
    if dense:
        try:
            import numpy as np
            rows = con.execute("SELECT id,embedding FROM chunks WHERE embedding IS NOT NULL").fetchall()
            if rows:
                M = np.vstack([np.frombuffer(r["embedding"], dtype="float32") for r in rows])
                qv = emb_model().encode(["query: " + q], normalize_embeddings=True)[0]
                dn = [rows[i]["id"] for i in np.argsort(-(M @ qv))[:30]]
        except ImportError:
            pass
    score = {}
    for lst in (bm, dn):
        for rank, i in enumerate(lst):
            score[i] = score.get(i, 0) + 1 / (60 + rank)
    top = sorted(score, key=score.get, reverse=True)[:k]
    res = []
    for i in top:
        r = con.execute("SELECT c.*, d.titulo AS doc_titulo FROM chunks c JOIN documents d ON d.id=c.doc_id WHERE c.id=?", (i,)).fetchone()
        res.append((score[i], r))
    return res


# --------------------------------------------------------------------------- CLI
def read_sources(args):
    src = list(args.urls_list or [])
    if args.urls:
        src += [l.strip() for l in Path(args.urls).read_text().splitlines() if l.strip() and not l.startswith("#")]
    if args.pasta:
        src += [str(p) for p in sorted(Path(args.pasta).glob("*.pdf"))]
    return list(dict.fromkeys(src))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ingest")
    p.add_argument("urls_list", nargs="*"); p.add_argument("--urls"); p.add_argument("--pasta")
    p.add_argument("--force", action="store_true"); p.add_argument("--enrich", choices=["llm", "heuristic"])
    p.add_argument("--embed", action="store_true")
    p = sub.add_parser("enrich"); p.add_argument("--mode", choices=["llm", "heuristic"], default="llm"); p.add_argument("--limit", type=int)
    sub.add_parser("embed")
    sub.add_parser("providers")
    p = sub.add_parser("models"); p.add_argument("--filtro", default="")
    p = sub.add_parser("search"); p.add_argument("query"); p.add_argument("-k", type=int, default=5); p.add_argument("--no-dense", action="store_true")
    sub.add_parser("stats")
    sub.add_parser("qualidade")
    p = sub.add_parser("export"); p.add_argument("out"); p.add_argument("--with-vectors", action="store_true")
    a = ap.parse_args()
    con = connect()

    if a.cmd == "ingest":
        for s in read_sources(a):
            try:
                ingest(con, s, a.force)
            except Exception as e:  # noqa
                print(f"! erro em {s}: {e}", file=sys.stderr)
        if a.enrich:
            enrich_pending(con, a.enrich)
        if a.embed:
            embed_pending(con)
    elif a.cmd == "enrich":
        enrich_pending(con, a.mode, a.limit)
    elif a.cmd == "embed":
        embed_pending(con)
    elif a.cmd == "providers":
        check_providers()
    elif a.cmd == "models":
        show_models(a.filtro)
    elif a.cmd == "search":
        for sc, r in search(con, a.query, a.k, not a.no_dense):
            print(f"\n[{sc:.4f}] {r['nota_tecnica'] or r['doc_titulo'][:50]} | {r['secao']} {r['titulo'][:90]}")
            print(f"  trilha: {r['trilha']}  (págs {r['pag_ini']}-{r['pag_fim']})")
            print("  " + (r["resumo"] or r["conclusoes"] or r["texto"])[:350].replace("\n", " "))
            if r["link_fonte"]:
                print("  fonte:", r["link_fonte"])
    elif a.cmd == "stats":
        for r in con.execute("SELECT id,titulo,n_paginas,url FROM documents"):
            c = con.execute("""SELECT COUNT(*) n, SUM(tipo='secao') s, SUM(tipo!='indice' AND resumo!='') e,
                               SUM(embedding IS NOT NULL) v FROM chunks WHERE doc_id=?""", (r["id"],)).fetchone()
            print(f"doc {r['id']}: {r['titulo'][:55]!r} | {r['n_paginas']} págs | {c['n']} chunks | {c['s']} seções | enriquecidos {c['e']} | vetores {c['v']}")
    elif a.cmd == "qualidade":
        for r in quality_report(con):
            print(f"\ndoc {r['doc']}: {r['titulo']!r} | {r['paginas']} págs ({r['paginas_cobertas']} cobertas) | {r['chunks']} chunks "
                  f"(mediana {r['tam_mediano']} car., min {r['tam_min']}, máx {r['tam_max']}, {r['curtos_300']} < 300)")
            print(f"  Notas Técnicas: {r['com_nota_tecnica']} (com link: {r['com_link']}) | chunks com notas de rodapé: {r['com_notas_rodape']}")
            print("  ruído residual (chunks):", {k: v for k, v in r['ruido'].items()})
            if r["limpeza"]:
                print("  limpeza:", {k: v for k, v in r['limpeza'].items() if k != 'chunks'})
    elif a.cmd == "export":
        import base64
        with open(a.out, "w", encoding="utf-8") as f:
            for r in con.execute("SELECT c.*, d.url, d.titulo AS doc_titulo FROM chunks c JOIN documents d ON d.id=c.doc_id WHERE c.tipo!='indice'"):
                o = {k: r[k] for k in r.keys() if k not in ("embedding", "texto_hash")}
                if a.with_vectors and r["embedding"]:
                    o["embedding_b64_float32"] = base64.b64encode(r["embedding"]).decode()
                f.write(json.dumps(o, ensure_ascii=False) + "\n")
        print("exportado:", a.out)


if __name__ == "__main__":
    main()