#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Collega le immagini estratte ai JSON delle domande
"""

import json
import os

def link_images(tipo, anno):
    """Collega immagini al JSON"""

    json_path = f"data/{tipo}/{anno}.json"
    img_folder = f"images/{tipo}-{anno}"

    if not os.path.exists(json_path):
        print(f"  ⏭️  JSON non trovato: {json_path}")
        return False

    if not os.path.exists(img_folder):
        print(f"  ⏭️  Cartella immagini non trovata: {img_folder}")
        return False

    # Carica JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Collega ogni domanda alla sua pagina
    # Assumiamo che ogni pagina contenga ~6 domande
    # Le prime 5 pagine hanno le domande, l'ultima ha le soluzioni
    domande_per_pagina = 6

    for domanda in data["domande"]:
        numero = domanda["numero"]
        # Calcola pagina (1-based)
        pagina = ((numero - 1) // domande_per_pagina) + 1

        # Collega immagine
        domanda["immagine"] = f"{img_folder}/page_{pagina}.png"

    # Salva JSON aggiornato
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  ✅ {tipo} {anno}: {len(data['domande'])} domande collegate alle immagini")
    return True

# Elabora le 3 gare
gare = [
    ("kangourou", 2024),
    ("kangourou", 2023),
    ("koala", 2013)
]

print("🔗 COLLEGAMENTO IMMAGINI AI JSON")
print("=" * 60)

for tipo, anno in gare:
    link_images(tipo, anno)

print("=" * 60)
print("✅ Collegamento completato!")
