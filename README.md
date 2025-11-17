# VerPal - Configuratore di Schemi di Pallettizzazione

VerPal è ora un toolkit Python pronto per essere eseguito in locale o integrato in applicazioni più complesse. Il progetto contiene:

- **Modelli di dominio** (`verpal.models`) per pallet, scatole, prese e layer.
- **Pianificatore ricorsivo a 5 blocchi** (`verpal.planner.RecursiveFiveBlockPlanner`).
- **Repository relazionale** basato su SQLite (`verpal.repository.DataRepository`) con dati di seed già inclusi.
- **Controlli di collisione** (`verpal.collisions.CollisionChecker`) e **snap point** (`verpal.snap.SnapPointGenerator`).
- **CLI** (`python -m verpal.cli`) per eseguire rapidamente un calcolo di strato e **export JSON** (`verpal.exporter.PlanExporter`).
  - Comando `plan` per calcolare un singolo layer.
  - Comando `stack` per generare sequenze multistrato alternate.
  - Comando `archive` per salvare l'intero progetto in un file di archivio comprimendo plan, dati e note operative.
  - Comando `catalog` per consultare da terminale pallet, scatole e tool disponibili nel database.
  - Comando `analyze` per ottenere le metriche di massa, centro di gravità e ingombro dell'intero piano o di una sequenza multistrato.

## Installazione e primi passi

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Per calcolare un layer di esempio con i dati forniti nel seed:

```bash
# Calcolo singolo layer
python -m verpal.cli plan --pallet EUR-EPAL --box BX-250 --tool TK-2 --export layer.json \
  --approach-direction NE --approach-distance 90 --label-offset 8 --approach-override center=E:120 north=N:60

# Generazione di una paletta a 4 strati alternando i corner
python -m verpal.cli stack --pallet EUR-EPAL --box BX-250 --tool TK-2 --layers 4 --corners SW NE --export stack.json
python -m verpal.cli stack --pallet EUR-EPAL --box BX-250 --tool TK-2 --layers 4 --corners SW NE \
  --approach-distance 90 --approach-direction NE --label-offset 8 --approach-override center=N:40 --export stack_annotated.json

# Salvataggio archivio completo comprensivo di note
python -m verpal.cli archive --name "Progetto demo" --pallet EUR-EPAL --box BX-250 --tool TK-2 \
  --layers 3 --corners SW NE NW --archive progetti/demo.kpg --note cliente=ACME --note priorita=alta

# Consultazione rapida del catalogo dati
python -m verpal.cli catalog pallets
python -m verpal.cli catalog boxes --db progetti/catalog.db --seed data/seed_data.json

# Report metrici di uno stack completo
python -m verpal.cli analyze --pallet EUR-EPAL --box BX-250 --tool TK-2 --layers 3 --corners SW NE NW

# Cambio del sistema di riferimento
python -m verpal.cli plan --pallet EUR-EPAL --box BX-250 --tool TK-2 \
  --origin center --axes WS --export layer_center.json
```

## Interfaccia grafica con drag & drop e vista 3D
VerPal integra anche una GUI Tkinter che permette di trascinare i colli nello strato corrente, calcolare al volo le quote e
visualizzare la paletta in 3D grazie a Matplotlib. Assicurati di avere installato le dipendenze opzionali `python3-tk` (o
`tkinter` su Windows/macOS) e `matplotlib`.

```bash
# Avvio GUI su layer singolo con riferimento SW/EN
python -m verpal.cli gui --pallet EUR-EPAL --box BX-250 --tool TK-2 --corner SW

# Visualizzazione multistrato alternando i corner e step Z personalizzato
python -m verpal.cli gui --pallet EUR-EPAL --box BX-250 --tool TK-2 --layers 3 --corners SW NE --z-step 180
```

La finestra mostra a sinistra il canvas 2D con il perimetro della pedana: è possibile trascinare ogni presa (drag&drop) per
verificare rapidamente l'effetto di micro-regolazioni. Il pulsante **Calcola quote** riporta le quote base/top degli strati
attualmente calcolati, mentre **Reset vista** ripristina la disposizione originale. A destra è sempre disponibile la vista 3D
della paletta completa con aggiornamento in tempo reale.

L'applicazione stamperà il rapporto di riempimento, le informazioni sui blocchi generati, i controlli di collisione e il numero di snap point calcolati. Il file `layer.json` contiene il payload pronto per essere trasmesso via ethernet o seriale.

## Calcolo automatico e generazione schemi
- **Algoritmo euristico ricorsivo a 5 blocchi** per il calcolo automatico dello strato ottimizzato.
- **Generazione paletta multistrato** basata su geometria di strato singola e replicabile.
- **Offset differenziati** in posizione di prelievo per la presa.
- **Assegnazione orientamento e numero scatole** per ogni presa, anche differenziata.

## Funzionalità interattive
- **Drag & Drop** per trascinare le prese sullo strato in lavorazione.
- **Snap point intelligenti** (vertici, punti medi, centro) per prese, tool e pedana con aggancio magnetico immediato.
- **Render 3D in tempo reale** dello strato e dell'intera paletta, con comandi di rotazione, traslazione e zoom.
- **Esploso dei piani** della paletta per analisi visiva rapida.
- **Anteprima etichette e vettori di accostamento** direttamente dalla CLI grazie al nuovo `PlacementAnnotator`.
- **Report metrici** (massa totale, centro di massa, ingombro, altezza) prodotti tramite il comando `analyze` o le API `verpal.metrics`.

## Dati e configurazione
- **Selezione dati dimensionali** di scatole, pallet e falde da database relazionale.
- **Consultazione** del catalogo direttamente via CLI (`python -m verpal.cli catalog pallets|boxes|tools`).
- **Impostazione origine del sistema di riferimento** per le coordinate di deposito (`--origin SW|SE|NW|NE|CENTER`).
- **Rotazione del sistema di assi** per adattarsi ai riferimenti macchina (`--axes EN|ES|WN|WS`).
- **Definizione caratteristiche dell'organo di presa**: dimensioni, orientamento, offset di prelievo, numero scatole.
- **Opzioni aggiuntive** come falda su pedana o su piani intermedi.
- **Salvataggio del progetto** in file di archivio (`ProjectArchiver`) con tutti i metadati utili e **esportazione dati** tramite ethernet o seriale verso i dispositivi di pallettizzazione.
- **Calcolo delle metriche di validazione** (`verpal.metrics.compute_layer_metrics` e `compute_sequence_metrics`) per certificare centro di massa e ingombri prima della produzione.

## Gestione schemi di formatura
La finestra *Configuratore Schemi* rappresenta l'area di lavoro per la progettazione dello strato attivo. Ogni schema conserva:
- Dimensioni pedana e **sbordatura massima ammissibile**.
- Dimensioni falda e **peso/dimensioni scatole** inclusa la posizione dell'etichetta.
- Parametri di presa predefiniti e opzionali.

## Controlli di collisione e vincoli
VerPal calcola automaticamente le condizioni di collisione tra:
1. **Sagome delle prese** (tra loro e con il tool).
2. **Sagome delle prese e pedana**, evidenziando violazioni della sbordatura consentita.
3. **Tool e prese depositate** durante il posizionamento.
4. **Prese in movimento** rispetto a quelle già depositate.
5. **Controllo di deposito** per posizioni oltre il massimo sbordo.

## Sequenza dei piani
- Possibilità di definire la **sequenza completa dei piani** che compongono il pallet.
- Per ciascun piano si seleziona uno schema esistente e le opzioni di deposito (pallet e/o falda).
- VerPal ottimizza automaticamente la **sequenza di deposito** delle prese e i dati di accostamento in funzione del corner di inizio strato.

## Gestione accostamenti e etichette
- **Direzioni e ampiezze di accostamento** programmabili per ciascuna posizione di deposito.
- Visualizzazione e gestione della **posizione etichetta** sulle scatole e della **direzione di accostamento** in deposito.
- Override puntuali della direzione/ampiezza tramite `--approach-override blocco=DIREZIONE:DISTANZA`.

## Workflow di progettazione
1. **Definizione modello**: import dei dati da database (scatole, pallet, falde) e delle caratteristiche del tool tramite `DataRepository`, che provvede alla creazione e al popolamento del database SQLite partendo dal file `data/seed_data.json`.
2. **Calcolo strato**: esecuzione dell'algoritmo euristico ricorsivo con orientamenti multipli, offset di presa e gestione differenziata per corner di inizio strato (`LayerRequest`).
3. **Ottimizzazione**: `CollisionChecker` applica automaticamente i limiti di sbordatura ed evidenzia sovrapposizioni; `SnapPointGenerator` calcola i punti di aggancio per drag&drop e per il tool di presa; `LayerSequencePlanner` replica ed eleva i layer per costruire sequenze multistrato complete.
4. **Validazione**: i dati prodotti dal planner (posizioni, blocchi, sequenza di deposito) sono pronti per l'integrazione in viewer 3D esterni o per una successiva gestione di accostamenti ed etichette.
5. **Esportazione**: `PlanExporter` salva il piano in JSON, includendo la posizione dell'etichetta e il vettore di accostamento calcolato da `PlacementAnnotator`, pronto per essere inviato verso dispositivi di pallettizzazione tramite ethernet o seriale.

Grazie alla nuova gestione del sistema di riferimento (`--origin` + `--axes`) è possibile allineare le coordinate generate dal planner con il riferimento macchina o con la cella robotizzata senza dover riconfigurare l'ambiente di destinazione. Le informazioni vengono serializzate nel piano stesso e propagate in tutta la sequenza multistrato.

VerPal offre così un ambiente unico e integrato per progettare, validare e condividere in sicurezza schemi complessi di pallettizzazione multistrato, con codice sorgente estendibile e test automatizzati (`pytest`).
