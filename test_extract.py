#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test estrazione testo da PDF Kangourou
"""

import PyPDF2
import sys

def extract_text_from_pdf(pdf_path):
    """Estrae tutto il testo da un PDF"""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)

            print(f"📄 File: {pdf_path}")
            print(f"📊 Numero pagine: {len(pdf_reader.pages)}")
            print("=" * 80)

            # Estrai testo da ogni pagina
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()

                print(f"\n--- PAGINA {page_num + 1} ---")
                print(text)
                print("\n" + "=" * 80)

                # Fermiamoci alle prime 3 pagine per il test
                if page_num >= 2:
                    print("\n[Test limitato alle prime 3 pagine]")
                    break

    except Exception as e:
        print(f"❌ Errore: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Test con Kangourou 2024
    pdf_path = "pdf/kangourou/2024.pdf"
    extract_text_from_pdf(pdf_path)
