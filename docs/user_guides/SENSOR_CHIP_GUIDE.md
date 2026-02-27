# Affilabs.core v2.0.5 — Sensor Chip Guide

**Last Updated:** February 24, 2026  
**Audience:** All users handling SPR sensor chips

---

## Overview

The SPR sensor chip is the consumable sensing element at the heart of every measurement. It consists of a glass substrate coated with a thin gold film, optically coupled to the instrument prism. Proper handling is essential for reliable results.

---

## Available Surface Chemistries

| Surface | Description | Typical Use |
|---------|------------|-------------|
| **Bare gold** | Unmodified gold film | Custom surface chemistry, thiol SAMs, direct adsorption |
| **COOH (carboxyl)** | Carboxymethyl dextran or alkane-thiol COOH | Amine coupling (EDC/NHS), most protein ligands |
| **NTA** | Nitrilotriacetic acid | His-tagged protein capture (via Ni²⁺) |
| **Biotin** | Biotinylated surface | Streptavidin capture, then biotinylated ligand |
| **Lipid-ready** | Hydrophobic alkane-thiol | Lipid bilayer / liposome capture |

> **Surface selection:** Contact Affinite Instruments to discuss which surface is best for your assay (info@affiniteinstruments.com).

---

## Handling Protocol

### Critical Safety Warning

**Do NOT touch the gold surface with fingers, tools, or any solid object.** The gold film is nanometers thick and will be permanently damaged by physical contact.

### Before Use

1. **Storage:** Keep chips in their protective case, gold side facing up, at room temperature (15–25 °C)
2. **Inspection:** Hold the chip by the edges only. Look for visible scratches or discoloration — discard damaged chips
3. **Equilibration:** Allow the chip to reach room temperature before use (especially if stored in a refrigerator)

### Installation

1. **Clean the prism surface** with lens paper and ethanol (if needed)
2. **Apply a thin layer of refractive index matching oil** to the prism surface
3. **Place the chip gold-side-up** on the prism, pressing gently on the edges only
4. **Ensure full optical contact** — no air gaps or oil bubbles between chip and prism
5. **Secure the flow cell** on top of the chip according to your instrument model

### During Use

- **Always keep the gold surface wet** once buffer has been applied. Drying causes irreversible surface contamination.
- **Avoid air bubbles** in the flow channel. Air bubbles cause:
  - Signal spikes and baseline jumps
  - Potential surface damage from meniscus forces
  - Loss of SPR coupling in the affected area
- **Flow buffer before sample.** Establish a stable baseline in running buffer (PBS, HBS, etc.) for at least 5 minutes before any injection.
- **Monitor the signal.** A stable, flat baseline indicates the chip is performing correctly. Drifting baseline (>0.5 nm/min after warm-up) may indicate surface degradation.

### After Use

1. **Flush with buffer** — run at least 3 mL of buffer through the flow cell
2. **Remove the chip** by gently sliding it off the prism from the edge
3. **Rinse with deionized water** if storing; do not use detergent
4. **Dry only for storage** — use gentle nitrogen gas if available; otherwise air-dry in a clean environment

---

## Chip Reuse

### Can chips be reused?

It depends on the surface and what was immobilized:

| Scenario | Reusable? | Notes |
|---------|----------|-------|
| **Bare gold — thiol SAMs** | Yes (3–5× typical) | Strip with piranha etch or UV-ozone, re-functionalize |
| **COOH — covalent amine coupling** | Limited (same ligand) | Regeneration can recover analyte binding if surface is not saturated |
| **COOH — new ligand needed** | No | Covalent ligand cannot be removed without destroying the surface |
| **NTA — His-tag capture** | Yes (10–20×) | Strip with EDTA + imidazole, re-charge with Ni²⁺ |
| **Biotin-streptavidin** | Limited | Streptavidin is essentially irreversible; analyte can be regenerated |

### Regeneration

Regeneration removes bound analyte while preserving the immobilized ligand:

| Regeneration Solution | Use For | Concentration | Contact Time |
|----------------------|---------|--------------|-------------|
| Glycine-HCl | Most protein interactions | 10 mM, pH 1.5–2.5 | 30–60 s |
| NaOH | Stubborn binding, lipids | 10–50 mM | 15–30 s |
| SDS | Non-specific binding cleanup | 0.05–0.5% | 15–30 s |
| EDTA | NTA/His-tag strip | 350 mM, pH 8.0 | 60 s |

> **Tip:** Start with the mildest regeneration condition and increase stringency only if needed. Harsh regeneration degrades the ligand.

---

## Troubleshooting

| Symptom | Likely Cause | Solution |
|---------|-------------|---------|
| No SPR dip visible | Chip installed upside-down, no index oil, air gap | Reinstall chip; check oil contact |
| SPR dip at wrong wavelength | Wrong buffer refractive index, contaminated surface | Switch to clean buffer; try new chip |
| Unstable baseline (>1 nm/min) | Air bubbles, temperature drift, surface degradation | De-gas buffer; wait for thermal equilibrium; try new chip |
| Low binding response | Inactive ligand, wrong orientation, surface blocked | Optimize immobilization; check ligand activity |
| High non-specific binding | Contaminated surface, inadequate blocking | Block with BSA or ethanolamine; use fresh chip |
| Signal drop after regeneration | Ligand denatured by harsh regen | Use milder conditions; reduce regen contact time |

---

## Storage

| Condition | Duration | Method |
|-----------|---------|--------|
| **Short-term (hours)** | Same day | Leave in buffer in flow cell |
| **Medium-term (days)** | Up to 1 week | Store in buffer at 4 °C in sealed container |
| **Long-term (weeks)** | Up to 3 months | Dry under nitrogen, store in protective case at room temperature |
| **Functionalized surface** | Varies | Follow surface-specific recommendations |

> **Never freeze sensor chips.** Ice crystal formation damages the gold film.

---

## Ordering

Contact Affinite Instruments for sensor chip orders:

- **Email:** info@affiniteinstruments.com
- **Specify:** Surface chemistry, quantity, and instrument model (P4SPR, P4PRO)

---

**© 2026 Affinite Instruments Inc.**
