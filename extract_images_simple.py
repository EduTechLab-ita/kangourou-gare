#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script semplificato per estrarre immagini dai PDF Kangourou
Usa PyMuPDF (fitz) che funziona su Windows senza dipendenze esterne
"""

import os
import sys

# Controlla se PyMuPDF è installato
try:
    import fitz  # PyMuPDF
except ImportError:
    print("❌ PyMuPDF non installato!")
    print("   Installalo con: pip install PyMuPDF")
    sys.exit(1)

def extract_images_from_pdf(pdf_path, output_dir, tipo, anno):
    """Estrae immagini da un PDF"""

    try:
        # Apri PDF
        pdf_document = fitz.open(pdf_path)

        # Crea cartella output
        img_folder = os.path.join(output_dir, f"{tipo}-{anno}")
        os.makedirs(img_folder, exist_ok=True)

        print(f"  📄 Elaboro {tipo} {anno} ({len(pdf_document)} pagine)...")

        # Conta pagine (esclusa ultima con soluzioni)
        num_pages = len(pdf_document) - 1

        # Per ogni pagina
        for page_num in range(num_pages):
            page = pdf_document[page_num]

            # Converti pagina in immagine
            # zoom=2 per qualità migliore
            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat)

            # Salva immagine
            output_path = os.path.join(img_folder, f"page_{page_num + 1}.png")
            pix.save(output_path)

        pdf_document.close()

        num_images = num_pages
        print(f"  ✅ {num_images} immagini estratte in {img_folder}")
        return True

    except Exception as e:
        print(f"  ❌ Errore: {e}")
        return False

def main():
    print("=" * 80)
    print("📸 ESTRAZIONE IMMAGINI DA PDF")
    print("=" * 80)

    # Directory
    pdf_dir = "pdf"
    output_dir = "images"

    # Gare da processare (iniziamo con quelle che hanno già JSON)
    gare_priority = [
        ("kangourou", 2024),
        ("kangourou", 2023),
        ("koala", 2013)
    ]

    print("\n🎯 Estraggo immagini dalle gare prioritarie...")
    print("-" * 80)

    success_count = 0
    for tipo, anno in gare_priority:
        pdf_path = os.path.join(pdf_dir, tipo, f"{anno}.pdf")

        if not os.path.exists(pdf_path):
            print(f"  ⏭️  {pdf_path} non trovato, salto...")
            continue

        if extract_images_from_pdf(pdf_path, output_dir, tipo, anno):
            success_count += 1

    print("\n" + "=" * 80)
    print(f"✅ Estrazione completata! {success_count}/{len(gare_priority)} gare elaborate")
    print("=" * 80)
    print("\n💡 Le immagini sono state salvate in:")
    print(f"   {os.path.abspath(output_dir)}")
    print("\n📝 Nota: Ora devi aggiornare i JSON per collegare le immagini alle domande")

if __name__ == "__main__":
    main()
