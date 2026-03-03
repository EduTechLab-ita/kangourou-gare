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
    Estrae le risposte ufficiali dal PDF. Formati gestiti:
    0. Riga singola con N lettere spaziate ("A B C D E B A ...")
    1. Tabella compatta: esattamente N lettere uppercase in una pagina
    2. Griglia con header ABCDE: N+5 lettere uppercase, prime 5 = A,B,C,D,E
    3. Griglia doppia con header: N*2+5 lettere uppercase
    1-3 CI: stessi casi ma case-insensitive (solo se CS era vicino: diff <= 3)
    4b. N-1 lettere + quesito annullato nel testo
    4. Formato spiegazioni: "N. Risposta X)." (accetta max 2 mancanti, per refusi)

    Strategia: CS prima (evita false match su 'a','e' italiane in testo prose),
    poi CI come fallback SOLO se CS era quasi-vicino al target (diff <= 3,
    serve per tabelle con lowercase 'e' come koala/2014).
    """
    doc = fitz.open(pdf_path)
    testo_completo = "\n".join(p.get_text() for p in doc)

    for page in reversed(doc):
        testo = page.get_text()

        # Caso 0: riga singola con N lettere spaziate (es. "A B C D E B A ...")
        for line in testo.split('\n'):
            parts = line.strip().split()
            if (len(parts) == n_atteso
                    and all(len(p) == 1 and p.upper() in 'ABCDE' for p in parts)):
                return [p.upper() for p in parts]

        # Case-SENSITIVE prima (evita false match con 'a','e' italiane)
        cs = re.findall(r'\b([A-E])\b', testo)
        n_cs = len(cs)
        if n_cs == n_atteso:
            return cs
        if n_cs == n_atteso + 5 and cs[:5] == ['A', 'B', 'C', 'D', 'E']:
            return cs[5:]
        if n_cs == n_atteso * 2 + 5 and cs[:5] == ['A', 'B', 'C', 'D', 'E']:
            return cs[5:5 + n_atteso]

        # Fallback CI (per tabelle con lowercase 'e', es. koala/2014)
        # Solo se CS era vicino al target: distingue 'e' maiuscola mancante da
        # 'a','e' italiane nel testo prose che gonfierebbero il conteggio.
        ci = [l.upper() for l in re.findall(r'\b([A-Ea-e])\b', testo)]
        n_ci = len(ci)
        cs_vicino = (abs(n_cs - n_atteso) <= 3
                     or abs(n_cs - (n_atteso + 5)) <= 3
                     or abs(n_cs - (n_atteso * 2 + 5)) <= 3)
        if cs_vicino:
            if n_ci == n_atteso:
                return ci
            if n_ci == n_atteso + 5 and ci[:5] == ['A', 'B', 'C', 'D', 'E']:
                return ci[5:]
            if n_ci == n_atteso * 2 + 5 and ci[:5] == ['A', 'B', 'C', 'D', 'E']:
                return ci[5:5 + n_atteso]

        # Caso 4b: N-1 lettere + quesito annullato (sempre controllato)
        if n_ci == n_atteso - 1 and 'annullat' in testo.lower():
            match = re.search(r'[Ii]l quesito\s+(\d+)', testo)
            if match:
                q_ann = int(match.group(1))
                if 1 <= q_ann <= n_atteso:
                    result = list(ci)
                    result.insert(q_ann - 1, None)  # None = annullato, skip verifica
                    return result

    # Caso 4: formato spiegazioni "N. Risposta X)." (accetta max 2 mancanti)
    matches = re.findall(r'(\d+)\.\s*Risposta\s+([A-E])\b', testo_completo, re.IGNORECASE)
    if matches:
        risposte = {}
        for num_str, lettera in matches:
            num = int(num_str)
            if 1 <= num <= n_atteso:
                risposte[num] = lettera.upper()
        if len(risposte) >= n_atteso - 2:
            return [risposte.get(i, None) for i in range(1, n_atteso + 1)]

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

    risposte_pdf = estrai_risposte_pdf(pdf_path, n_att)
    if risposte_pdf is None:
        WARNINGS.append(f"  [{tipo}/{anno_str}] Tabella risposte non trovata nel PDF — skip")
        return

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    domande = data.get("domande", [])
    if len(domande) != n_att:
        WARNINGS.append(f"  [{tipo}/{anno_str}] JSON ha {len(domande)} domande invece di {n_att} — skip")
        return

    discrepanze = []
    annullati = 0
    for i, domanda in enumerate(domande):
        risposta_pdf = risposte_pdf[i]
        if risposta_pdf is None:
            annullati += 1
            continue  # Quesito annullato o refuso — non verificabile
        risposta_json = domanda.get("risposta_corretta", "?")
        if risposta_json != risposta_pdf:
            discrepanze.append((i + 1, risposta_json, risposta_pdf))

    ann_note = f" ({annullati} annullati/refusi skip)" if annullati else ""
    if discrepanze:
        ERRORI.append((tipo, anno_str, discrepanze))
        for n, rj, rp in discrepanze:
            print(f"  \u274c [{tipo}/{anno_str}] Q{n:02d}: JSON={rj}  PDF={rp}")
    else:
        OK += 1
        print(f"  \u2705 [{tipo}/{anno_str}]{ann_note}")


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

    print("\n" + "=" * 60)
    print("RIEPILOGO")
    print("=" * 60)
    print(f"Gare controllate: {totale_gare}")
    print(f"\u2705 OK:            {OK}")
    print(f"\u274c Con errori:    {len(ERRORI)}")
    print(f"\u26a0\ufe0f  Warning/skip: {len(WARNINGS)}")

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
                print(f"    Q{n:02d}: e' '{rj}', dovrebbe essere '{rp}'")
        sys.exit(1)
    else:
        if not WARNINGS:
            print("\n\u2705 Tutte le risposte sono corrette!")
        else:
            print("\n\u2705 Tutte le gare verificabili sono corrette (vedi warning per quelle skip).")


if __name__ == "__main__":
    main()
