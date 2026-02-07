# ESP32-EMU - Console Retro Gaming DIY

Progetto personale per la costruzione di una console di emulazione retro gaming basata su ESP32 WROVER, utilizzando il firmware ESPlay Retro Emulation.

## Panoramica

Questo progetto documenta la costruzione di una console portatile per emulare sistemi retro gaming classici, basata sull'hardware ESPlay Micro e sul firmware open source di [pebri86](https://github.com/pebri86/esplay-retro-emulation).

## Emulatori Supportati

- **Nofrendo** - Emulatore NES/Nintendo
- **GNUBoy** - GameBoy e GameBoy Color
- **SMSPlusGX** - Sega Master System, Game Gear e Coleco Vision
- **Atari** - Sistemi Atari
- **PC Engine** - NEC PC Engine/TurboGrafx
- **ZX-Spectrum** - Sinclair ZX Spectrum
- **MSX** - Standard MSX

> Nota: A causa dei 4MB di Flash ROM, solo 3 emulatori possono essere precaricati contemporaneamente.

## Funzionalita Aggiuntive

- Menu in-game per tutti gli emulatori
- Audio Player integrato (WAV, MP3, OGG, FLAC)
- Launcher ESPlay con interfaccia UGUI
- WiFi e Bluetooth 4 BLE integrati

## Specifiche Tecniche (ESPlay Micro)

| Componente       | Specifica                   |
| ---------------- | --------------------------- |
| Processore       | ESP32 WROVER dual-core      |
| Flash            | 4MB integrato               |
| PSRAM            | 4MB integrato               |
| Display          | 2.4" ILI9341 TFT Panel      |
| Audio DAC        | UDA1334A I2S                |
| Jack Audio       | 3.5mm                       |
| Storage          | Slot microSD (SDMMC 1-line) |
| Caricatore       | TP4056 Li-Po integrato      |
| USB-Serial       | CH340C                      |
| Dimensioni PCB   | 100 x 50 mm                 |
| Porta Espansione | I2C                         |

## Lista Componenti da Acquistare

### 1. Scheda Principale - ESPlay Micro
- **Prodotto**: ESPlay Micro - Console DIY ESP32 WROVER
- **Prezzo**: ~27 EUR
- **Link**: [AliExpress](https://it.aliexpress.com/item/1005010451380752.html)
- Include: 1x ESPlay Micro, 1x Cavo USB, 1x Scheda SD

### 2. Batteria LiPo
- **Prodotto**: Batteria ai polimeri di litio 3.7V 5000mAh (955565)
- **Prezzo**: ~8 EUR
- **Link**: [AliExpress](https://it.aliexpress.com/item/1005008867815394.html)

### 3. Scheda MicroSD (opzionale, per ROM aggiuntive)
- **Prodotto**: SanDisk Ultra Micro SD (32GB/64GB/128GB)
- **Prezzo**: ~1 EUR (32GB)
- **Link**: [AliExpress](https://it.aliexpress.com/item/1005007498167692.html)

### Costo Hardware Totale: 35 EUR

## Case/Scocca 3D

Partendo dal modello originale "ESPlay Micro V2 Case" di PierreGG, ho sviluppato un **case custom V7** generato parametricamente tramite script Python + trimesh, ottimizzato per la stampa 3D.

- **Modello originale**: [Thingiverse - ESPlay Micro V2 Case](https://www.thingiverse.com/thing:5592683)
- **Case custom V7**: `model_3d_cover_v1/scripts/build_v7.py` (generazione automatica via Docker)
- **Output**: `model_3d_cover_v1/output/v7/` (STL per stampa + GLB per visualizzazione)

### Case V7 - Caratteristiche

| Caratteristica | Dettaglio |
| --- | --- |
| Top shell | Piatto superiore solido con cutout precisi per schermo, D-pad (croce), pulsanti (tondi) |
| Bottom shell | Profondita ottimizzata (19.3mm), batteria contro parete interna |
| Viti | M3 a incasso (countersunk) nel bottom, flush con la superficie |
| Pulsanti | Flangia di ritenzione 1mm per incastro tra board e top body |
| Porte | USB-C, audio jack, SD card slot, shoulder L/R |
| Dimensioni esterne | 103.3 x 58.3 x 27.3 mm |

### Assembly Chiusa

![Assembly chiusa - vista isometrica](docs/images/assembly_closed_front_iso.png)

![Assembly chiusa - vista dall'alto](docs/images/assembly_closed_top.png)

### Assembly Esplosa

![Assembly esplosa - vista isometrica](docs/images/assembly_open_front_iso.png)

![Assembly esplosa - vista frontale](docs/images/assembly_open_front.png)

### Top Body - Dettaglio Cutout

![Top body V7 - dettaglio](docs/images/top_body_v7_detail.png)

### Come Generare il Case

```bash
cd model_3d_cover_v1
docker compose run --rm cover-tool /workspace/scripts/build_v7.py
```

I file STL per la stampa vengono generati in `output/v7/`:
- `top_body_v7.stl` - Scocca superiore
- `bottom_body_v7.stl` - Scocca inferiore
- `btn_assy_1_v7.stl` - Assembly pulsanti sinistri (D-pad + Start/Select)
- `btn_assy_2_v7.stl` - Assembly pulsanti destri (A/B/X)
- `shoulder_l.stl` / `shoulder_r.stl` - Tasti spalla

### Stampa 3D

Ho utilizzato un **servizio di stampa 3D online** per la realizzazione del case.

- **Costo stampa**: 30 EUR
- Include tutti i pezzi necessari per il case

### Materiali Necessari per il Case
- 4x viti M3 da 15mm
- Protettore schermo (opzionale): taglio laser su acrilico 3mm (file SVG incluso)

## Riepilogo Costi

| Voce                              | Costo      |
| --------------------------------- | ---------- |
| Hardware (ESPlay + Batteria + SD) | 35 EUR     |
| Stampa 3D Case                    | 30 EUR     |
| **Totale Progetto**               | **65 EUR** |

## Risorse e Link Utili

| Risorsa                  | Link                                                                                         |
| ------------------------ | -------------------------------------------------------------------------------------------- |
| Firmware ESPlay          | [GitHub - pebri86/esplay-retro-emulation](https://github.com/pebri86/esplay-retro-emulation) |
| Documentazione Ufficiale | [Makerfabs - ESPlay Micro](https://www.makerfabs.com/esplay-micro.html)                      |
| Case 3D                  | [Thingiverse - ESPlay Micro V2 Case](https://www.thingiverse.com/thing:5592683)              |

## Istruzioni di Build del Firmware

### Requisiti
- ESP-IDF v3.3
- FFmpeg installato e nel PATH

### Procedura
1. Clonare il repository: `git clone https://github.com/pebri86/esplay-retro-emulation.git`
2. Editare `mkrelease.sh` con i percorsi corretti
3. Eseguire `./mkrelease.sh` per generare `esplay-retro-emu.fw`
4. Copiare il file in `esplay/firmware/` sulla scheda SD
5. Avviare la console tenendo premuto il tasto B (modalita bootloader)
6. Flashare il firmware dal menu

## Istruzioni di Assemblaggio

1. Saldare la batteria LiPo ai connettori della scheda ESPlay Micro
2. Inserire la scheda microSD con le ROM
3. Stampare il case 3D
4. Assemblare il tutto con le viti M3
5. (Opzionale) Applicare il protettore schermo in acrilico

## Struttura Directory SD Card

```
/
├── esplay/
│   └── firmware/
│       └── esplay-retro-emu.fw
├── roms/
│   ├── nes/
│   ├── gb/
│   ├── gbc/
│   ├── sms/
│   └── gg/
└── music/
    └── (file WAV, MP3, OGG, FLAC)
```

## Note Legali

- Il firmware ESPlay e rilasciato sotto licenza MIT
- Utilizzare solo ROM di giochi di cui si possiede l'originale
- Il case 3D e rilasciato sotto licenza Creative Commons BY 4.0

## TODO

- [x] Ordinare i componenti
- [x] Stampare il case 3D
- [ ] Assemblare l'hardware
- [ ] Flashare il firmware
- [ ] Testare gli emulatori
- [ ] Documentare il processo con foto

---

*Progetto basato sul lavoro di [Fuji Pebri](https://github.com/pebri86) e della community ESPlay.*
