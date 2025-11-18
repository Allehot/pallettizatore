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
  - Comando `plc` per generare il file di scambio dedicato ai PLC Siemens (S7) pronto per ethernet/seriale.

## Installazione e primi passi

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Esecuzione dei test su Windows (passo-passo)
1. **Installa Python 3.11** dal sito ufficiale [python.org](https://www.python.org/downloads/windows/) e seleziona l'opzione
   *Add python.exe to PATH* durante l'installazione.
2. **Apri PowerShell** nella cartella del progetto (`Shift` + tasto destro > *Apri finestra PowerShell qui*).
3. **Crea l'ambiente virtuale**:
   ```powershell
   py -3.11 -m venv .venv
   ```
4. **Attiva l'ambiente**:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```
5. **Aggiorna pip e installa dipendenze + test**:
   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -e .
   python -m pip install pytest
   ```
6. **Esegui la suite**:
   ```powershell
   python -m pytest
   ```
7. **Disattiva l'ambiente** quando hai terminato:
   ```powershell
   deactivate
   ```
   Tutti i comandi devono essere eseguiti nella stessa finestra PowerShell; eventuali errori mostrati da `pytest` ti aiutano a
   individuare rapidamente file e righe da correggere.

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

# Consultazione rapida del catalogo dati, incluse le interfalde
python -m verpal.cli catalog pallets
python -m verpal.cli catalog boxes --db progetti/catalog.db --seed data/seed_data.json
python -m verpal.cli catalog interleaves

# Report metrici di uno stack completo
python -m verpal.cli analyze --pallet EUR-EPAL --box BX-250 --tool TK-2 --layers 3 --corners SW NE NW

# Cambio del sistema di riferimento
python -m verpal.cli plan --pallet EUR-EPAL --box BX-250 --tool TK-2 \
  --origin center --axes WS --export layer_center.json

# Export diretto verso PLC Siemens
python -m verpal.cli plc --pallet EUR-EPAL --box BX-250 --tool TK-2 --target packet.s7 \
  --approach-direction NE --approach-distance 85 --layers 2 --corners SW NE --interleaf IL-CARTON
```

## Personalizzazione dimensioni scatole e scelta bancale
Ogni comando della CLI ora accetta override dimensionali opzionali:

- `--box-width/--box-depth/--box-height/--box-weight` consentono di ridefinire al volo il formato scatola senza modificare il database. È possibile indicare anche `--label-position` per cambiare la faccia dell'etichetta.
- `--pallet-width/--pallet-depth/--pallet-height` e `--overhang-x/--overhang-y` permettono di simulare bancali speciali o di restringere gli sbordi ammessi per verifiche conservative.

Gli override vengono propagati al planner, al motore di collisione e a tutti gli exporter, mantenendo coerenti quote, snap point e metriche.

## Interfalde e PLC Siemens
Il database contiene ora la tabella `interleaves` (consultabile con `python -m verpal.cli catalog interleaves`) che descrive spessore, peso e materiale delle falde. I comandi `stack`, `archive`, `analyze`, `gui` e `plc` includono i flag `--interleaf` e `--interleaf-frequency` per inserire automaticamente le interfalde tra uno strato e l'altro. L'altezza del piano e le metriche di peso vengono aggiornate automaticamente, così come gli exporter JSON.

Il comando `plc` sfrutta il nuovo modulo `verpal.plc.SiemensPLCExporter` per generare un file testuale con intestazione `#VERPAL-S7`, metadati di massa/ingombro e una tabella `IDX;LAYER;...` pronta per il download su PLC Siemens tramite ethernet o seriale. Le coordinate includono anche i vettori di accostamento e le quote etichetta calcolate dal `PlacementAnnotator`, garantendo il passaggio dati verso l'automazione industriale senza conversioni manuali.

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

Se ometti i flag `--pallet`, `--box` o `--tool` la GUI parte comunque utilizzando il primo record disponibile nel database e ti
permette di scegliere tutto direttamente dall'interfaccia. Puoi inoltre passare direttamente da riga di comando i nuovi flag
`--approach-direction`, `--approach-distance`, `--label-offset` e `--approach-override` per aprire la sessione già impostata con
gli stessi parametri di accostamento utilizzati nei workflow CLI.

La finestra mostra a sinistra il canvas 2D con il perimetro della pedana: è possibile trascinare ogni presa (drag&drop) per
verificare rapidamente l'effetto di micro-regolazioni. Sul lato destro trovi il pannello **Dati disponibili nel DB** con
menu a discesa dedicati alla scelta del **pallet**, della **scatola**, del **tool** e dell'eventuale **interfalda**, oltre a
spinbox per numero di strati e frequenza delle falde e campi per corner/z-step personalizzati. Ogni modifica rilancia il
calcolo dell'algoritmo ricorsivo e aggiorna anche la sequenza multistrato. Subito sotto è presente il pannello **Accostamento
e annotazioni** che permette di impostare la direzione/distanza di accostamento predefinite, l'offset dell'etichetta e gli
eventuali override blocco per blocco direttamente dall'interfaccia, con i pulsanti **Anteprima etichette** e **Verifica
collisioni** che consentono di validare i dati senza tornare in CLI. I pulsanti **Calcola quote** e **Reset vista** restano
disponibili per consultare rapidamente le quote base/top o per tornare allo stato iniziale. A destra è sempre disponibile la
vista 3D della paletta completa con aggiornamento in tempo reale, inclusa l'altezza risultante dal settaggio delle interfalde e
ora arricchita dai marker rossi che rappresentano la posizione dell'etichetta e il vettore di accostamento relativo ad ogni
presa.

La parte inferiore della colonna destra ospita il riquadro **Dettagli posizionamenti** con una tabella che per ogni presa
mostra centro, rotazione, direzione/ampiezza dell'accostamento e coordinate dell'etichetta nel sistema di riferimento selezionato.
Subito sotto è sempre disponibile il pannello **Metriche e export** che riepiloga modalità (layer singolo o sequenza), numero di
strati, peso totale, centro di massa e ingombro calcolati tramite `verpal.metrics`. Dallo stesso pannello puoi aprire il file
dialog e generare al volo sia il JSON completo del progetto sia il file `#VERPAL-S7` pronto per il PLC Siemens, senza uscire
dall'interfaccia grafica.

L'applicazione stamperà il rapporto di riempimento, le informazioni sui blocchi generati, i controlli di collisione e il numero di snap point calcolati. I file prodotti dai pulsanti di export sono immediatamente pronti per il trasferimento via ethernet o seriale.

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
- **Pannello accostamenti della GUI** con override blocchi, anteprima etichette/collisioni e tabella riepilogativa delle prese.
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
