# Phase-1 dataset evaluation: why accuracy is 44%, and how to report it honestly

**Setup.** Gold-CSV run (`research/run_phase1_dataset_eval.py`): nutrition and ingredients taken from `fmcg_label_audit_dataset.csv` (n = 25). No OCR. Claim mapping from `backend/claim_mapper.py` + `fssai_rules.json`; verdicts from `backend/rule_engine.py`. Raw rows: `research/phase1_dataset_eval_raw.json`.

**Headline.** The 44% figure is **not** a failure of FSSAI numeric thresholds. It is an **evaluation-design artefact**: 14/25 packs never enter a Phase-1 rule because the front claim does not match any alias, the engine **abstains** (`UNKNOWN_CLAIM`), and the scorer treats abstention as a wrong boolean decision.

---

## 1. What Phase-1 can actually judge

The mapper is substring match on a small alias list (longest alias first). Canonical claims in `fssai_rules.json`:

| Canonical | Example aliases |
|---|---|
| `high_protein` | high protein, rich in protein, high in protein, protein rich |
| `source_of_protein` | source of protein, contains protein, protein source |
| `sugar_free` | sugar free, zero sugar, 0 sugar, no sugar |
| `low_sugar` | low sugar, low in sugar, reduced sugar |
| `no_added_sugar` | no added sugar, zero added sugar, 0% added sugar |
| `high_fibre` | high fibre / high fiber, rich in fibre |
| `source_of_fibre` | source of fibre, contains fibre |
| `low_fat` | low fat, low in fat, reduced fat |
| `percent_wholegrain` | 100% atta, 100% whole wheat / wholegrain |
| Prohibited terms (short-circuit) | 100% pure, 100% natural, prevent/treat/cure, … |

There is **no** alias for: quantitative protein (“20g Protein”), trans-fat-free, cholesterol-free, “50% less fat”, “lite/diet”, “naturally sweetened”, “multigrain”, “smart snacking”, fruit/wellness marketing, or “protein snack” without “high/source of protein”.

The engine is designed to say `UNKNOWN_CLAIM` rather than guess. That is correct system behaviour. The 2×2 scorer is not.

---

## 2. How the current scorer inflates error

`confusion_cell()` in the eval script:

- Positive class = **Non-Compliant** (GT `is_technically_compliant = False`).
- `COMPLIANT` → predicted negative.
- `NON_COMPLIANT` / `PROHIBITED` → predicted positive.
- **`UNKNOWN_CLAIM` / `INSUFFICIENT_DATA` are forced into the error cell for that GT**:
  - GT Non-Compliant + abstain → **FN**
  - GT Compliant + abstain → **FP**

`match` is also false whenever `system_label` is `Abstain (UNKNOWN_CLAIM)`, because gold is only Compliant / Non-Compliant.

So **abstention is scored as a false decision**. That is why precision on Non-Compliant collapses (12 of 14 “errors” are abstentions on packs the gold set calls Compliant).

---

## 3. Two metrics for the paper (same run)

### 3.1 Strict (current protocol)

Every row must emit Compliant or Non-Compliant. Abstain counts as incorrect.

| | Value |
|---|---|
| n | 25 |
| TP / FP / TN / FN | 2 / **12** / 9 / **2** |
| Correct / incorrect | 11 / 14 |
| Accuracy | **0.44** |
| Precision (Non-Compliant) | 2/(2+12) = **0.143** |
| Recall (Non-Compliant) | 2/(2+2) = **0.50** |
| F1 (Non-Compliant) | **0.22** |
| Status mix | COMPLIANT 9, UNKNOWN_CLAIM **14**, NON_COMPLIANT 1, PROHIBITED 1 |

Of the 14 FPs+FNs, **14 are `UNKNOWN_CLAIM`**. There are **zero** threshold mis-comparisons in this gold-CSV run.

### 3.2 Coverage-aware (recommended)

Exclude `UNKNOWN_CLAIM`. Report **coverage** separately from **accuracy on decided cases**.

Decided set (n = 11): ids 1, 2, 3, 5, 6, 8, 10, 13, 15, 18, 24.

| | Value |
|---|---|
| Coverage | 11/25 = **0.44** |
| Abstention rate | 14/25 = **0.56** |
| Decided TP / FP / TN / FN | **2 / 0 / 9 / 0** |
| Decided accuracy | **11/11 = 1.00** |
| Decided precision (NC) | **1.00** |
| Decided recall (NC) | **1.00** |
| Decided F1 (NC) | **1.00** |

Coverage equals strict accuracy **only because every decided case was correct**. That coincidence is useful in the paper: it shows the engine is conservative and accurate *where it has a rule*, not that “accuracy = coverage” in general.

**Suggested paper sentence.**  
*On 25 FMCG packs with gold nutrition (no OCR), Phase-1 maps 11/25 claims (coverage 44%). Conditional on a mapped claim, technical compliance accuracy is 11/11. Treating `UNKNOWN_CLAIM` as a false 2×2 decision yields 44% accuracy, 0.14 precision and 0.22 F1 on Non-Compliant — those figures measure coverage, not threshold error.*

---

## 4. Product-level breakdown

### 4.1 Decided and correct (11) — rules actually fired

| ID | Product | Front claim | Mapped as | Status | GT |
|---|---|---|---|---|---|
| 1 | Bagrry's No Added Sugar Muesli | No Added Sugar / 0% Added Sugar | No Added Sugar | COMPLIANT | Compliant |
| 2 | Sunfeast Farmlite Digestive | 0% Added Sugar | No Added Sugar | COMPLIANT | Compliant |
| 3 | Pintola peanut butter | Zero Added Sugar / 100% Peanuts | No Added Sugar | COMPLIANT | Compliant |
| 5 | Epigamia Greek Yogurt | Zero Added Sugar | No Added Sugar | COMPLIANT | Compliant |
| 6 | Harvest Gold 100% Atta Bread | 100% Atta / Brown Bread | 100% Atta / Wholegrain | NON_COMPLIANT (maida) | Non-Compliant |
| 8 | McVitie's Digestive | … High Fibre | High Fibre (6.1 ≥ 6.0) | COMPLIANT | Compliant |
| 10 | Mission Whole Wheat Wraps | 100% Whole Wheat Wraps | 100% Atta / Wholegrain | COMPLIANT | Compliant |
| 13 | Kellogg's Special K | High Protein & High Fiber … | High Protein (15 ≥ 10) | COMPLIANT | Compliant |
| 15 | Amul Kool Protein | High Protein Drink | High Protein (7.5 ≥ 5 liquid) | COMPLIANT | Compliant |
| 18 | Raw Pressery Coconut Water | 100% Pure … / Fresh | Prohibited term `100% pure` | PROHIBITED | Non-Compliant |
| 24 | Saffola Masala Oats | Heart Healthy / High Fibre & Protein | High Fibre (8.2 ≥ 3 liquid) | COMPLIANT | Compliant |

Notes for the paper:

- **Technical vs deceptive.** Several TN rows still set `is_deceptive=true` (juice concentrate, maltodextrin, fructose). Gold `is_technically_compliant` agrees with the numeric/ingredient **claim** rule, not with “healthy”. Do not score deception as the same 2×2 as technical compliance.
- **Multi-claim, first match.** McVitie’s “whole wheat & high fibre” maps only **High Fibre** (there is no “goodness of whole wheat” rule; `percent_wholegrain` needs “100% …”). Special K maps **High Protein**, not High Fibre (`high protein` is a longer alias than `high fibre`, and both strings are present). Masala Oats maps **High Fibre** because “High Fibre & Protein” does **not** contain the substring `high protein`.
- **Form inference** marked rusk and masala oats as `liquid` in this run. It did not flip any verdict here; it is a future risk if more claims are mapped.

### 4.2 Strict “FP” — all 12 are abstentions on GT-Compliant packs

These are **not** false non-compliance flags. The engine said “I cannot judge this claim.” The scorer put them in FP because GT is Compliant.

| ID | Product | Front claim | Why unmapped | Gold clause (what GT is about) |
|---|---|---|---|---|
| 7 | Maggi Atta Noodles | Richness of Atta / Wholesome | No “richness of atta” / “wholesome” alias; not `100% atta` | Cake flour is 85.3% atta (not a 100% wholegrain claim) |
| 9 | Too Yumm! chips | Multigrain / Smart Snacking | No multigrain rule; **do not invent “Smart Snacking”** | Literal ≥2 grains |
| 11 | RiteBite Max Protein bar | 20g Protein / Healthy Meal Replacement | “20g protein” ≠ alias `high protein`; “meal replacement” unregulated here | Declared protein delivered (20 g) |
| 12 | Haldiram's Peanut Chikki | Power Packed Protein Snack | Puffery; not `high protein` / `source of protein` | Peanuts provide 14.5 g protein |
| 14 | RiteBite cookie | 10g Protein Per Cookie / Clean Snack | Per-serve quantity ≠ `high protein`; “clean snack” unregulated | 10 g protein per 55 g cookie |
| 16 | Réal Cranberry | Goodness of Cranberry / Antioxidant Rich | Marketing / implied nutrient; no Phase-1 antioxidant rule | Legal RTS fruit beverage category |
| 17 | Sting Energy | Berry Blast Energy | Flavour name, not a nutrient claim | Caffeinated beverage standard |
| 19 | Tetley Honey Lemon premix | Natural Honey & Lemon … Wellness | Wellness / “natural”; no NAS/sugar-free string | Ingredients declared |
| 20 | Nestea Iced Tea | Refreshing Real Tea with Lemon | Composition marketing | Powdered mix |
| 21 | Lay's Baked | Baked Not Fried / 50% Less Fat | Comparative fat claim not in Phase-1; `reduced fat` exists but string is “50% less fat” | Less fat than fried chips (~32 g) |
| 22 | Saffola Gold oil | Zero Cholesterol / Pro Heart | No cholesterol-free claim in Phase-1; “pro heart” is health-claim territory | Vegetable oil naturally 0 mg cholesterol |
| 25 | Britannia Toastea rusk | 0g Trans Fat / Wholesome Tea Snack | No trans-fat-free aliases; “wholesome” unregulated | Rounding: trans fat &lt; 0.2 g/serving as 0 g |

### 4.3 Strict “FN” — both are abstentions on GT-Non-Compliant packs

Again **not** missed numeric thresholds. The engine never evaluated the clause gold uses.

| ID | Product | Front claim | GT reason | If we mapped something real |
|---|---|---|---|---|
| 4 | Power Gummies | Naturally Sweetened / Healthy Diet Gummy | Health/wellness gummy with ~50% added sugars | “Naturally sweetened” is **not** a defined FSSAI nutrient claim. Do not alias it to No Added Sugar without a written rule. A future **health-claim / prohibited implied-health** check could catch “healthy diet”. |
| 23 | Bikaji Diet / Lite Mixture | Diet / Lite Snacking / Low Oil | “Diet/Lite” needs statutory **low-fat** criteria; fat is 25.5 g/100 g | Phase-1 already has `low_fat` (≤ 3 g solid) but aliases are only “low fat / low in fat / reduced fat”, **not** “diet”, “lite”, or “low oil”. Mapping `lite`/`diet` → `low_fat` would likely yield **NON_COMPLIANT** and a true TP — **only if** you treat those words as the FSSAI low-fat claim (cite the Advertising & Claims regulation, don’t invent a “low oil” threshold). |

### 4.4 True threshold / ingredient TP (the only real “catches”)

| ID | Product | Mechanism |
|---|---|---|
| 6 | Harvest Gold | `100% atta` + maida in ingredients → NON_COMPLIANT |
| 18 | Raw Pressery | Keyword `100% pure` → PROHIBITED (gold also flags “Fresh” on preserved coconut water) |

No row in this run is COMPLIANT vs gold Non-Compliant, or NON_COMPLIANT vs gold Compliant.

---

## 5. OCR is not the cause of 44%

This run **bypasses OCR**: panel fields and ingredients come from the CSV. Failures are **claim coverage + scoring of abstention**. OCR (wrong grams, missed ingredients, truncated claims) is a **future error class** for an end-to-end pipeline paper, not an explanation of these numbers.

---

## 6. Improvement plan (ordered by impact on *honest* metrics)

Do **not** chase 90% strict accuracy by mapping puffery onto fake rules. Raise **coverage of claims that FSSAI actually defines**, and **stop stuffing UNKNOWN into FP/FN**.

### 6.1 Report three numbers, always

1. **Coverage** = mapped & decided / n.  
2. **Conditional accuracy** (and P/R/F1) on decided rows only.  
3. **Abstention rate** and a table of unmapped claim types.

Optional fourth: strict 2×2 if a reviewer demands a single accuracy — labelled as “UNKNOWN counted as error”.

### 6.2 Claim mapping: extract an evaluable span from multi-claim strings

`front_claim` is often `A / B`. Mapper takes the **whole string** and needs an alias **substring**. High-impact, rule-backed extractions:

| Pattern in dataset | Map to (only if FSSAI rule exists) | Expected effect on this 25 |
|---|---|---|
| `20g Protein / Healthy Meal Replacement` | Content claim: declared protein vs panel (not necessarily `high_protein`) | id 11: likely COMPLIANT vs GT Compliant if you verify 20 g **as labelled** (per 100 g here). “Healthy meal replacement” stays unmapped / warning. |
| `10g Protein Per Cookie / Clean Snack` | Per-serve content vs serving size — **do not** silently use per-100 `high_protein` | id 14: needs serving mass; CSV protein is 18.2 g/100 g. |
| `0g Trans Fat / …` | Trans-fat free / 0 g trans fat (FSSAI rounding) | id 25: **needs a new rule + nutrient column** (CSV has no trans-fat field today). |
| `Baked Not Fried / 50% Less Fat` | Comparative “reduced fat” (typically ≥25% less than reference) | id 21: only if a reference fried-chip fat is specified; don’t hard-code 32 g without citing the comparison. |
| `Zero Cholesterol / Pro Heart` | Cholesterol-free (conditions on cholesterol **and** often sat fat / trans fat) | id 22: needs cholesterol in the panel; “Pro Heart” is a **health claim**, out of Phase-1 numeric set. |
| `Diet / Lite … / Low Oil` | `low_fat` **iff** you document that Diet/Lite ≡ low fat under FSSAI ads/claims | id 23: would become a real TP (25.5 g fat ≫ 3 g). **Do not** add “low oil” as a fake synonym without a threshold. |
| `Naturally Sweetened` | **No** Phase-1 numeric alias. Optional: ingredient/sweetener disclosure warning | id 4: keep UNKNOWN or add a **health-descriptor** policy, not a fake sugar-free pass. |
| `Smart Snacking`, `Wholesome`, `Clean Snack`, `Berry Blast`, `Antioxidant Rich` | **Do not map.** Stay UNKNOWN | Honest abstention |

Implementation sketch (eval or mapper): split on `/`; for each span, run `map_claim`; if gold `compliance_clause` names a specific claim, evaluate **that** span; else evaluate **all mappable** spans and aggregate (any-fail vs all-pass — pick one and state it).

### 6.3 Add Phase-1 aliases / rules only where FSSAI has a rule

Justified additions (cite 2.2.7 / Advertising & Claims, don’t invent):

- Quantitative protein / fibre **content** (“X g protein”) as a **declaration check**, distinct from High/Source of Protein.
- Trans-fat-free / 0 g trans fat.
- Cholesterol-free / 0 cholesterol (with sat-fat conditions if the regulation requires them).
- Comparative “X% less fat/sugar/sodium” with an explicit reference product.
- Aliases: `0g added sugar`, `lite`, `light`, `diet` → only onto **existing** `low_fat` / `low_sugar` after legal reading.
- `source of protein` will **not** match “Power Packed Protein Snack” unless you add a puffery alias — that is scientifically weak; prefer leaving id 12 uncovered.

Unjustified: Smart Snacking, Wholesome, Clean, Antioxidant Rich, Meal Replacement, Naturally Sweetened as NAS.

### 6.4 Multi-claim rows: evaluate the clause gold uses

Gold is often about **one** of several slogans (fibre vs “heart healthy”; protein grams vs “healthy meal replacement”; 0 g trans fat vs “wholesome”). Scoring the wrong conjunct, or abstaining because the other conjunct is puffery, will keep coverage low even after more aliases.

### 6.5 Do not change the rule engine to “guess” unmapped claims

`UNKNOWN_CLAIM` is the honest output. Changing production to force COMPLIANT/NON_COMPLIANT on unmapped text would **raise strict accuracy and destroy validity**.

### 6.6 Secondary (will matter once coverage rises)

- Form inference (solid vs liquid) for oats, rusks, premixes.
- Per-100 vs per-serve (protein cookie, 200 ml lassi sugars).
- Deception flags as a **separate** task (hidden sugars, 8% millet, 3.5% cranberry) — that is closer to the project’s research story than technical 2×2.
- OCR error analysis on the same 25 packs as a second experiment.

---

## 7. Production code

No rule-engine or mapper change in this analysis pass. A small alias dump without new FSSAI rules would move a few UNKNOWN rows into decided COMPLIANT and inflate coverage without new science. Implement aliases only with a cited rule, then re-run:

```text
python research/run_phase1_dataset_eval.py
```

and quote **both** strict and coverage-aware numbers.

---

## 8. Checklist for the next eval cycle

- [ ] Eval script: emit `decided_n`, `coverage`, `accuracy_decided`, P/R/F1_decided; keep strict 2×2 labelled “UNKNOWN = error”.
- [ ] Split `front_claim` on `/` and map each span.
- [ ] Align evaluation claim with `compliance_clause` when it names a regulated claim.
- [ ] Add FSSAI-backed: trans-fat-free, cholesterol-free, comparative reduced-fat, Diet/Lite → low fat (if legally supported).
- [ ] Add CSV columns needed (trans fat, cholesterol, serving size) before scoring those claims.
- [ ] Leave marketing puffery as UNKNOWN; table them as OOD claims.
- [ ] Separate technical-compliance vs deception metrics.
- [ ] Run OCR-on vs gold-CSV as a distinct error analysis.
