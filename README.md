# 🦘 Kangourou Gare - Archivio Digitale

[![GitHub Pages](https://img.shields.io/badge/GitHub-Pages-blue)](https://edutechlab-ita.github.io/kangourou-trainer)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> 📚 Archivio digitale delle gare nazionali di matematica **Kangourou** e **Koala** per la scuola primaria.

---

## 🎯 Obiettivo

Fornire alle scuole primarie italiane un archivio completo e accessibile delle gare Kangourou degli anni precedenti, permettendo agli studenti di allenarsi in formato digitale.

**Problema risolto:** I libretti cartacei vengono utilizzati solo per la gara ufficiale, lasciando le scuole senza materiale per l'allenamento. Questa repository digitalizza le gare passate rendendole riutilizzabili.

---

## 📂 Struttura Repository

```
kangourou-gare/
├── pdf/                    # PDF originali delle gare
│   ├── koala/             # Gare Koala (2ª-3ª primaria)
│   │   └── 2013.pdf
│   └── kangourou/         # Gare Kangourou (4ª-5ª primaria)
│       └── 2024.pdf
│
├── data/                   # Dati JSON strutturati
│   ├── koala/
│   │   └── 2013.json      # (da generare)
│   └── kangourou/
│       └── 2024.json      # (da generare)
│
├── images/                 # Immagini estratte dalle gare
│   ├── koala-2013/        # (da generare)
│   └── kangourou-2024/    # (da generare)
│
└── index.json             # Catalogo completo gare disponibili
```

---

## 🦘 Gare Disponibili

### Koala (Pre-Ecolier)
- **Classi:** 2ª e 3ª Primaria
- **Anni disponibili:** 2013
- **Formato:** 24 domande, 75 minuti, 96 punti max

### Kangourou (Ecolier)
- **Classi:** 4ª e 5ª Primaria
- **Anni disponibili:** 2024
- **Formato:** 24 domande, 75 minuti, 96 punti max

---

## 📊 Formato Dati

Ogni gara è strutturata in JSON con:
- **Meta-informazioni:** anno, categoria, tempo, punteggi
- **24 domande** a scelta multipla (A, B, C, D, E)
- **3 livelli di difficoltà:**
  - Q. 1-8: 3 punti (facili)
  - Q. 9-16: 4 punti (medie)
  - Q. 17-24: 5 punti (difficili)
- **Soluzioni complete** con spiegazioni
- **Immagini** collegate (quando presenti)

---

## 🌐 Applicazione Web

L'applicazione web per utilizzare queste gare è disponibile su:

👉 **[edutechlab-ita.github.io/kangourou-trainer](https://edutechlab-ita.github.io/kangourou-trainer)**

### Funzionalità:
- ✅ Interfaccia docenti per generare link gare
- ✅ Interfaccia studenti per svolgere le gare
- ✅ Modalità **Allenamento** (feedback immediato)
- ✅ Modalità **Simulazione** (timer 75 minuti)
- ✅ PWA installabile (funziona offline)
- ✅ Compatibile con tablet, PC e LIM

---

## 🔄 Aggiornamento Annuale

**Ogni anno a marzo** (dopo la gara ufficiale):

1. Scarica nuovi PDF da [kangourou.it](https://www.kangourou.it)
2. Aggiungi alla repository:
   ```bash
   git add pdf/kangourou/2025.pdf
   git commit -m "Aggiunta gara Kangourou 2025"
   git push
   ```
3. Converti PDF → JSON (procedura automatizzata)
4. L'app si aggiorna automaticamente ✅

---

## 📜 Licenza e Crediti

- **Licenza:** MIT License
- **Gare ufficiali:** © [Kangourou Italia](https://www.kangourou.it)
- **Progetto didattico:** [EduTechLab](https://edutechlab-ita.github.io)
- **Uso consentito:** Solo scopo educativo e di allenamento

⚠️ **Nota:** Questo archivio è destinato esclusivamente all'allenamento degli studenti. Le gare ufficiali rimangono di proprietà di Kangourou Italia.

---

## 🛠️ Tecnologie

- **Hosting:** GitHub Pages (gratuito)
- **Frontend:** HTML5, CSS3, JavaScript (Vanilla)
- **PWA:** Service Worker + Manifest
- **Dati:** JSON statico (nessun database)
- **Privacy:** Nessun login/tracking richiesto

---

## 📞 Contatti

- **Sito:** [edutechlab-ita.github.io](https://edutechlab-ita.github.io)
- **Email:** edutechlab.ita@gmail.com
- **Repository:** [github.com/edutechlab-ita/kangourou-gare](https://github.com/edutechlab-ita/kangourou-gare)

---

## 🚀 Sviluppo

**Versione:** 1.0.0
**Stato:** 🟢 In sviluppo attivo
**Data creazione:** 11 Novembre 2025

---

**Made with ❤️ for Italian Primary Schools**
