"""
Script per estrarre TUTTE le immagini (raster + vettoriali) dai PDF Kangourou.
Combina get_images() per immagini embedded e get_drawings() per figure vettoriali.

Uso: python extract_all_images.py <pdf_path> <output_folder>
Esempio: python extract_all_images.py pdf/benjamin/2024.pdf images/benjamin-2024-extracted
"""

import fitz  # PyMuPDF
from PIL import Image
import os
import sys
import json


# === CONFIGURAZIONE ===

# Zoom per rendering pagina (3x = buona qualità)
RENDER_ZOOM = 3.0

# Padding attorno alle figure ritagliate (in punti PDF)
CROP_PADDING = 8

# Gap per clustering: distanza massima tra path per considerarli parte della stessa figura
CLUSTER_GAP = 8

# Dimensioni minime cluster (in punti PDF)
MIN_CLUSTER_W = 20
MIN_CLUSTER_H = 20

# Dimensioni minime immagini raster da tenere (in pixel)
MIN_RASTER_W = 60
MIN_RASTER_H = 60

# Margini pagina da escludere (percentuale della larghezza/altezza)
MARGIN_LEFT_PCT = 0.06    # Escludi scritta laterale sinistra (es. "BENJAMIN")
MARGIN_RIGHT_PCT = 0.92   # Escludi scritta laterale destra
MARGIN_TOP_PCT = 0.04     # Escludi decorazioni in alto
MARGIN_BOTTOM_PCT = 0.96  # Escludi piè di pagina

# Soglia per dividere cluster troppo alti (% altezza pagina)
MAX_CLUSTER_HEIGHT_PCT = 0.35


def is_in_margins(rect, page_rect):
    """Controlla se un rettangolo è nelle zone di margine da escludere."""
    pw, ph = page_rect.width, page_rect.height
    cx = (rect.x0 + rect.x1) / 2  # centro x del rect
    cy = (rect.y0 + rect.y1) / 2  # centro y del rect

    # Completamente nella fascia sinistra (scritta "BENJAMIN" verticale)
    if rect.x1 < pw * MARGIN_LEFT_PCT:
        return True
    # Completamente nella fascia destra
    if rect.x0 > pw * MARGIN_RIGHT_PCT:
        return True
    # Completamente nella fascia superiore (decorazioni)
    if rect.y1 < ph * MARGIN_TOP_PCT:
        return True
    # Completamente nella fascia inferiore (piè di pagina, logo kangourou)
    if rect.y0 > ph * MARGIN_BOTTOM_PCT:
        return True

    return False


def is_logo_or_junk(width, height, img_bytes_len):
    """Identifica immagini raster che sono loghi o spazzatura."""
    # Logo kangourou piccolo: sempre circa 75x66
    if 70 <= width <= 80 and 60 <= height <= 70:
        return True
    # Immagini troppo piccole (icone, decorazioni)
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
                    current = current | merged[j]  # union
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
    """
    Se un cluster è troppo alto, prova a dividerlo trovando un gap verticale.
    Restituisce una lista di sotto-cluster.
    """
    if (cluster.y1 - cluster.y0) < page_height * MAX_CLUSTER_HEIGHT_PCT:
        return [cluster]

    # Trova i rect originali dentro questo cluster
    contained = []
    for r in all_rects:
        expanded_cluster = fitz.Rect(
            cluster.x0 - gap, cluster.y0 - gap,
            cluster.x1 + gap, cluster.y1 + gap
        )
        if expanded_cluster.contains(r):
            contained.append(r)

    if len(contained) < 2:
        return [cluster]

    # Ordina per y0 e cerca il gap verticale più grande
    contained.sort(key=lambda r: r.y0)
    max_gap = 0
    split_y = None

    for i in range(len(contained) - 1):
        gap_size = contained[i + 1].y0 - contained[i].y1
        if gap_size > max_gap:
            max_gap = gap_size
            split_y = (contained[i].y1 + contained[i + 1].y0) / 2

    # Se il gap è significativo (> 10 punti), dividi
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


def extract_raster_images(doc, page_num):
    """Estrae immagini raster embedded dalla pagina."""
    page = doc[page_num]
    images = []

    for img_info in page.get_images(full=True):
        xref = img_info[0]
        base = doc.extract_image(xref)
        w, h = base["width"], base["height"]
        ext = base["ext"]
        img_bytes = base["image"]

        if is_logo_or_junk(w, h, len(img_bytes)):
            continue

        images.append({
            "type": "raster",
            "width": w,
            "height": h,
            "ext": ext,
            "data": img_bytes,
            "page": page_num + 1
        })

    return images


def extract_vector_figures(doc, page_num):
    """Estrae figure vettoriali dalla pagina tramite clustering dei drawings."""
    page = doc[page_num]
    page_rect = page.rect
    page_area = page_rect.width * page_rect.height

    drawings = page.get_drawings()
    if not drawings:
        return []

    # Filtra i path: escludi quelli troppo grandi, troppo piccoli, o nei margini
    filtered_rects = []
    for d in drawings:
        r = fitz.Rect(d["rect"])
        area = (r.x1 - r.x0) * (r.y1 - r.y0)

        # Troppo grande (bordo pagina intero)
        if area > page_area * 0.5:
            continue
        # Troppo piccolo (puntino)
        if area < 4:
            continue
        # Nei margini
        if is_in_margins(r, page_rect):
            continue

        filtered_rects.append(r)

    if not filtered_rects:
        return []

    # Clustering
    clusters = cluster_rects(filtered_rects, CLUSTER_GAP)

    # Filtra cluster troppo piccoli o troppo grandi
    good_clusters = []
    for c in clusters:
        w = c.x1 - c.x0
        h = c.y1 - c.y0
        if w < MIN_CLUSTER_W or h < MIN_CLUSTER_H:
            continue
        if w * h > page_area * 0.4:
            continue

        # Prova a dividere cluster troppo alti
        sub_clusters = split_tall_cluster(c, filtered_rects, page_rect.height, CLUSTER_GAP)
        for sc in sub_clusters:
            sw = sc.x1 - sc.x0
            sh = sc.y1 - sc.y0
            if sw >= MIN_CLUSTER_W and sh >= MIN_CLUSTER_H:
                good_clusters.append(sc)

    # Renderizza la pagina per ritagliare
    mat = fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM)
    pix = page.get_pixmap(matrix=mat)
    page_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    figures = []
    for c in good_clusters:
        # Converti coordinate PDF in pixel
        px0 = max(0, int((c.x0 - CROP_PADDING) * RENDER_ZOOM))
        py0 = max(0, int((c.y0 - CROP_PADDING) * RENDER_ZOOM))
        px1 = min(pix.width, int((c.x1 + CROP_PADDING) * RENDER_ZOOM))
        py1 = min(pix.height, int((c.y1 + CROP_PADDING) * RENDER_ZOOM))

        crop = page_img.crop((px0, py0, px1, py1))

        figures.append({
            "type": "vector",
            "rect_pdf": (round(c.x0, 1), round(c.y0, 1), round(c.x1, 1), round(c.y1, 1)),
            "width": px1 - px0,
            "height": py1 - py0,
            "image": crop,
            "page": page_num + 1
        })

    return figures


def process_pdf(pdf_path, output_folder):
    """Processa un PDF completo ed estrae tutte le immagini."""
    print(f"\n{'=' * 60}")
    print(f"  ESTRAZIONE IMMAGINI: {os.path.basename(pdf_path)}")
    print(f"{'=' * 60}\n")

    os.makedirs(output_folder, exist_ok=True)

    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    # L'ultima pagina è spesso la griglia risposte → la saltiamo
    pages_to_process = total_pages - 1

    all_images = []
    report = {"pdf": os.path.basename(pdf_path), "pages": total_pages, "images": []}

    img_counter = 0

    for pg in range(pages_to_process):
        print(f"[Pagina {pg + 1}/{pages_to_process}]")

        # 1. Immagini raster
        raster_imgs = extract_raster_images(doc, pg)
        for ri in raster_imgs:
            img_counter += 1
            fname = f"img_{img_counter:03d}_p{pg + 1}_raster.{ri['ext']}"
            fpath = os.path.join(output_folder, fname)

            with open(fpath, "wb") as f:
                f.write(ri["data"])

            entry = {
                "filename": fname,
                "type": "raster",
                "page": ri["page"],
                "size": f"{ri['width']}x{ri['height']}",
                "question": None  # Da assegnare manualmente o con AI
            }
            report["images"].append(entry)
            print(f"   + Raster: {fname} ({ri['width']}x{ri['height']})")

        # 2. Figure vettoriali
        vector_figs = extract_vector_figures(doc, pg)
        for vf in vector_figs:
            img_counter += 1
            fname = f"img_{img_counter:03d}_p{pg + 1}_vector.png"
            fpath = os.path.join(output_folder, fname)

            vf["image"].save(fpath)

            entry = {
                "filename": fname,
                "type": "vector",
                "page": vf["page"],
                "size": f"{vf['width']}x{vf['height']}",
                "rect_pdf": vf["rect_pdf"],
                "question": None
            }
            report["images"].append(entry)
            print(f"   + Vector: {fname} ({vf['width']}x{vf['height']})")

    doc.close()

    # Salva report JSON
    report_path = os.path.join(output_folder, "extraction_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"  OK: COMPLETATO: {img_counter} immagini estratte")
    print(f"  Report: Report: {report_path}")
    print(f"{'=' * 60}\n")

    return report


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python extract_all_images.py <pdf_path> <output_folder>")
        print("Esempio: python extract_all_images.py pdf/benjamin/2024.pdf images/benjamin-2024-extracted")
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_folder = sys.argv[2]

    if not os.path.exists(pdf_path):
        print(f"ERRORE: File non trovato: {pdf_path}")
        sys.exit(1)

    process_pdf(pdf_path, output_folder)
