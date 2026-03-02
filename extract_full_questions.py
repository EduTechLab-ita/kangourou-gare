"""
extract_full_questions.py
Estrae screenshot COMPLETI di ogni domanda (testo + immagini + opzioni) dal PDF.
Nuovo approccio: una sola immagine per domanda, pulsanti solo lettere A-E.
"""
import fitz
import re
import os
import json

# ── CONFIGURAZIONE ──────────────────────────────────────────────────────────
TIPO  = "kangourou"   # kangourou | koala | benjamin
ANNO  = "2013"
N_DOM = 24
SCALA = 2.5           # Risoluzione (2.5x ≈ 180 DPI, buona su schermo)
MARGINE_SOPRA = 8     # pt da aggiungere sopra il numero della domanda
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
    return _cerca(re.compile(r'^(\d{1,2})(?!\d)'), con_constraint=True)


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

        clip = fitz.Rect(0, y_top, page_w, y_end)
        mat  = fitz.Matrix(scala, scala)
        pix  = page.get_pixmap(matrix=mat, clip=clip, colorspace=fitz.csRGB)

        fname = f"q{num:02d}.png"
        fpath = os.path.join(output_dir, fname)
        pix.save(fpath)
        salvati.append(fname)
        print(f"  ✅ q{num:02d}.png  (pag {page_num+1}, y={y_start:.0f}–{y_end:.0f})")

    doc.close()
    return salvati


def aggiorna_json(json_path, output_dir, n_dom, tipo, anno, salvati):
    with open(json_path, encoding='utf-8') as f:
        dati = json.load(f)

    # Leggi le risposte corrette dal JSON esistente
    risposte = {}
    for q in dati.get('domande', []):
        risposte[q['id']] = q.get('risposta_corretta', '')

    # Punti per fascia (standard Kangourou Ecolier 24 domande)
    def punti(num):
        if   num <= 8:  return 3
        elif num <= 16: return 4
        else:           return 5

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

    PDF_PATH   = f"pdf/{TIPO}/{ANNO}.pdf"
    OUTPUT_DIR = f"images/{TIPO}-{ANNO}-screenshots"
    JSON_PATH  = f"data/{TIPO}/{ANNO}.json"

    print(f"=== Estrazione screenshot completi: {TIPO} {ANNO} ===\n")

    if not os.path.exists(PDF_PATH):
        print(f"⏭️  PDF non trovato, skip: {PDF_PATH}")
        exit(0)

    if not os.path.exists(JSON_PATH):
        print(f"⏭️  JSON risposte non trovato, skip: {JSON_PATH}")
        exit(0)

    salvati = estrai_screenshots(PDF_PATH, OUTPUT_DIR, N_DOM, SCALA, MARGINE_SOPRA)

    trovate = sum(1 for s in salvati if s is not None)
    if trovate < N_DOM // 2:
        print(f"⏭️  Troppe domande mancanti ({trovate}/{N_DOM}) — formato PDF non supportato, skip.")
        exit(0)

    aggiorna_json(JSON_PATH, OUTPUT_DIR, N_DOM, TIPO, ANNO, salvati)
    aggiorna_index(TIPO, ANNO)

    print(f"\n=== Fatto! Verifica le immagini in: {OUTPUT_DIR}/ ===")
