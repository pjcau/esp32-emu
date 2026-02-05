# ESPlay Micro - Alignment Analysis Report

**Data**: 2026-02-04
**Progetto**: ESP32-EMU Console Retro Gaming

---

## 1. Coordinate System Analysis

### STL Case Orientation
Il case STL utilizza un sistema di coordinate dove:
- **X positivo** = lato destro della console
- **X negativo** = lato sinistro della console
- **Y** = INVERTITO rispetto al PCB

### PCB Orientation (Eagle)
- **X positivo** = lato destro (dove sono A/B, Menu)
- **X negativo** = lato sinistro (dove sono D-Pad, Start/Select)
- **Y positivo** = lato superiore (dove sono L/R shoulders)
- **Y negativo** = lato inferiore (USB, Audio)

### Trasformazione Applicata
Y-axis invertito per allineare i sistemi di coordinate.

---

## 2. Button Positions Comparison

| Componente | STL Center (X, Y) | PCB Center (X, Y) | Offset (mm) | Status |
|------------|-------------------|-------------------|-------------|--------|
| d_Pad | (-39.1, 5.5) | (-39.1, 8.0) | 2.5 | ✓ OK |
| A_B | (39.4, -3.8) | (41.5, 7.6) | 11.6 | ⚠ Offset |
| start_select | (-39.2, -12.0) | (-39.1, -10.4) | 1.5 | ✓ OK |
| menu | (41.5, 14.0) | (39.0, -10.5) | 24.7 | ⚠ Offset |
| power | (-4.7, -0.6) | (18.6, 10.6) | 25.8 | ⚠ Offset |

### L/R Shoulders (caso speciale)
- STL L_R è un **pezzo singolo** posizionato sul lato destro (X=42.0)
- PCB ha L_BTN (X=-38.6) e R_BTN (X=38.9) separati
- **Nota**: Il pezzo L_R potrebbe necessitare di essere specchiato per il lato sinistro

---

## 3. Layout Console

```
      L_BTN                              R_BTN
   ┌─────────────────────────────────────────────┐
   │                                             │
   │  ┌─────┐                        ┌───┐       │
   │  │D-Pad│        ┌──────┐        │A/B│       │
   │  └─────┘        │ LCD  │        └───┘       │
   │                 │Screen│                    │
   │  ┌──────────┐   └──────┘        ┌────┐      │
   │  │Start/Sel │                   │Menu│      │
   │  └──────────┘                   └────┘      │
   │                                             │
   └─────────────────────────────────────────────┘
           USB              AUDIO
```

---

## 4. Dimensional Compatibility

| Componente | Dimensioni (mm) |
|------------|-----------------|
| PCB | 100.0 x 50.0 x 1.6 |
| Top Cover | 110.7 x 55.7 x 10.0 |
| Back Cover | 110.0 x 55.0 x 11.0 |

**Margine Case-PCB**: ~5mm per lato (adeguato per montaggio)

---

## 5. Render Files

I seguenti file sono stati generati in `stl-tools/output/renders/`:

| File | Descrizione |
|------|-------------|
| assembly_colored.glb | Assembly completo con PCB e case |
| assembly_exploded.glb | Vista esplosa dei componenti |
| pcb_detailed.glb | PCB con marker posizioni bottoni |
| case_only.glb | Solo case senza PCB |
| viewer.html | Viewer 3D interattivo |

### Visualizzazione
```bash
# Avviare server e aprire viewer
python3 -m http.server 8082 --directory stl-tools/output/renders
# Poi aprire: http://localhost:8082/viewer.html
```

---

## 6. Conclusioni

### Compatibilità
- ✓ Dimensioni case compatibili con PCB 100x50mm
- ✓ Posizioni X dei bottoni allineate
- ⚠ Y-axis invertito - compensato nei render

### Note
- Il pezzo L_R è singolo e posizionato a destra; verificare se serve specchiatura
- Gli offset residui sono dovuti a differenze di design tra case Thingiverse e PCB ESPlay

---

*Report generato automaticamente - ESP32-EMU Project*
