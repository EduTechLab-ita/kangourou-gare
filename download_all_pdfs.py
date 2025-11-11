#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script per scaricare TUTTI i PDF delle gare Kangourou
Pre-Ecolier (Koala): 2013-2022
Ecolier (Kangourou): 2000-2024
"""

import requests
import os
import time

# Lista completa gare Pre-Ecolier (Koala)
KOALA_GARE = [
    (2013, "PMarzo-13.pdf"),
    (2014, "PMarzo-14.pdf"),
    (2015, "PMarzo-15.pdf"),
    (2016, "PMarzo-16.pdf"),
    (2017, "PMarzo-17.pdf"),
    (2018, "PMarzo-18.pdf"),
    (2019, "Koala2019REL.pdf"),
    (2020, "PMarzo-20.pdf"),
    (2021, "Koala2021REL.pdf"),
    (2022, "Koala2022REL.pdf"),
]

# Lista completa gare Ecolier (Kangourou)
ECOLIER_GARE = [
    (2000, "Marzo_00.pdf"),
    (2001, "EMarzo-01.pdf"),
    (2002, "EMarzo-02.pdf"),
    (2003, "EMarzo-03.pdf"),
    (2004, "EMarzo-04.pdf"),
    (2005, "EMarzo-05.pdf"),
    (2006, "EMarzo-06.pdf"),
    (2007, "EMarzo-07.pdf"),
    (2008, "EMarzo-08.pdf"),
    (2009, "EMarzo-09.pdf"),
    (2010, "EMarzo-10.pdf"),
    (2011, "EMarzo-11.pdf"),
    (2012, "EMarzo-12.pdf"),
    (2013, "EMarzo-13.pdf"),
    (2014, "EMarzo-14.pdf"),
    (2015, "EMarzo-15.pdf"),
    (2016, "EMarzo-16.pdf"),
    (2017, "EMarzo-17.pdf"),
    (2018, "EMarzo-18.pdf"),
    (2019, "EMarzo-19.pdf"),
    (2020, "EMarzo-20.pdf"),
    (2021, "Ecolier2021REL.pdf"),
    (2022, "Ecolier2022REL.pdf"),
    (2023, "Ecolier2023REL.pdf"),
    (2024, "Ecolier2024REL.pdf"),
]

BASE_URL = "https://www.kangourou.it/images/TestiGare"

def download_pdf(anno, filename, categoria):
    """Scarica un singolo PDF"""
    url = f"{BASE_URL}/{anno}/{filename}"

    # Determina cartella destinazione
    if categoria == "koala":
        dest_folder = "pdf/koala"
        dest_filename = f"{anno}.pdf"
    else:
        dest_folder = "pdf/kangourou"
        dest_filename = f"{anno}.pdf"

    dest_path = os.path.join(dest_folder, dest_filename)

    # Salta se già esiste
    if os.path.exists(dest_path):
        print(f"  ⏭️  {dest_filename} già presente, salto...")
        return True

    try:
        print(f"  📥 Scarico {filename}...", end=" ")
        response = requests.get(url, timeout=30)

        if response.status_code == 200:
            # Salva il file
            with open(dest_path, 'wb') as f:
                f.write(response.content)
            print(f"✅ OK ({len(response.content)//1024} KB)")
            return True
        else:
            print(f"❌ Errore HTTP {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Errore: {e}")
        return False

def main():
    print("=" * 80)
    print("🦘 DOWNLOAD AUTOMATICO GARE KANGOUROU")
    print("=" * 80)

    # Assicurati che le cartelle esistano
    os.makedirs("pdf/koala", exist_ok=True)
    os.makedirs("pdf/kangourou", exist_ok=True)

    # Scarica tutte le gare Koala
    print("\n🐨 GARE PRE-ECOLIER (KOALA) - 2013-2022")
    print("-" * 80)
    koala_ok = 0
    for anno, filename in KOALA_GARE:
        if download_pdf(anno, filename, "koala"):
            koala_ok += 1
        time.sleep(0.5)  # Pausa per non sovraccaricare il server

    # Scarica tutte le gare Kangourou
    print("\n🦘 GARE ECOLIER (KANGOUROU) - 2000-2024")
    print("-" * 80)
    ecolier_ok = 0
    for anno, filename in ECOLIER_GARE:
        if download_pdf(anno, filename, "kangourou"):
            ecolier_ok += 1
        time.sleep(0.5)

    # Riepilogo finale
    print("\n" + "=" * 80)
    print("📊 RIEPILOGO DOWNLOAD")
    print("=" * 80)
    print(f"🐨 Koala:      {koala_ok}/{len(KOALA_GARE)} gare scaricate")
    print(f"🦘 Kangourou:  {ecolier_ok}/{len(ECOLIER_GARE)} gare scaricate")
    print(f"📚 TOTALE:     {koala_ok + ecolier_ok}/{len(KOALA_GARE) + len(ECOLIER_GARE)} gare")
    print("=" * 80)

    if (koala_ok + ecolier_ok) == (len(KOALA_GARE) + len(ECOLIER_GARE)):
        print("✅ Tutti i PDF scaricati con successo!")
    else:
        print("⚠️  Alcuni PDF non sono stati scaricati. Verifica gli errori sopra.")

if __name__ == "__main__":
    main()
