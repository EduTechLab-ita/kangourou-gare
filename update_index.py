#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera index.json completo con tutte le 35 gare
"""

import json

# Lista completa gare Pre-Ecolier (Koala)
koala_anni = [2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]

# Lista completa gare Ecolier (Kangourou)
kangourou_anni = list(range(2000, 2025))  # 2000-2024

gare = []

# Aggiungi tutte le gare Koala
for anno in koala_anni:
    gare.append({
        "id": f"koala-{anno}",
        "tipo": "koala",
        "anno": anno,
        "categoria": "Pre-Ecolier",
        "classi": "2ª e 3ª Primaria",
        "tempo_minuti": 75,
        "totale_domande": 24,
        "punteggio_massimo": 96,
        "pdf_url": f"pdf/koala/{anno}.pdf",
        "json_url": f"data/koala/{anno}.json",
        "disponibile": True
    })

# Aggiungi tutte le gare Kangourou
for anno in kangourou_anni:
    gare.append({
        "id": f"kangourou-{anno}",
        "tipo": "kangourou",
        "anno": anno,
        "categoria": "Ecolier",
        "classi": "4ª e 5ª Primaria",
        "tempo_minuti": 75,
        "totale_domande": 24,
        "punteggio_massimo": 96,
        "pdf_url": f"pdf/kangourou/{anno}.pdf",
        "json_url": f"data/kangourou/{anno}.json",
        "disponibile": True
    })

# Ordina per anno (più recenti prima)
gare.sort(key=lambda x: x['anno'], reverse=True)

# Crea index.json
index_data = {
    "gare": gare,
    "ultimo_aggiornamento": "2025-11-11",
    "versione": "1.0.0",
    "totale_gare": len(gare)
}

# Salva
with open("index.json", "w", encoding="utf-8") as f:
    json.dump(index_data, f, ensure_ascii=False, indent=2)

print(f"✅ index.json aggiornato con {len(gare)} gare!")
print(f"   - Koala: {len(koala_anni)} gare")
print(f"   - Kangourou: {len(kangourou_anni)} gare")
