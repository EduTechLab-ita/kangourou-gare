"""
Pipeline completa per processare una gara Kangourou/Benjamin/Cadet.
Estrae immagini dal PDF e le abbina automaticamente ai quesiti.

Uso: python process_gara.py <pdf_path> <output_folder>
Esempio: python process_gara.py pdf/benjamin/2024.pdf images/benjamin-2024-screenshots

Funziona su layout a colonna (Benjamin, Kangourou/Ecolier, Cadet).
NON funziona su layout a griglia (Koala/Pre-Ecolier).

Fasi:
1. Trova posizioni di tutte le domande nel PDF (pattern "N.")
2. Estrae immagini raster embedded con coordinate
3. Estrae figure vettoriali tramite clustering dei drawings
4. Abbina ogni immagine alla domanda piu vicina per coordinate spaziali
5. Per domande con drawings ma senza immagini estratte → clip PDF (fallback "volo radente")
6. Combina immagini multiple della stessa domanda
7. Salva screenshots finali nella cartella output
"""

import fitz
from PIL import Image
import os
import sys
import json
import re
import io


# === CONFIGURAZIONE ===

# Rendering
DPI = 300
ZOOM = DPI / 72

# Estrazione vettoriale
CLUSTER_GAP = 8          # Distanza max tra path per clustering
MIN_CLUSTER_W = 20       # Dimensione minima cluster (punti PDF)
MIN_CLUSTER_H = 20
MAX_CLUSTER_HEIGHT_PCT = 0.35  # Soglia per split cluster alti

# Filtri
MIN_RASTER_W = 60        # Dimensione minima immagini raster (pixel)
MIN_RASTER_H = 60
MARGIN_LEFT_PCT = 0.06   # Margini pagina da escludere (filtro immagini)
MARGIN_RIGHT_PCT = 0.94
MARGIN_TOP_PCT = 0.04
MARGIN_BOTTOM_PCT = 0.96

CLIP_LEFT_PCT = 0.01     # Margine sinistro per clip PDF (più generoso, include etichette A/B/C/D/E)

# Abbinamento
CLIP_PADDING = 5          # Padding per clip PDF (punti)


# === UTILITA ===

def is_in_margins(rect, page_rect):
    """Controlla se un rettangolo e nelle zone di margine da escludere."""
    pw, ph = page_rect.width, page_rect.height
    if rect.x1 < pw * MARGIN_LEFT_PCT:
        return True
    if rect.x0 > pw * MARGIN_RIGHT_PCT:
        return True
    if rect.y1 < ph * MARGIN_TOP_PCT:
        return True
    if rect.y0 > ph * MARGIN_BOTTOM_PCT:
        return True
    return False


def is_logo_or_junk(width, height):
    """Identifica immagini raster che sono loghi o spazzatura."""
    if 70 <= width <= 80 and 60 <= height <= 70:
        return True
    if width < MIN_RASTER_W or height < MIN_RASTER_H:
        return True
    return False


def cluster_rects(rects, gap):
    """Raggruppa rettangoli vicini in cluster (unione iterativa)."""
    if not rects:
        return []
    merged = [fitz.Rect(r) for r in rects]
    changed = True
    while changed:
        changed = False
        new_merged = []
        used = [False] * len(merged)
        for i in range(len(merged)):
            if used[i]:
                continue
            current = fitz.Rect(merged[i])
            expanded = fitz.Rect(
                current.x0 - gap, current.y0 - gap,
                current.x1 + gap, current.y1 + gap
            )
            for j in range(i + 1, len(merged)):
                if used[j]:
                    continue
                if expanded.intersects(merged[j]):
                    current = current | merged[j]
                    expanded = fitz.Rect(
                        current.x0 - gap, current.y0 - gap,
                        current.x1 + gap, current.y1 + gap
                    )
                    used[j] = True
                    changed = True
            new_merged.append(current)
            used[i] = True
        merged = new_merged
    return merged


def split_tall_cluster(cluster, all_rects, page_height, gap):
    """Se un cluster e troppo alto, prova a dividerlo trovando un gap verticale."""
    if (cluster.y1 - cluster.y0) < page_height * MAX_CLUSTER_HEIGHT_PCT:
        return [cluster]
    contained = []
    expanded_cluster = fitz.Rect(
        cluster.x0 - gap, cluster.y0 - gap,
        cluster.x1 + gap, cluster.y1 + gap
    )
    for r in all_rects:
        if expanded_cluster.contains(r):
            contained.append(r)
    if len(contained) < 2:
        return [cluster]
    contained.sort(key=lambda r: r.y0)
    max_gap = 0
    split_y = None
    for i in range(len(contained) - 1):
        gap_size = contained[i + 1].y0 - contained[i].y1
        if gap_size > max_gap:
            max_gap = gap_size
            split_y = (contained[i].y1 + contained[i + 1].y0) / 2
    if max_gap > 10 and split_y:
        top_rects = [r for r in contained if r.y1 <= split_y]
        bottom_rects = [r for r in contained if r.y0 >= split_y]
        result = []
        for group in [top_rects, bottom_rects]:
            if group:
                union = group[0]
                for r in group[1:]:
                    union = union | r
                result.append(union)
        return result
    return [cluster]


def render_clip(doc, page_num, rect_tuple, padding=None):
    """Renderizza un clip dal PDF come immagine PIL."""
    pad = padding if padding is not None else CLIP_PADDING
    page = doc[page_num]
    x0, y0, x1, y1 = rect_tuple
    clip = fitz.Rect(x0 - pad, y0 - pad, x1 + pad, y1 + pad)
    mat = fitz.Matrix(ZOOM, ZOOM)
    pix = page.get_pixmap(matrix=mat, clip=clip)
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)


def combine_images_vertical(images):
    """Combina immagini in verticale."""
    if len(images) == 1:
        return images[0]
    max_w = max(img.width for img in images)
    total_h = sum(img.height for img in images) + 5 * (len(images) - 1)
    combined = Image.new("RGB", (max_w, total_h), (255, 255, 255))
    y_offset = 0
    for img in images:
        combined.paste(img, (0, y_offset))
        y_offset += img.height + 5
    return combined


# === FASE 1: TROVARE LE DOMANDE ===

def find_questions(doc):
    """
    Trova tutte le domande nel PDF con le loro coordinate.
    Restituisce lista di dict: {num, page, y_start, y_end_zone}
    ordinata per (page, y_start).
    """
    raw_questions = []

    for pg in range(len(doc) - 1):  # Salta ultima pagina (risposte)
        page = doc[pg]
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                text = "".join([s["text"] for s in line["spans"]]).strip()
                m = re.match(r"^(\d+)\.\s", text)
                if m:
                    q_num = int(m.group(1))
                    bbox = line["bbox"]
                    raw_questions.append({
                        "num": q_num,
                        "page": pg,
                        "y_start": bbox[1],
                        "x_start": bbox[0],
                    })

    # Ordina per pagina e posizione Y
    raw_questions.sort(key=lambda q: (q["page"], q["y_start"]))

    # Calcola y_end_zone per ogni domanda (= y_start della domanda successiva sulla stessa pagina)
    questions = []
    for i, q in enumerate(raw_questions):
        # Trova la prossima domanda sulla stessa pagina
        y_end = None
        for j in range(i + 1, len(raw_questions)):
            if raw_questions[j]["page"] == q["page"]:
                y_end = raw_questions[j]["y_start"]
                break

        if y_end is None:
            # Ultima domanda della pagina → zona fino a fine pagina
            y_end = doc[q["page"]].rect.height * MARGIN_BOTTOM_PCT

        # Per la prima domanda della pagina, NON estendere sopra y_start
        # (sopra ci sono intestazione/loghi che non vogliamo)
        y_top = q["y_start"]

        questions.append({
            "num": q["num"],
            "page": q["page"],
            "y_start": q["y_start"],
            "y_top": y_top,       # Inizio zona (puo essere sopra y_start)
            "y_end": y_end,       # Fine zona
        })

    return questions


# === FASE 2: ESTRARRE IMMAGINI CON COORDINATE ===

def extract_raster_with_positions(doc, page_num):
    """Estrae immagini raster dalla pagina con le loro coordinate nel PDF."""
    page = doc[page_num]
    images = []

    for img_info in page.get_images(full=True):
        xref = img_info[0]
        base = doc.extract_image(xref)
        w, h = base["width"], base["height"]

        if is_logo_or_junk(w, h):
            continue

        # Trova la posizione dell'immagine nella pagina
        rects = page.get_image_rects(xref)
        if not rects:
            continue

        for rect in rects:
            if is_in_margins(rect, page.rect):
                continue

            images.append({
                "type": "raster",
                "rect": rect,
                "xref": xref,
                "width": w,
                "height": h,
                "data": base["image"],
                "ext": base["ext"],
                "page": page_num,
            })

    return images


def extract_vector_clusters(doc, page_num):
    """Estrae cluster di figure vettoriali dalla pagina con coordinate."""
    page = doc[page_num]
    page_rect = page.rect
    page_area = page_rect.width * page_rect.height

    drawings = page.get_drawings()
    if not drawings:
        return []

    # Filtra path
    filtered_rects = []
    for d in drawings:
        r = fitz.Rect(d["rect"])
        area = (r.x1 - r.x0) * (r.y1 - r.y0)
        if area > page_area * 0.5 or area < 4:
            continue
        if is_in_margins(r, page_rect):
            continue
        filtered_rects.append(r)

    if not filtered_rects:
        return []

    # Clustering
    clusters = cluster_rects(filtered_rects, CLUSTER_GAP)

    # Filtra e split cluster
    good_clusters = []
    for c in clusters:
        w = c.x1 - c.x0
        h = c.y1 - c.y0
        if w < MIN_CLUSTER_W or h < MIN_CLUSTER_H:
            continue
        if w * h > page_area * 0.4:
            continue
        sub_clusters = split_tall_cluster(c, filtered_rects, page_rect.height, CLUSTER_GAP)
        for sc in sub_clusters:
            sw = sc.x1 - sc.x0
            sh = sc.y1 - sc.y0
            if sw >= MIN_CLUSTER_W and sh >= MIN_CLUSTER_H:
                good_clusters.append(sc)

    return [{"type": "vector", "rect": c, "page": page_num} for c in good_clusters]


def has_drawings_in_zone(doc, page_num, y_top, y_end):
    """Controlla se ci sono drawings significativi in una zona della pagina."""
    page = doc[page_num]
    drawings = page.get_drawings()
    if not drawings:
        return False

    count = 0
    for d in drawings:
        r = fitz.Rect(d["rect"])
        cy = (r.y0 + r.y1) / 2
        if y_top <= cy <= y_end:
            area = (r.x1 - r.x0) * (r.y1 - r.y0)
            if area > 10:  # Non puntini
                count += 1

    return count >= 3  # Almeno 3 drawings → probabilmente una figura


# === FASE 3: ABBINAMENTO ===

def match_images_to_questions(questions, all_images):
    """
    Abbina immagini alle domande per prossimita spaziale.
    Un'immagine appartiene alla domanda N se il suo centro Y
    cade nella zona [y_top, y_end) della domanda N sulla stessa pagina.
    """
    assignments = {q["num"]: [] for q in questions}

    for img in all_images:
        img_page = img["page"]
        rect = img["rect"]
        img_cy = (rect.y0 + rect.y1) / 2

        best_q = None
        for q in questions:
            if q["page"] != img_page:
                continue
            if q["y_top"] <= img_cy < q["y_end"]:
                best_q = q["num"]
                break

        if best_q is None:
            # Fallback: assegna alla domanda piu vicina sulla stessa pagina
            min_dist = float("inf")
            for q in questions:
                if q["page"] != img_page:
                    continue
                dist = abs(img_cy - q["y_start"])
                if dist < min_dist:
                    min_dist = dist
                    best_q = q["num"]

        if best_q is not None:
            assignments[best_q].append(img)

    return assignments


# === FASE 4: GENERAZIONE IMMAGINI FINALI ===

def render_image(doc, img_info):
    """Renderizza un'immagine (raster o vettoriale) come PIL Image."""
    if img_info["type"] == "raster":
        data = img_info["data"]
        return Image.open(io.BytesIO(data)).convert("RGB")
    else:
        # Vettoriale: clip dal PDF
        rect = img_info["rect"]
        return render_clip(doc, img_info["page"],
                          (rect.x0, rect.y0, rect.x1, rect.y1))


def generate_question_image(doc, q, images, all_images):
    """
    Genera l'immagine finale per una domanda.
    - Se ci sono immagini assegnate → le usa (singola o combinata)
    - Se non ci sono ma ci sono drawings nella zona → clip PDF (volo radente)
    - Altrimenti → None (domanda solo testo)
    """
    use_clip = False

    # Se troppe immagini (>3), il match singolo e inaffidabile → clip PDF
    if len(images) > 3:
        use_clip = True

    if images and not use_clip:
        images.sort(key=lambda i: (i["rect"].y0, i["rect"].x0))

        # Per cluster vettoriali: bounding box totale con padding asimmetrico.
        # +25pt sinistra (etichette A/B/C/D/E), +25pt basso (etichette sotto figure).
        # NON si usa clip_pdf: includerebbe testo domanda e domande adiacenti.
        if all(img["type"] == "vector" for img in images):
            x0 = min(img["rect"].x0 for img in images)
            x1 = max(img["rect"].x1 for img in images)
            y0 = min(img["rect"].y0 for img in images)
            y1 = max(img["rect"].y1 for img in images)
            page_obj = doc[images[0]["page"]]
            clip = fitz.Rect(
                max(0, x0 - 25),
                max(0, y0 - 5),
                min(page_obj.rect.width, x1 + 5),
                min(page_obj.rect.height, y1 + 25),
            )
            mat = fitz.Matrix(ZOOM, ZOOM)
            pix = page_obj.get_pixmap(matrix=mat, clip=clip)
            return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # Immagini raster: estrazione diretta
        rendered = [render_image(doc, img) for img in images]
        if len(rendered) == 1:
            return rendered[0]
        else:
            return combine_images_vertical(rendered)

    # Nessuna immagine estratta, o troppe → clip PDF se ci sono drawings
    has_content = use_clip or has_drawings_in_zone(doc, q["page"], q["y_top"], q["y_end"])
    if has_content:
        # Clip generoso della zona domanda (tecnica "volo radente")
        page = doc[q["page"]]
        x0 = page.rect.width * CLIP_LEFT_PCT
        x1 = page.rect.width * MARGIN_RIGHT_PCT
        y0 = q["y_start"]
        y1 = q["y_end"]
        return render_clip(doc, q["page"], (x0, y0, x1, y1), padding=2)

    return None


# === MAIN ===

def process_gara(pdf_path, output_folder):
    """Processa una gara completa: PDF → immagini screenshots."""
    pdf_name = os.path.basename(pdf_path)
    print(f"\n{'=' * 60}")
    print(f"  PROCESSO GARA: {pdf_name}")
    print(f"{'=' * 60}\n")

    os.makedirs(output_folder, exist_ok=True)
    doc = fitz.open(pdf_path)

    # Fase 1: Trova domande
    print("[1/4] Ricerca domande nel PDF...")
    questions = find_questions(doc)
    print(f"  Trovate {len(questions)} domande")
    for q in questions:
        print(f"    Q{q['num']}: pag {q['page']+1}, y={q['y_start']:.0f} (zona {q['y_top']:.0f}-{q['y_end']:.0f})")

    if not questions:
        print("  ERRORE: Nessuna domanda trovata! Formato PDF non supportato.")
        doc.close()
        return None

    # Fase 2: Estrai immagini
    print("\n[2/4] Estrazione immagini...")
    all_images = []
    pages_to_process = len(doc) - 1  # Salta ultima pagina (risposte)

    for pg in range(pages_to_process):
        rasters = extract_raster_with_positions(doc, pg)
        vectors = extract_vector_clusters(doc, pg)
        all_images.extend(rasters)
        all_images.extend(vectors)
        if rasters or vectors:
            print(f"  Pag {pg+1}: {len(rasters)} raster, {len(vectors)} vettoriali")

    print(f"  Totale: {len(all_images)} immagini estratte")

    # Fase 3: Abbinamento
    print("\n[3/4] Abbinamento immagini ai quesiti...")
    assignments = match_images_to_questions(questions, all_images)

    with_images = sum(1 for imgs in assignments.values() if imgs)
    print(f"  {with_images} domande con immagini estratte")

    # Fase 4: Generazione screenshots
    print("\n[4/4] Generazione screenshots finali...")
    report = {
        "pdf": pdf_name,
        "questions_total": len(questions),
        "questions_with_images": 0,
        "details": []
    }

    for q in questions:
        q_num = q["num"]
        imgs = assignments.get(q_num, [])

        result_img = generate_question_image(doc, q, imgs, all_images)

        if result_img is not None:
            fname = f"q{q_num:02d}.png"
            fpath = os.path.join(output_folder, fname)
            result_img.save(fpath)
            report["questions_with_images"] += 1

            method = "extracted"
            if not imgs or len(imgs) > 3:
                method = "clip_pdf"
            elif len(imgs) > 1:
                method = f"combined_{len(imgs)}"

            print(f"  Q{q_num}: {fname} ({result_img.size[0]}x{result_img.size[1]}) [{method}]")
            report["details"].append({
                "question": q_num,
                "file": fname,
                "method": method,
                "size": f"{result_img.size[0]}x{result_img.size[1]}"
            })
        else:
            print(f"  Q{q_num}: (nessuna immagine)")
            report["details"].append({
                "question": q_num,
                "file": None,
                "method": "no_image",
            })

    doc.close()

    # Fase 5: Validazione automatica
    print("\n[5/5] Validazione immagini...")
    warnings = []

    for detail in report["details"]:
        q_num = detail["question"]
        fname = detail.get("file")

        if fname is None:
            continue

        fpath = os.path.join(output_folder, fname)
        try:
            img = Image.open(fpath)
            w, h = img.size

            # Controllo 1: immagine troppo piccola (probabilmente spazzatura)
            if w < 50 or h < 50:
                msg = f"Q{q_num}: immagine troppo piccola ({w}x{h})"
                warnings.append(msg)
                print(f"  WARN: {msg}")
                continue

            # Controllo 2: immagine troppo stretta (probabilmente un frammento)
            if w < 80 and h > w * 5:
                msg = f"Q{q_num}: immagine troppo stretta ({w}x{h}), possibile frammento"
                warnings.append(msg)
                print(f"  WARN: {msg}")

            # Controllo 3: immagine quasi tutta bianca (vuota)
            pixels = list(img.getdata())
            total = len(pixels)
            white_count = sum(1 for p in pixels if (p[0] > 240 and p[1] > 240 and p[2] > 240) if isinstance(p, tuple))
            if isinstance(pixels[0], tuple):
                white_pct = white_count / total
            else:
                white_pct = sum(1 for p in pixels if p > 240) / total

            if white_pct > 0.98:
                msg = f"Q{q_num}: immagine quasi vuota ({white_pct:.0%} bianca)"
                warnings.append(msg)
                print(f"  WARN: {msg}")

            # Controllo 4: dimensioni sospette (troppo grande = probabilmente ha troppo contenuto)
            if w > 2000 and h > 2000:
                msg = f"Q{q_num}: immagine molto grande ({w}x{h}), potrebbe includere troppo"
                warnings.append(msg)
                print(f"  WARN: {msg}")

            detail["validated"] = True
            detail["warnings"] = []

        except Exception as e:
            msg = f"Q{q_num}: errore lettura immagine: {e}"
            warnings.append(msg)
            print(f"  WARN: {msg}")

    # Aggiungi warnings ai dettagli
    for w_msg in warnings:
        q_num_str = w_msg.split(":")[0]  # "Q5"
        q_num = int(q_num_str[1:])
        for detail in report["details"]:
            if detail["question"] == q_num:
                if "warnings" not in detail:
                    detail["warnings"] = []
                detail["warnings"].append(w_msg)

    report["warnings"] = warnings
    report["warnings_count"] = len(warnings)

    if not warnings:
        print("  Tutte le immagini superano la validazione")
    else:
        print(f"  {len(warnings)} warning trovati")

    # Salva report
    report_path = os.path.join(output_folder, "process_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"  COMPLETATO: {report['questions_with_images']}/{report['questions_total']} domande con immagini")
    if warnings:
        print(f"  WARNING: {len(warnings)} problemi trovati (vedi report)")
    else:
        print(f"  VALIDAZIONE: OK, nessun problema")
    print(f"  Output: {output_folder}")
    print(f"  Report: {report_path}")
    print(f"{'=' * 60}\n")

    return report


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python process_gara.py <pdf_path> <output_folder>")
        print("Esempio: python process_gara.py pdf/benjamin/2024.pdf images/benjamin-2024-screenshots")
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_folder = sys.argv[2]

    if not os.path.exists(pdf_path):
        print(f"ERRORE: File non trovato: {pdf_path}")
        sys.exit(1)

    process_gara(pdf_path, output_folder)
