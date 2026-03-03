"""
extract_full_questions.py
Estrae screenshot COMPLETI di ogni domanda (testo + immagini + opzioni) dal PDF.
Nuovo approccio: una sola immagine per domanda, pulsanti solo lettere A-E.
"""
import sys
import fitz
import re
import os
import json
import urllib.request

# Fix encoding emoji su terminale Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# URL con fallback: lista di pattern in ordine di priorità
URL_PDF_PATTERNS = {
    "kangourou": ["https://www.kangourou.it/images/TestiGare/{anno}/EcolierMarzo-{anno2}.pdf"],
    "koala":     ["https://www.kangourou.it/images/TestiGare/{anno}/PreEcolierMarzo-{anno2}.pdf"],
    "benjamin":  [
        "https://www.kangourou.it/images/TestiGare/{anno}/Benjamin{anno}REL.pdf",  # 2021+
        "https://www.kangourou.it/images/TestiGare/{anno}/BMarzo-{anno2}.pdf",     # 2000-2020
    ],
    "cadet": [
        "https://www.kangourou.it/images/TestiGare/{anno}/Cadet{anno}REL.pdf",     # 2021+
        "https://www.kangourou.it/images/TestiGare/{anno}/CMarzo-{anno2}.pdf",     # 2000-2020
    ],
}
# Compatibilità (usato solo per riferimento)
URL_PDF = {k: v[0] for k, v in URL_PDF_PATTERNS.items()}


def scarica_pdf(tipo, anno, pdf_path):
    """Scarica il PDF da kangourou.it se non esiste già. Prova più URL in sequenza."""
    if os.path.exists(pdf_path):
        return True
    if tipo not in URL_PDF_PATTERNS:
        return False
    anno2 = str(anno)[-2:]
    patterns = URL_PDF_PATTERNS[tipo]
    for pattern in patterns:
        url = pattern.format(anno=anno, anno2=anno2)
        print(f"   Download: {url.split('/')[-1]}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
            with open(pdf_path, "wb") as f:
                f.write(data)
            print(f"   ✅ Scaricato ({len(data)//1024} KB)")
            return True
        except Exception:
            continue
    print(f"   ❌ Nessun URL disponibile per {tipo} {anno}")
    return False

# ── CONFIGURAZIONE ──────────────────────────────────────────────────────────
TIPO  = "kangourou"   # kangourou | koala | benjamin | cadet
ANNO  = "2013"
N_DOM = None          # None = auto (30 per benjamin/cadet, 24 per kangourou/koala)
SCALA = 2.5           # Risoluzione (2.5x ≈ 180 DPI, buona su schermo)
MARGINE_SOPRA = 8     # pt da aggiungere sopra il numero della domanda

N_DOM_PER_TIPO = {"kangourou": 24, "koala": 24, "benjamin": 30, "cadet": 30}
CATEGORIA_PER_TIPO = {"kangourou": "Ecolier", "koala": "Pre-Ecolier", "benjamin": "Benjamin", "cadet": "Cadet"}
DURATA_PER_TIPO = {"kangourou": 75, "koala": 75, "benjamin": 75, "cadet": 75}
# ─────────────────────────────────────────────────────────────────────────────

PDF_PATH   = f"pdf/{TIPO}/{ANNO}.pdf"
OUTPUT_DIR = f"images/{TIPO}-{ANNO}-screenshots"
JSON_PATH  = f"data/{TIPO}/{ANNO}.json"


def trova_coordinate_domande(doc, n_dom):
    """Cerca i pattern 'N. testo' (kangourou) o 'N' solo (koala) e restituisce {num: (page_num, y_top)}.
    Primo tentativo: pattern con punto (sicuro, nessun falso positivo).
    Fallback: pattern senza punto + constraint 80% altezza pagina (formato koala)."""

    def _cerca(pattern, con_constraint):
        coords = {}
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_h = page.rect.height
            for b in page.get_text('blocks'):
                txt = b[4].strip()
                if 'risposta' in txt[:30].lower():
                    continue
                m = pattern.match(txt)
                if m:
                    num = int(m.group(1))
                    if con_constraint and b[1] >= page_h * 0.80:
                        continue
                    if 1 <= num <= n_dom and num not in coords:
                        coords[num] = (page_num, b[1])
        return coords

    # Tentativo 1: pattern con punto (formato kangourou: "1. testo" o "1.")
    coords = _cerca(re.compile(r'^(\d{1,2})\.(?:\s*\S|$)'), con_constraint=False)
    if len(coords) >= n_dom // 2:
        return coords

    # Fallback: pattern permissivo con constraint y < 80% pagina (formato koala)
    # Esclude anche "/" dopo il numero (evita date tipo "15/5/2050" nelle opzioni)
    return _cerca(re.compile(r'^(\d{1,2})(?![0-9/])'), con_constraint=True)


def estrai_screenshots(pdf_path, output_dir, n_dom, scala, margine):
    doc = fitz.open(pdf_path)
    os.makedirs(output_dir, exist_ok=True)

    coords = trova_coordinate_domande(doc, n_dom)
    print(f"Trovate {len(coords)}/{n_dom} domande nel PDF.")

    salvati = []
    for num in range(1, n_dom + 1):
        if num not in coords:
            print(f"  ⚠️  Domanda {num} non trovata nel PDF!")
            salvati.append(None)
            continue

        page_num, y_start = coords[num]
        page = doc[page_num]
        page_h = page.rect.height
        page_w = page.rect.width

        # Y di fine: inizio domanda successiva (stessa pagina) o fine pagina
        y_end = page_h
        for next_num in range(num + 1, n_dom + 2):
            if next_num in coords:
                np, ny = coords[next_num]
                if np == page_num:
                    y_end = ny - 5
                break

        # Se siamo a fine pagina (ultima domanda), taglia dopo l'ultimo contenuto visibile
        if y_end == page_h:
            ultimo_y = y_start
            # Testo
            for b in page.get_text('blocks'):
                if b[1] >= y_start and b[3] <= page_h:
                    ultimo_y = max(ultimo_y, b[3])
            # Immagini raster
            for img in page.get_image_info():
                y1 = img['bbox'][3]
                if img['bbox'][1] >= y_start and y1 <= page_h:
                    ultimo_y = max(ultimo_y, y1)
            # Disegni vettoriali (includi se arrivano oltre y_start)
            for path in page.get_drawings():
                y1 = path['rect'].y1
                if path['rect'].y1 > y_start and y1 <= page_h:
                    ultimo_y = max(ultimo_y, y1)
            if ultimo_y > y_start:
                y_end = min(page_h, ultimo_y + 20)

        y_top = max(0, y_start - margine)

        # Salta se rettangolo non valido (formato PDF non supportato)
        if y_end <= y_top + 10:
            print(f"  ⚠️  q{num:02d}: rettangolo non valido (y_top={y_top:.0f}, y_end={y_end:.0f}), skip")
            salvati.append(None)
            continue

        mat = fitz.Matrix(scala, scala)
        fname = f"q{num:02d}.png"
        fpath = os.path.join(output_dir, fname)

        # Verifica se la domanda successiva è su una pagina diversa (domanda a cavallo di pagina)
        next_page_num = None
        next_y_start  = None
        for next_num in range(num + 1, n_dom + 2):
            if next_num in coords:
                next_page_num, next_y_start = coords[next_num]
                break

        if y_end >= page_h - 5 and next_page_num is not None and next_page_num > page_num:
            # Domanda a cavallo di pagina: unisci parte bassa pagina corrente + parte alta pagina successiva
            next_page = doc[next_page_num]
            next_page_w = next_page.rect.width
            y_end_next = next_y_start - 5  # fino all'inizio della domanda successiva

            pix1 = page.get_pixmap(matrix=mat, clip=fitz.Rect(0, y_top, page_w, page_h), colorspace=fitz.csRGB)
            pix2 = next_page.get_pixmap(matrix=mat, clip=fitz.Rect(0, 0, next_page_w, max(y_end_next, 5)), colorspace=fitz.csRGB)

            # Unisci verticalmente le due immagini
            import PIL.Image, io
            img1 = PIL.Image.open(io.BytesIO(pix1.tobytes("png")))
            img2 = PIL.Image.open(io.BytesIO(pix2.tobytes("png")))
            w = max(img1.width, img2.width)
            combined = PIL.Image.new("RGB", (w, img1.height + img2.height), (255, 255, 255))
            combined.paste(img1, (0, 0))
            combined.paste(img2, (0, img1.height))
            combined.save(fpath)
            print(f"  ✅ q{num:02d}.png  (pag {page_num+1}→{next_page_num+1}, cross-page)")
        else:
            clip = fitz.Rect(0, y_top, page_w, y_end)
            pix  = page.get_pixmap(matrix=mat, clip=clip, colorspace=fitz.csRGB)
            pix.save(fpath)
            print(f"  ✅ q{num:02d}.png  (pag {page_num+1}, y={y_start:.0f}–{y_end:.0f})")

        salvati.append(fname)

    doc.close()
    return salvati


def aggiorna_json(json_path, output_dir, n_dom, tipo, anno, salvati):
    with open(json_path, encoding='utf-8') as f:
        dati = json.load(f)

    # Leggi le risposte corrette dal JSON esistente
    risposte = {}
    for q in dati.get('domande', []):
        r = q.get('risposta_corretta', '')
        if r:
            risposte[q['id']] = r

    # Se mancano risposte, tenta di estrarle dall'ultima pagina del PDF
    if len(risposte) < n_dom:
        pdf_path = f"pdf/{tipo}/{anno}.pdf"
        if os.path.exists(pdf_path):
            try:
                doc = fitz.open(pdf_path)
                txt = doc[-1].get_text()
                doc.close()
                tutte = re.findall(r'\b([A-E])\b', txt)
                if len(tutte) >= n_dom:
                    for i, r in enumerate(tutte[:n_dom], 1):
                        if i not in risposte:
                            risposte[i] = r
                    print(f"   Risposte integrate dall'ultima pagina PDF ({len(risposte)}/{n_dom})")
            except Exception as e:
                print(f"   ⚠️  Impossibile leggere risposte da PDF: {e}")

    # Punti per fascia (proporzionale: n_dom/3 per ogni fascia — vale per 24 e 30 domande)
    fascia = n_dom // 3
    def punti(num):
        if   num <= fascia:     return 3
        elif num <= fascia * 2: return 4
        else:                   return 5

    opzioni_base = [{"id": "A"}, {"id": "B"}, {"id": "C"}, {"id": "D"}, {"id": "E"}]

    nuove_domande = []
    for num in range(1, n_dom + 1):
        img_file = salvati[num - 1]
        img_path = f"images/{tipo}-{anno}-screenshots/{img_file}" if img_file else None
        nuove_domande.append({
            "id":               num,
            "immagine":         img_path,
            "risposta_corretta": risposte.get(num, ""),
            "punteggio":        punti(num),
            "opzioni":          opzioni_base
        })

    dati['screenshot_mode'] = True
    dati['domande']         = nuove_domande

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(dati, f, ensure_ascii=False, indent=2)
    print(f"\n✅ JSON aggiornato: {json_path}")
    print(f"   screenshot_mode: true, {n_dom} domande, opzioni solo lettera")


def crea_json_da_pdf(pdf_path, json_path, n_dom, tipo, anno):
    """Crea il JSON base estraendo le risposte corrette dall'ultima pagina del PDF."""
    doc = fitz.open(pdf_path)
    txt = doc[-1].get_text()
    doc.close()

    risposte = re.findall(r'\b([A-E])\b', txt)
    if len(risposte) < n_dom:
        print(f"⚠️  Trovate solo {len(risposte)} risposte nell'ultima pagina (attese {n_dom}). Verificare manualmente.")
        return False
    risposte = risposte[:n_dom]

    fascia = n_dom // 3
    def punti(num):
        if   num <= fascia:     return 3
        elif num <= fascia * 2: return 4
        else:                   return 5

    titoli = {"kangourou": "Kangourou", "koala": "Koala", "benjamin": "Benjamin", "cadet": "Cadet"}
    dati = {
        'id':            f'{tipo}-{anno}',
        'titolo':        f'{titoli.get(tipo, tipo.capitalize())} {anno}',
        'anno':          int(anno),
        'categoria':     CATEGORIA_PER_TIPO.get(tipo, tipo.capitalize()),
        'durata_minuti': DURATA_PER_TIPO.get(tipo, 75),
        'domande':       [{'id': i+1, 'risposta_corretta': r, 'punteggio': punti(i+1)}
                          for i, r in enumerate(risposte)]
    }
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(dati, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON creato da PDF: {json_path}  ({n_dom} risposte estratte)")
    return True


def aggiorna_index(tipo, anno):
    """Mette disponibile: true per la gara nel catalogo index.json."""
    index_path = 'index.json'
    with open(index_path, encoding='utf-8') as f:
        index = json.load(f)
    gara_id = f"{tipo}-{anno}"
    for gara in index['gare']:
        if gara['id'] == gara_id:
            gara['disponibile'] = True
            break
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"✅ index.json: {gara_id} → disponibile: true")


# ── MAIN ────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        ANNO = sys.argv[1]
    if len(sys.argv) > 2:
        TIPO = sys.argv[2]
    if len(sys.argv) > 3:
        N_DOM = int(sys.argv[3])
    # Auto N_DOM se non specificato
    if N_DOM is None:
        N_DOM = N_DOM_PER_TIPO.get(TIPO, 24)

    PDF_PATH   = f"pdf/{TIPO}/{ANNO}.pdf"
    OUTPUT_DIR = f"images/{TIPO}-{ANNO}-screenshots"
    JSON_PATH  = f"data/{TIPO}/{ANNO}.json"

    print(f"=== Estrazione screenshot completi: {TIPO} {ANNO} ===\n")

    # Controlla se la gara è marcata come formato incompatibile in index.json
    gara_id = f"{TIPO}-{ANNO}"
    try:
        with open('index.json', encoding='utf-8') as f:
            _idx = json.load(f)
        for _g in _idx.get('gare', []):
            if _g['id'] == gara_id and _g.get('formato_incompatibile'):
                print(f"⏭️  Formato PDF incompatibile (già verificato), skip: {gara_id}")
                exit(0)
    except Exception:
        pass

    if not os.path.exists(PDF_PATH):
        print(f"📥 PDF non trovato — tento download automatico...")
        if not scarica_pdf(TIPO, ANNO, PDF_PATH):
            print(f"⏭️  PDF non disponibile, skip: {PDF_PATH}")
            exit(0)

    if not os.path.exists(JSON_PATH):
        print(f"📋 JSON non trovato — estraggo risposte dall'ultima pagina del PDF...")
        if not crea_json_da_pdf(PDF_PATH, JSON_PATH, N_DOM, TIPO, ANNO):
            print(f"⏭️  Impossibile creare JSON automaticamente, skip.")
            exit(0)

    salvati = estrai_screenshots(PDF_PATH, OUTPUT_DIR, N_DOM, SCALA, MARGINE_SOPRA)

    trovate = sum(1 for s in salvati if s is not None)
    if trovate < N_DOM // 2:
        print(f"⏭️  Troppe domande mancanti ({trovate}/{N_DOM}) — formato PDF non supportato, skip.")
        exit(0)

    aggiorna_json(JSON_PATH, OUTPUT_DIR, N_DOM, TIPO, ANNO, salvati)
    aggiorna_index(TIPO, ANNO)

    print(f"\n=== Fatto! Verifica le immagini in: {OUTPUT_DIR}/ ===")
