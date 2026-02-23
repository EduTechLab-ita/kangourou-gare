#!/usr/bin/env python3
"""
batch_publish.py - Orchestratore batch per Kangourou Trainer
=====================================================
Processa N gare dalla coda batch_queue.json:
  1. Scarica PDF da kangourou.it (se needs_download=true)
  2. Estrae immagini con process_gara.py
  3. Estrae JSON domande con Gemini AI
  4. Aggiorna index.json e sw.js
  5. Genera report in output/batch_report.md

Uso:
    python batch_publish.py [--batch-size N] [--dry-run] [--skip-images] [--skip-json]

Variabile d'ambiente richiesta (se gemini_json_extractor.py non presente in locale):
    GEMINI_API_KEY = "la tua chiave API Gemini"
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).parent

# URL pattern kangourou.it
# NOTA: verificare prefissi su kangourou.it se cambiano di anno in anno
URL_PATTERNS = {
    "kangourou": "https://www.kangourou.it/images/TestiGare/{anno}/EcolierMarzo-{anno2}.pdf",
    "benjamin":  "https://www.kangourou.it/images/TestiGare/{anno}/BenjaminMarzo-{anno2}.pdf",
    "cadet":     "https://www.kangourou.it/images/TestiGare/{anno}/CadetMarzo-{anno2}.pdf",
    "koala":     "https://www.kangourou.it/images/TestiGare/{anno}/PreEcolierMarzo-{anno2}.pdf",
}

N_DOM_DEFAULT = {
    "kangourou": 24,
    "koala": 24,
    "benjamin": 30,
    "cadet": 30,
}

TITOLI = {
    "kangourou": lambda a: f"Kangourou - Ecolier {a}",
    "koala":     lambda a: f"Koala {a}",
    "benjamin":  lambda a: f"Benjamin {a}",
    "cadet":     lambda a: f"Cadet {a}",
}

CATEGORIE = {
    "kangourou": "Kangourou (Classi 4a-5a primaria)",
    "koala":     "Koala (Classi 2a-3a primaria)",
    "benjamin":  "Benjamin (Classi 1a-2a secondaria)",
    "cadet":     "Cadet (Classe 3a secondaria)",
}


# ─────────────────────────────────────────────────────────────
# STEP 1: Download PDF
# ─────────────────────────────────────────────────────────────

def download_pdf(tipo, anno):
    """Scarica il PDF da kangourou.it se non esiste già."""
    pdf_path = REPO_ROOT / f"pdf/{tipo}/{anno}.pdf"
    if pdf_path.exists():
        print(f"    ✅ PDF già presente: {pdf_path.name}")
        return True

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    anno2 = str(anno)[-2:]
    url = URL_PATTERNS[tipo].format(anno=anno, anno2=anno2)

    print(f"    📥 Download: {url}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        with open(pdf_path, "wb") as f:
            f.write(data)
        size_kb = len(data) // 1024
        print(f"    ✅ PDF scaricato ({size_kb} KB)")
        return True
    except Exception as e:
        print(f"    ❌ Download fallito: {e}")
        if pdf_path.exists():
            pdf_path.unlink()
        return False


# ─────────────────────────────────────────────────────────────
# STEP 2: Estrazione immagini
# ─────────────────────────────────────────────────────────────

def run_process_gara(tipo, anno):
    """Esegue process_gara.py per estrarre immagini dal PDF."""
    pdf_path = f"pdf/{tipo}/{anno}.pdf"
    output_folder = f"images/{tipo}-{anno}-screenshots"

    if not (REPO_ROOT / pdf_path).exists():
        print(f"    ❌ PDF non trovato: {pdf_path}")
        return False

    print(f"    🖼️  Estrazione immagini...")
    try:
        result = subprocess.run(
            [sys.executable, "process_gara.py", pdf_path, output_folder],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        print(f"    ❌ Timeout estrazione immagini")
        return False

    if result.returncode == 0:
        out_dir = REPO_ROOT / output_folder
        n_img = len(list(out_dir.glob("q*.png"))) if out_dir.exists() else 0
        print(f"    ✅ Immagini estratte: {n_img}")
        return True
    else:
        print(f"    ⚠️  process_gara.py fallito (returncode={result.returncode})")
        if result.stderr:
            print(f"       {result.stderr[:300]}")
        return False  # non fatale: si continua con JSON


# ─────────────────────────────────────────────────────────────
# STEP 3: Estrazione JSON con Gemini
# ─────────────────────────────────────────────────────────────

def extract_json_gemini(tipo, anno, n_dom):
    """
    Estrae JSON domande con Gemini.
    - In locale: prova prima a importare gemini_json_extractor.py (con API key hardcoded)
    - In GitHub Action: usa GEMINI_API_KEY dal secret
    """
    # Tentativo 1: modulo locale (gemini_json_extractor.py in .gitignore)
    try:
        import gemini_json_extractor as gje
        print(f"    🤖 Gemini (modulo locale)...")
        result = gje.extract_json(
            pdf_path=str(REPO_ROOT / f"pdf/{tipo}/{anno}.pdf"),
            gara_tipo=tipo,
            anno=anno,
            num_domande=n_dom,
        )
        return result is not None
    except ImportError:
        pass

    # Tentativo 2: google-genai (nuovo SDK) con GEMINI_API_KEY da env
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(f"    ❌ GEMINI_API_KEY non trovata. "
              f"Assicurati che gemini_json_extractor.py sia presente (locale) "
              f"oppure setta la variabile GEMINI_API_KEY.")
        return False

    try:
        from google import genai
    except ImportError:
        print(f"    ❌ google-genai non installato. Esegui: pip install google-genai")
        return False

    print(f"    🤖 Gemini (GEMINI_API_KEY da env)...")
    client = genai.Client(api_key=api_key)

    pdf_path = REPO_ROOT / f"pdf/{tipo}/{anno}.pdf"
    if not pdf_path.exists():
        print(f"    ❌ PDF non trovato per Gemini")
        return False

    # Chiamata API Gemini
    try:
        import time
        uploaded = client.files.upload(
            file=str(pdf_path),
            config={"mime_type": "application/pdf"},
        )
        # Aspetta che il file sia elaborato da Gemini
        while uploaded.state and uploaded.state.name == "PROCESSING":
            time.sleep(3)
            uploaded = client.files.get(name=uploaded.name)

        prompt = _build_gemini_prompt(tipo, anno, n_dom)
        print(f"       ⏳ Attendo risposta Gemini...")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[uploaded, prompt],
        )
        raw = response.text.strip()
        print(f"       RAW (primi 600 chars): {raw[:600]}")
        try:
            client.files.delete(name=uploaded.name)
        except Exception:
            pass
    except Exception as e:
        print(f"    ❌ Errore Gemini API: {e}")
        return False

    # Pulizia output Gemini (gestisce testo extra da modelli thinking)
    # Prova 1: estrai blocco ```json ... ``` con regex (più robusto)
    import re as _re
    m = _re.search(r'```json\s*(.*?)\s*```', raw, _re.DOTALL)
    if m:
        raw = m.group(1).strip()
        print(f"       ℹ️  JSON estratto da blocco markdown")
    else:
        # Prova 2: rimuovi backtick manualmente
        if raw.startswith("```json"):
            raw = raw[7:]
        elif raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    # Fix virgolette tipografiche (bug Gemini)
    raw = raw.replace('\u201c', '"').replace('\u201d', '"')

    # Parse JSON
    data = None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        pass

    if data is None:
        (REPO_ROOT / "output").mkdir(exist_ok=True)
        raw_path = REPO_ROOT / f"output/{tipo}-{anno}-raw.json"
        raw_path.write_text(raw, encoding="utf-8")
        print(f"    ❌ JSON parse error: impossibile estrarre JSON valido (raw in {raw_path.name})")
        return False

    domande_raw = data.get("domande", [])
    if len(domande_raw) < n_dom:
        print(f"    ⚠️  Estratte {len(domande_raw)}/{n_dom} domande")

    # Converti in formato app
    domande_app = []
    for q in sorted(domande_raw, key=lambda x: x["numero"]):
        n = q["numero"]
        img_path = Path(f"images/{tipo}-{anno}-screenshots/q{n:02d}.png")
        img_final = img_path.as_posix() if (REPO_ROOT / img_path).exists() else None
        domande_app.append({
            "id": n,
            "testo": q["testo"],
            "immagine": img_final,
            "opzioni": [{"id": k, "testo": v} for k, v in q["opzioni"].items()],
            "risposta_corretta": q["risposta_corretta"],
            "punteggio": _get_punteggio(n, n_dom),
        })

    app_data = {
        "id": f"{tipo}-{anno}",
        "titolo": TITOLI[tipo](anno),
        "anno": anno,
        "categoria": CATEGORIE[tipo],
        "durata_minuti": 75,
        "screenshot_mode": False,
        "domande": domande_app,
    }

    out_path = REPO_ROOT / f"data/{tipo}/{anno}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    json_str = json.dumps(app_data, indent=2, ensure_ascii=False)

    try:
        json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"    ❌ JSON finale non valido: {e}")
        return False

    out_path.write_text(json_str, encoding="utf-8")
    con_img = sum(1 for d in domande_app if d["immagine"])
    print(f"    ✅ JSON salvato: {len(domande_app)} domande, {con_img} con immagine")
    return True


def _build_gemini_prompt(gara_tipo, anno, num_domande):
    return f"""Sei un assistente esperto nell'estrazione di dati strutturati da PDF.

Questo PDF contiene la gara {gara_tipo.upper()} {anno} di matematica, con {num_domande} domande a scelta multipla (opzioni A, B, C, D, E).

COMPITO: Estrai TUTTE le {num_domande} domande e restituisci un unico JSON con questa struttura esatta:

{{
  "domande": [
    {{
      "numero": 1,
      "testo": "testo completo della domanda senza prefisso numerico",
      "opzioni": {{
        "A": "testo opzione A",
        "B": "testo opzione B",
        "C": "testo opzione C",
        "D": "testo opzione D",
        "E": "testo opzione E"
      }},
      "risposta_corretta": "A",
      "ha_immagine": false
    }}
  ]
}}

REGOLE:
1. Le risposte corrette si trovano nell'ULTIMA PAGINA del PDF (tabella delle soluzioni)
2. "ha_immagine" = true se la domanda ha figure, diagrammi, grafici o immagini geometriche; false se solo testo
3. Se le opzioni sono figure senza testo, scrivi "figura" come testo dell'opzione
4. "testo" deve contenere la domanda completa, senza il numero iniziale (es. senza "1." o "Domanda 1")
5. Includi TUTTE le {num_domande} domande, da 1 a {num_domande}
6. RISPONDI SOLO CON IL JSON VALIDO. Niente markdown, niente spiegazioni, niente testo prima o dopo.
"""


def _get_punteggio(numero, n_dom):
    fasce = [(1, 8, 3), (9, 16, 4), (17, 24, 5)] if n_dom == 24 else [(1, 10, 3), (11, 20, 4), (21, 30, 5)]
    for s, e, p in fasce:
        if s <= numero <= e:
            return p
    return 3


# ─────────────────────────────────────────────────────────────
# STEP 4: Aggiorna index.json e sw.js
# ─────────────────────────────────────────────────────────────

def update_index_json(tipo, anno, nuova_versione, novita_text):
    """Aggiorna index.json: disponibile=true per la gara, versione e metadati."""
    idx_path = REPO_ROOT / "index.json"
    with open(idx_path, encoding="utf-8") as f:
        idx = json.load(f)

    gara_id = f"{tipo}-{anno}"
    found = False
    for gara in idx["gare"]:
        if gara["id"] == gara_id:
            gara["disponibile"] = True
            found = True
            break

    if not found:
        print(f"    ⚠️  Gara {gara_id} non trovata in index.json")
        return False

    idx["versione"] = nuova_versione
    idx["gare_disponibili"] = sum(1 for g in idx["gare"] if g["disponibile"])
    idx["ultimo_aggiornamento"] = date.today().isoformat()
    idx["novita"] = novita_text

    idx_path.write_text(json.dumps(idx, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"    ✅ index.json: {gara_id} disponibile, v{nuova_versione}, gare={idx['gare_disponibili']}")
    return True


def update_sw_js(nuova_versione):
    """Aggiorna CACHE_NAME in sw.js alla nuova versione."""
    sw_path = REPO_ROOT / "sw.js"
    content = sw_path.read_text(encoding="utf-8")
    new_content = re.sub(
        r"(const CACHE_NAME\s*=\s*'kangourou-trainer-v)[^']+(')",
        rf"\g<1>{nuova_versione}\g<2>",
        content,
    )
    if new_content == content:
        print(f"    ⚠️  sw.js: CACHE_NAME non aggiornato (pattern non trovato)")
        return False
    sw_path.write_text(new_content, encoding="utf-8")
    print(f"    ✅ sw.js: CACHE_NAME = kangourou-trainer-v{nuova_versione}")
    return True


def increment_minor_version(versione):
    """Incrementa la minor version: '2.2.0' -> '2.3.0'"""
    parts = versione.split(".")
    parts[1] = str(int(parts[1]) + 1)
    parts[2] = "0"
    return ".".join(parts)


def get_current_version():
    """Legge la versione corrente da index.json."""
    idx_path = REPO_ROOT / "index.json"
    with open(idx_path, encoding="utf-8") as f:
        idx = json.load(f)
    return idx.get("versione", "2.2.0")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Pubblica gare Kangourou in batch")
    parser.add_argument("--batch-size", type=int, default=None,
                        help="Numero gare da processare (default: da batch_queue.json)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simula senza modificare file")
    parser.add_argument("--skip-images", action="store_true",
                        help="Salta estrazione immagini (process_gara.py)")
    parser.add_argument("--skip-json", action="store_true",
                        help="Salta estrazione JSON con Gemini")
    args = parser.parse_args()

    queue_path = REPO_ROOT / "batch_queue.json"
    with open(queue_path, encoding="utf-8") as f:
        queue_data = json.load(f)

    queue = queue_data.get("queue", [])
    batch_size = args.batch_size or queue_data.get("batch_size", 3)
    batch = queue[:batch_size]

    if not batch:
        print("✅ Coda vuota - niente da processare")
        return 0

    print(f"\n🦘 KANGOUROU BATCH PUBLISHER")
    print(f"{'=' * 50}")
    print(f"  Gare in coda:  {len(queue)}")
    print(f"  Batch size:    {batch_size}")
    print(f"  Dry run:       {args.dry_run}")
    print(f"  Skip immagini: {args.skip_images}")
    print(f"  Skip JSON:     {args.skip_json}")
    print(f"{'=' * 50}\n")

    report_lines = [f"# Batch Report - {date.today()}\n\n"]
    processate = []
    errori = []
    versione = get_current_version()
    novita_lista = []

    for item in batch:
        tipo = item["tipo"]
        anno = item["anno"]
        n_dom = item.get("n_dom", N_DOM_DEFAULT.get(tipo, 24))
        needs_download = item.get("needs_download", False)

        print(f"\n📋 {tipo.upper()} {anno} ({n_dom} domande)")
        print(f"   {'-' * 40}")

        if args.dry_run:
            print(f"   [DRY RUN] Saltato")
            processate.append(item)
            continue

        # 1. Download PDF
        if needs_download:
            if not download_pdf(tipo, anno):
                errori.append(f"{tipo}/{anno}: download PDF fallito")
                report_lines.append(f"- ❌ **{tipo} {anno}**: download PDF fallito\n")
                continue

        # 2. Immagini
        ok_images = True
        if not args.skip_images:
            ok_images = run_process_gara(tipo, anno)
        else:
            print(f"    ⏭️  Immagini skippate")

        # 3. JSON Gemini
        ok_json = True
        if not args.skip_json:
            ok_json = extract_json_gemini(tipo, anno, n_dom)
        else:
            print(f"    ⏭️  JSON skippato")

        if not ok_json:
            errori.append(f"{tipo}/{anno}: estrazione JSON fallita")
            report_lines.append(f"- ❌ **{tipo} {anno}**: JSON non estratto\n")
            continue

        # 4. Aggiorna index.json e sw.js
        versione = increment_minor_version(versione)
        tipo_label = tipo.capitalize()
        novita_lista.append(f"{tipo_label} {anno}")
        novita_text = "Nuove gare disponibili: " + ", ".join(novita_lista)

        ok_idx = update_index_json(tipo, anno, versione, novita_text)
        ok_sw = update_sw_js(versione)

        stato = "✅" if (ok_json and ok_idx and ok_sw) else "⚠️"
        img_stato = "✅" if ok_images else "⚠️ (parziale)"
        report_lines.append(
            f"- {stato} **{tipo_label} {anno}** → v{versione} | immagini: {img_stato} | JSON: ✅\n"
        )
        processate.append(item)
        print(f"\n   ✅ {tipo.upper()} {anno} completato (v{versione})")

    # Aggiorna coda: rimuovi le gare processate
    if not args.dry_run and processate:
        ids_processati = {(q["tipo"], str(q["anno"])) for q in processate}
        queue_data["queue"] = [
            q for q in queue
            if (q["tipo"], str(q["anno"])) not in ids_processati
        ]
        queue_path.write_text(json.dumps(queue_data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n📋 Coda aggiornata: {len(queue_data['queue'])} gare rimaste")

    # Report finale
    report_lines.append(f"\n---\n**Processate**: {len(processate)} | **Errori**: {len(errori)}\n")
    report_path = REPO_ROOT / "output" / "batch_report.md"
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text("".join(report_lines), encoding="utf-8")

    print(f"\n{'=' * 50}")
    print(f"  ✅ Processate:   {len(processate)}")
    print(f"  ❌ Errori:       {len(errori)}")
    print(f"  📋 Coda rimasta: {len(queue_data.get('queue', []))}")
    print(f"  📄 Report:       output/batch_report.md")
    print(f"{'=' * 50}\n")

    return 1 if errori else 0


if __name__ == "__main__":
    sys.exit(main())
