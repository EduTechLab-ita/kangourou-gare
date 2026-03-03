"""
verifica_risposte.py - Controllo incrociato risposte JSON vs PDF ufficiali
Uso: py -3 verifica_risposte.py
"""

import fitz
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
PDF_BASE  = os.path.join(BASE, "pdf")
DATA_BASE = os.path.join(BASE, "data")

N_DOMANDE = {"kangourou": 24, "koala": 24, "benjamin": 30, "cadet": 30}

ERRORI   = []
WARNINGS = []
OK       = 0


def estrai_risposte_pdf(pdf_path, n_atteso):
    """
    Estrae le risposte ufficiali dal PDF. Gestisce 3 formati:
    1. Tabella compatta (esattamente N lettere in una pagina)
    2. Tabella con header ABCDE (N+5 lettere, prime 5 = A,B,C,D,E)
    3. Spiegazioni ("N. Risposta X).") sparse su più pagine
    Scansiona dall'ultima pagina all'indietro per trovare prima la tabella.
    """
    doc = fitz.open(pdf_path)
    testo_completo = "\n".join(p.get_text() for p in doc)

    # Scansione dall'ultima pagina all'indietro: la tabella è sempre alla fine
    for page in reversed(doc):
        testo = page.get_text()
        lettere = re.findall(r'\b([A-E])\b', testo)
        n = len(lettere)

        # Caso 1: esattamente N lettere
        if n == n_atteso:
            return lettere

        # Caso 2: N+5 lettere con header ABCDE (griglia opzioni)
        if n == n_atteso + 5 and lettere[:5] == ['A', 'B', 'C', 'D', 'E']:
            return lettere[5:]

        # Caso 3: N*2+5 lettere (griglia doppia con header — alcune versioni)
        if n == n_atteso * 2 + 5 and lettere[:5] == ['A', 'B', 'C', 'D', 'E']:
            return lettere[5:5 + n_atteso]

    # Caso 4: formato spiegazioni ("N. Risposta X)." o "Risposta: X")
    matches = re.findall(r'(\d+)\.\s*Risposta\s+([A-E])\b', testo_completo, re.IGNORECASE)
    if matches:
        risposte = {}
        for num_str, lettera in matches:
            num = int(num_str)
            if 1 <= num <= n_atteso:
                risposte[num] = lettera
        if len(risposte) == n_atteso:
            return [risposte[i] for i in range(1, n_atteso + 1)]

    return None  # Nessuna tabella risposte trovata


def verifica_gara(tipo, anno_str):
    global OK
    pdf_path  = os.path.join(PDF_BASE,  tipo, f"{anno_str}.pdf")
    json_path = os.path.join(DATA_BASE, tipo, f"{anno_str}.json")

    if not os.path.exists(pdf_path):
        WARNINGS.append(f"  [{tipo}/{anno_str}] PDF non trovato — skip")
        return
    if not os.path.exists(json_path):
        WARNINGS.append(f"  [{tipo}/{anno_str}] JSON non trovato — skip")
        return

    n_att = N_DOMANDE[tipo]

    # --- Leggi risposte PDF ---
    risposte_pdf = estrai_risposte_pdf(pdf_path, n_att)
    if risposte_pdf is None:
        WARNINGS.append(f"  [{tipo}/{anno_str}] Tabella risposte non trovata nel PDF — skip")
        return

    # --- Leggi risposte JSON ---
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    domande = data.get("domande", [])
    if len(domande) != n_att:
        WARNINGS.append(f"  [{tipo}/{anno_str}] JSON ha {len(domande)} domande invece di {n_att} — skip")
        return

    # --- Confronta ---
    discrepanze = []
    for i, domanda in enumerate(domande):
        risposta_json = domanda.get("risposta_corretta", "?")
        risposta_pdf  = risposte_pdf[i]
        if risposta_json != risposta_pdf:
            discrepanze.append((i + 1, risposta_json, risposta_pdf))

    if discrepanze:
        ERRORI.append((tipo, anno_str, discrepanze))
        for n, rj, rp in discrepanze:
            print(f"  ❌ [{tipo}/{anno_str}] Q{n:02d}: JSON={rj}  PDF={rp}")
    else:
        OK += 1
        print(f"  ✅ [{tipo}/{anno_str}]")


def main():
    print("=" * 60)
    print("VERIFICA RISPOSTE - Confronto JSON vs PDF ufficiali")
    print("=" * 60)

    totale_gare = 0
    for tipo in ["kangourou", "koala", "benjamin", "cadet"]:
        json_dir = os.path.join(DATA_BASE, tipo)
        if not os.path.isdir(json_dir):
            continue
        anni = sorted(f.replace(".json", "") for f in os.listdir(json_dir) if f.endswith(".json"))
        print(f"\n--- {tipo.upper()} ({len(anni)} gare) ---")
        for anno in anni:
            verifica_gara(tipo, anno)
            totale_gare += 1

    # --- Riepilogo ---
    print("\n" + "=" * 60)
    print("RIEPILOGO")
    print("=" * 60)
    print(f"Gare controllate: {totale_gare}")
    print(f"✅ OK:            {OK}")
    print(f"❌ Con errori:    {len(ERRORI)}")
    print(f"⚠️  Warning/skip: {len(WARNINGS)}")

    if WARNINGS:
        print("\nWARNING (PDF senza tabella risposte o non trovato):")
        for w in WARNINGS:
            print(w)

    if ERRORI:
        print(f"\n{'='*60}")
        print("ERRORI DA CORREGGERE:")
        for tipo, anno, disc in ERRORI:
            print(f"\n  {tipo}/{anno}:")
            for n, rj, rp in disc:
                print(f"    Q{n:02d}: è '{rj}', dovrebbe essere '{rp}'")
        sys.exit(1)
    else:
        if not WARNINGS:
            print("\n✅ Tutte le risposte sono corrette!")
        else:
            print("\n✅ Tutte le gare verificabili sono corrette (vedi warning per quelle skip).")


if __name__ == "__main__":
    main()
