# STL Position Corrections Report

## Summary
These STL files have been corrected to align with the ESPlay Micro PCB button positions.

## Corrections Applied

| Part | Original (X, Y) | Correction | New (X, Y) |
|------|-----------------|------------|------------|
| A_B | (39.4, 3.8) | (+2.1, +3.7) | (41.5, 7.6) |
| L_R | (42.0, 2.0) | (+0.0, +0.0) | (42.0, 2.0) |
| back_cover | (0.2, 0.3) | (+0.0, +0.0) | (0.2, 0.3) |
| d_Pad | (-39.1, -5.5) | (-0.0, +13.6) | (-39.1, 8.0) |
| frame | (-0.6, 1.9) | (+0.0, +0.0) | (-0.6, 1.9) |
| menu | (41.5, -14.0) | (-2.5, +3.5) | (39.0, -10.5) |
| power | (-4.7, 0.6) | (+23.3, +10.0) | (18.6, 10.6) |
| start_select | (-39.2, 12.0) | (+0.1, -22.4) | (-39.2, -10.4) |
| top_cover | (1.5, 0.2) | (+0.0, +0.0) | (1.5, 0.2) |

## L/R Shoulder Buttons
- Original L_R.stl was only for the right side
- Created separate L.stl (mirrored) and R.stl files
- Both positioned to match PCB L_BTN and R_BTN positions

## Files Ready for Printing
All STL files in this directory are ready for 3D printing with:
- Wall thickness >= 1.0mm
- Correct positions aligned to PCB
- Preserved original geometry (only translated, not scaled)
