#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script per aggiungere le soluzioni corrette ai JSON già generati
"""

import json

# Soluzioni Kangourou 2024 (dalla pagina 6 del PDF)
SOLUZIONI_2024 = {
    1: "C", 2: "B", 3: "C", 4: "E", 5: "D", 6: "C",
    7: "B", 8: "C", 9: "C", 10: "C", 11: "B", 12: "D",
    13: "A", 14: "B", 15: "B", 16: "D", 17: "B", 18: "D",
    19: "E", 20: "D", 21: "D", 22: "C", 23: "E", 24: "D"
}

def update_json_with_solutions(json_path, soluzioni):
    """Aggiorna un JSON con le soluzioni corrette"""

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Aggiorna ogni domanda con la risposta corretta
    for domanda in data["domande"]:
        numero = domanda["numero"]
        if numero in soluzioni:
            domanda["risposta_corretta"] = soluzioni[numero]

    # Salva JSON aggiornato
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ {json_path} aggiornato con {len(soluzioni)} soluzioni")

# Aggiorna Kangourou 2024
update_json_with_solutions("data/kangourou/2024.json", SOLUZIONI_2024)

print("\n✅ Soluzioni aggiunte con successo!")
