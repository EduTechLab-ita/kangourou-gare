#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script per convertire automaticamente i PDF Kangourou in JSON
Estrae: testo domande, opzioni, risposte corrette, immagini
"""

import PyPDF2
import json
import os
import re
from pathlib import Path

def extract_text_from_pdf(pdf_path):
    """Estrae tutto il testo da un PDF"""
    text_pages = []
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text_pages.append(page.extract_text())
        return text_pages
    except Exception as e:
        print(f"❌ Errore lettura PDF: {e}")
        return []

def parse_domande(text_pages, anno, tipo):
    """Parsing intelligente delle domande"""

    # Unisci tutto il testo (esclusa ultima pagina con soluzioni)
    full_text = "\n".join(text_pages[:-1])  # Esclude ultima pagina

    domande = []

    # Pattern per identificare le domande
    # Formato: "1. Testo domanda... A) ... B) ... C) ... D) ... E) ..."
    pattern = r'(\d+)\.\s+(.+?)(?=\d+\.|$)'

    matches = re.finditer(pattern, full_text, re.DOTALL)

    for match in matches:
        numero = int(match.group(1))
        testo_completo = match.group(2).strip()

        # Estrai testo domanda (tutto prima delle opzioni)
        # Le opzioni iniziano con "A) " o "A)"
        opzioni_match = re.search(r'\n?\s*A\)\s*', testo_completo)
        if not opzioni_match:
            continue

        testo_domanda = testo_completo[:opzioni_match.start()].strip()
        testo_opzioni = testo_completo[opzioni_match.start():].strip()

        # Estrai le 5 opzioni A, B, C, D, E
        opzioni = {}
        for lettera in ['A', 'B', 'C', 'D', 'E']:
            pattern_opzione = rf'{lettera}\)\s*([^\n]+?)(?=\s*[B-E]\)|$)'
            match_opz = re.search(pattern_opzione, testo_opzioni, re.DOTALL)
            if match_opz:
                opzioni[lettera] = match_opz.group(1).strip()

        # Determina punti in base al numero domanda
        if numero <= 8:
            punti = 3
            difficolta = "facile"
        elif numero <= 16:
            punti = 4
            difficolta = "media"
        else:
            punti = 5
            difficolta = "difficile"

        domanda = {
            "numero": numero,
            "punti": punti,
            "difficolta": difficolta,
            "testo": testo_domanda,
            "immagine": None,  # Da estrarre manualmente
            "opzioni": opzioni,
            "risposta_corretta": None  # Da estrarre dalla pagina soluzioni
        }

        domande.append(domanda)

    return domande

def extract_soluzioni(text_pages):
    """Estrae le soluzioni dalla pagina finale"""
    # L'ultima pagina contiene le soluzioni
    ultima_pagina = text_pages[-1]

    soluzioni = {}

    # Pattern per trovare le soluzioni: "1. C" o "1. C)" o "1) C"
    patterns = [
        r'(\d+)[.\)]\s*([A-E])',
        r'(\d+)\s+([A-E])',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, ultima_pagina)
        for match in matches:
            numero = int(match[0])
            risposta = match[1]
            soluzioni[numero] = risposta

    return soluzioni

def convert_pdf_to_json(pdf_path, anno, tipo):
    """Converte un PDF in formato JSON"""

    print(f"  📄 Elaboro {tipo.upper()} {anno}...")

    # Estrai tutto il testo
    text_pages = extract_text_from_pdf(pdf_path)

    if not text_pages:
        print(f"  ❌ Errore: impossibile leggere il PDF")
        return None

    # Parse domande
    domande = parse_domande(text_pages, anno, tipo)

    # Estrai soluzioni
    soluzioni = extract_soluzioni(text_pages)

    # Abbina soluzioni alle domande
    for domanda in domande:
        numero = domanda["numero"]
        if numero in soluzioni:
            domanda["risposta_corretta"] = soluzioni[numero]

    # Crea struttura JSON completa
    categoria_nome = "Pre-Ecolier" if tipo == "koala" else "Ecolier"
    classi = "2ª e 3ª Primaria" if tipo == "koala" else "4ª e 5ª Primaria"

    json_data = {
        "meta": {
            "anno": anno,
            "tipo": tipo,
            "categoria": categoria_nome,
            "classi": classi,
            "tempo_minuti": 75,
            "totale_domande": 24,
            "punteggio_massimo": 96
        },
        "domande": domande
    }

    return json_data

def main():
    print("=" * 80)
    print("🔄 CONVERSIONE AUTOMATICA PDF → JSON")
    print("=" * 80)

    # Crea cartelle output
    os.makedirs("data/koala", exist_ok=True)
    os.makedirs("data/kangourou", exist_ok=True)

    # Per ora facciamo solo un test con 2-3 gare
    test_files = [
        ("pdf/koala/2013.pdf", 2013, "koala"),
        ("pdf/kangourou/2024.pdf", 2024, "kangourou"),
        ("pdf/kangourou/2023.pdf", 2023, "kangourou"),
    ]

    print("\n🧪 TEST CONVERSIONE (3 gare di esempio)")
    print("-" * 80)

    for pdf_path, anno, tipo in test_files:
        if not os.path.exists(pdf_path):
            print(f"  ⏭️  {pdf_path} non trovato, salto...")
            continue

        # Converte PDF → JSON
        json_data = convert_pdf_to_json(pdf_path, anno, tipo)

        if json_data:
            # Salva JSON
            output_path = f"data/{tipo}/{anno}.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)

            num_domande = len(json_data["domande"])
            num_soluzioni = sum(1 for d in json_data["domande"] if d["risposta_corretta"])

            print(f"  ✅ {tipo.upper()} {anno}: {num_domande} domande, {num_soluzioni} soluzioni")
            print(f"     → Salvato in {output_path}")
        else:
            print(f"  ❌ Errore conversione {tipo} {anno}")

    print("\n" + "=" * 80)
    print("✅ Conversione test completata!")
    print("=" * 80)
    print("\n💡 NOTA: Questo è un test con 3 gare.")
    print("   Verifica i JSON generati in data/koala/ e data/kangourou/")
    print("   Se il formato è corretto, possiamo convertire tutte le 35 gare!")

if __name__ == "__main__":
    main()
