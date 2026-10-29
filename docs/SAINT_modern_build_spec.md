# pySAINT — Build Specification for a Modern Re-implementation of SAINT
**Systems Analysis of Integrated Networks of Tasks (USAF AMRL / Pritsker & Associates, 1974–1978)**
Version 0.1 (draft) · 29 Oct 2026 · Prepared for Quinn Michaels

---

## Executive Summary
1. **pySAINT** is a Python 3.11+ package that reproduces SAINT's combined discrete/continuous man-machine network simulation semantics as documented in *The SAINT User's Manual* (AMRL-TR-77-62, 1978), while modernizing I/O, statistics and extensibility.
2. Core = a **discrete-event task-network kernel** (PR1/PR2 release, DIFF, INCM, priority queue with 4 ranking rules, AND/OR resources, 4 branching types, clearing, network/distribution-set modification, sink termination) coupled to a **variable-step RK integrator** for SS()/DD() state variables with **monitor threshold-crossing** location.
3. Two input front-ends feed one validated schema: a **legacy free-form card parser** (all 33 card types of Manual Table 5) and a **modern YAML/JSON** format.
4. All nine legacy user subprograms (USERF, MODRF, PRIOR, STATE, INTLC, …) become typed Python **plugin hooks**; the ~45 support routines become a `ctx` API.
5. Outputs: statistics-task summaries, resource utilization, state-variable stats/plots/tables, histograms, multi-iteration summaries; CSV/Parquet export replaces the SPSS export.
6. Execution error codes 3001–3604 map 1:1 to a typed exception hierarchy; input errors are reported with card/field locations.
7. Validation: unit tests per feature, regression tests built from every worked example in the manual, and **statistical (distributional) golden tests** instead of bit-exact FORTRAN replay (DRAND was machine-specific).
8. Optional Phase 2: hierarchical sub-models, parallel Monte Carlo with CIs, LLM "describe a system → SAINT model + report" assistant, web graph editor/visualizer.
9. Roadmap: 6 phases, ~14–18 engineer-weeks to a faithful v1.0. Key risk: 20 OCR-ambiguous/unspecified details resolvable only with AMRL-TR-77-61 (Instruction Manual) and AMRL-TR-77-63 (Program Documentation) — see §13.3.

---

## 0. Sources and Conventions
| Tag | Document | Use |
|---|---|---|
| **[UM]** | Wortman, Duket, Seifert, Hann, Chubb — *The SAINT User's Manual*, AMRL-TR-77-62, June 1978 (144 pp., OCR) | **Primary normative source.** "UM p.NN" = printed page number. |
| **[SO]** | Seifert — *SAINT: A Combined Simulation Language for Modeling Man-Machine Systems* (NASA NTRS 19790025671) | Concepts, continuous component, outputs |
| **[WDS]** | Wortman, Duket, Seifert — *Modeling and Analysis Using SAINT…*, AMRL-TR-77-78, 1977 | Source/sink/statistics tasks, hierarchical modeling, user subprograms |
| **[CAT]** | JCS SAGA *Catalog of Wargaming and Military Simulation Models*, 9th ed., 1982 | Context only (SAINT is not listed); example-scenario domains |

Markers: **DESIGN DECISION** = our choice where sources are silent or we deliberately modernize · **ASSUMPTION** = inferred behavior to confirm against AMRL-TR-77-61/-63 · **OCR-AMBIGUOUS** = scan garbled/inconsistent · **Qn** = open question in §13.3. Unmarked rules are stated by the cited source.

---

## 1. Purpose, Scope, Non-Goals, Fidelity
### 1.1 Purpose
An open, testable, scriptable re-implementation of SAINT that (a) runs legacy SAINT card decks with semantically faithful results and (b) offers modern authoring, analysis and extension for human-performance / man-machine modeling.

### 1.2 In scope (v1.0)
- Everything in UM Sections II–VII: task symbolism (17 codes), monitors (4 codes), all input data types, user-written subprograms, user support subprograms, input/execution error handling.
- Multiple networks per deck (SIM/FIN), multiple iterations per network.
- Statistics, histograms, plots/tables (matplotlib + text tables), exports.

### 1.3 Non-goals
- FORTRAN overlay structure (UM §IX), COMMON-block sizing (UM §X), device units NCRDR/NPRNT/NRNIT/NRENT/NPUNCH (UM p.119), line-printer plots. Array-dimension limits (UM Table 16) become optional, configurable validation limits (DESIGN DECISION).
- Bit-identical random streams with the original DRAND (machine-specific by design, UM p.119).
- Force-on-force combat modeling (the domain of most [CAT] models). pySAINT stays a task-network/human-performance tool.
- The separate "no error checking" input processor (UM p.103): modern parsing is fast; a `--no-validate` flag replaces it.

### 1.4 Fidelity goals
| Area | Target |
|---|---|
| Network semantics (release, queueing, branching, clearing, modifications, sink termination) | **Faithful** to UM; ambiguities flagged and configurable |
| Distributions | Faithful parameterization and min/max **clamping** (not truncation), UM p.45 |
| Card format | Faithful grammar incl. `(n)` field skip, continuation, `*` terminator, 8-char alpha significance |
| Continuous integration | Semantically equivalent (variable-step embedded RK with AAERR/RRERR, DTMIN/DTMAX, DTSAV); not numerically identical to RKE |
| Outputs | Same information content; modern layout |
| Random numbers | Reproducible within pySAINT (seeded numpy `Generator`); statistically equivalent to SAINT |

---

## 2. Concept Glossary
| Term | Definition (source) |
|---|---|
| **Task (node)** | Basic network element with three functions: release, performance, successor identification (UM p.10). Integer task number. |
| **PR1 / PR2** | Predecessor completions required for first / subsequent release (UM p.10, Fig.1). TAS f4/f5; defaults PR1 = 0 for source tasks else 1, PR2 = 9999 (UM p.60). |
| **Release** | Task becomes eligible when its outstanding requirement count reaches 0 (UM p.10; [SO]). |
| **Source task** | Released automatically at simulation start ([WDS]); requires no predecessor completions (UM p.21 Ex.3). TAS f10 `SO`. |
| **Sink task** | Possible end point; the network (iteration) completes when the number of sink completions equals GEN f8 ([WDS]; UM p.40). TAS f10 `SI`. |
| **Statistics task** | Task with an STA card collecting statistics ([WDS]; UM p.62). |
| **Branch** | Directed precedence link; selection by deterministic, probabilistic, conditional-take-first or conditional-take-all rules (UM Table 2). Selecting a branch reduces the successor's requirement count by one ([SO]). |
| **Information packet** | Record of information attributes (IA) flowing through the network; the packet residing at a task is transmitted along each selected branch ([SO]). Also carries a **mark time** (TMARK, UM p.97). |
| **INCM** | Information choice mechanism: which arriving packet a task keeps — FIRST, LAST (default), BIG attr, SMALL attr (UM p.15, p.61; [SO] "default … pass the last one arriving"). |
| **Resource** | Operator or equipment performing tasks; has a resource-attribute (RA) packet; busy/idle status ([SO]; UM p.18). |
| **System attribute (SA)** | Global attribute that does not flow (POP f5; [SO]). |
| **Distribution set (DS)** | Numbered distribution type + parameters (DIS card, UM p.45). |
| **Moderator function** | User code (MODRF) altering a task's baseline time TTIME or first-branch probability PFIRB; active/inactive status (UM p.92, p.54, p.64). |
| **User function (UF)** | `USERF(I)` value function referenced as a function type (UM p.93). |
| **UTCH** | Up to 25 real user-defined characteristics per task, via GETTC/PUTTC (UM p.63, p.96). |
| **Marking** | Stamping the packet with current time, used later for INTERVAL statistics (UM p.15–16, p.21, p.62). |
| **Task modification (NMO)** | Substituting the description and output side of one task for another upon a task completion (UM p.27 Fig.2, p.72). |
| **DS modification (DMOD/DMO)** | Replacing one distribution set by another upon task completion (UM p.14, p.73). |
| **Task clearing (TCLR/TCL)** | Halting a specified task in progress when another task completes; optional signal (UM p.19, p.74). |
| **Resource clearing (RCLR/RCL)** | Halting whatever task a resource is performing; optional signal (UM p.17, p.75; [SO]). |
| **Signal** | Reducing a task's predecessor requirement by one, caused by clearing or a threshold crossing (UM p.27). |
| **SS(i)** | State variable defined by algebraic/difference equation in STATE; `SSL(i)` = value at last update, `DTNOW` = step (UM Fig.5 p.29; [SO]). |
| **DD(i)** | Derivative of SS(i) for differential equations, integrated by Runge-Kutta-England (RKE) ([SO], [WDS]). |
| **Switch IS(k)** | Integer logical variable set by task completion (SWIT) or monitor (MSWT); read in STATE, conditions, user code (UM p.19, p.31, p.92). |
| **Regulation (REGL)** | Discrete change of SS(i) on task completion: equal / increase / decrease by `CADD + CMULT·var` (UM p.17, p.77). |
| **Monitor** | Watches an SS/DD variable against threshold `CADD + CMULT·var` for a crossing (POSITIVE/NEGATIVE/BOTH) within a tolerance; on crossing signals tasks (MTAS) and sets switches (MSWT) (UM p.29–31, p.79–81). |
| **Iteration** | One replication of the network until the sink condition (count = GEN f7). |
| **Network run** | All iterations of one network; a deck can hold several networks separated by SIM (UM p.33, p.37). |

---

## 3. Architecture
### 3.1 Technology choices
Python ≥ 3.11; `numpy` (Generator/PCG64 + SeedSequence), `scipy` (stats; optional `solve_ivp`), `pandas` (results), `pyarrow` (Parquet), `pydantic` v2 (schema + validation + JSON Schema), `matplotlib` (plots), `ruamel.yaml`, `typer` (CLI), `rich` (text reports), `networkx` (graph checks/export), `pytest` + `hypothesis` (tests). Packaging via `pyproject.toml` (hatch), `ruff`, `mypy --strict` on core.

### 3.2 Package layout
```
pysaint/
  __init__.py            # public API: load_model, Simulation, run
  model/
    schema.py            # pydantic models (§4, §5.4)
    enums.py             # FunctionType, BranchType, StatType, Timing, ...
    validate.py          # cross-reference checks -> InputDiagnostic list (§10.1)
  legacy/
    lexer.py             # card/record tokenizer (§5.1)
    cards.py             # data-driven per-card field tables (§5.2, App. B)
    parser.py            # records -> schema; deck/SIM/FIN handling
    writer.py            # schema -> card deck (round trip)
  io/ yaml_io.py, json_io.py
  kernel/
    engine.py            # Simulation; event loop (§6)
    events.py            # calendar (heap) with tie-break keys
    tasks.py             # task runtime state (counts, packets, instances)
    resources.py         # busy/idle, utilization accumulators
    queue.py             # waiting file; ranking rules 1-4
    branching.py         # DET/PRO/CFI/CAL
    effects.py           # ATAS, MOD, NMO, DMO, TCL, RCL, SWI, REG
    rng.py               # streams & distributions (§4.6)
  continuous/
    integrator.py        # embedded RK, DTMIN/DTMAX/AAERR/RRERR (§7)
    monitors.py          # threshold functions, crossing location
    state_api.py         # SS/DD/SSL/IS views for STATE
  plugins/
    hooks.py             # Protocols for USERF, MODRF, PRIOR, STATE, INTLC, ...
    registry.py          # decorators, module path, entry points
    ctx.py               # support-subprogram API (GETIA ... DMPSV) (§8)
  stats/ collectors.py, task_stats.py, summary.py
  report/ text.py, plots.py, export.py
  errors.py              # exception hierarchy + code tables (§10)
  cli.py                 # saint run | validate | convert | graph | schema
  ext/                   # Phase 2: hierarchy, batch, llm, web
tests/  examples/  docs/
```

### 3.3 Data flow
```
cards (.dat) ──legacy.parser──┐
                              ├─► model.Model ──validate──► kernel.Simulation (+plugins)
YAML/JSON ────io.yaml_io──────┘                                   │ events, state traces
                                                                  ▼
                                         stats.collectors ─► report.text / plots / export
```
Modeling (schema) is strictly separated from analysis (kernel/stats), following [WDS]'s "separation of modeling and analysis".

---

## 4. Data Model (Task Description Codes and Semantics)
### 4.1 Value references ("function types")
Many fields take a *(function type, parameter)* pair (UM pp.55–60, 65):

| Code | Meaning | Allowed in |
|---|---|---|
| `DS,n` | Sample distribution set *n* | TIME, ATAS, IRA, ISA |
| `SC,x` | Constant = x ÷ scale factor (GEN f10) | TIME, ATAS, IRA, ISA |
| `UF,n` | `USERF(n)` | TIME, ATAS, IRA, ISA |
| `IA,a` | Information attribute *a* of the task's packet | TIME (TAS f6) |
| `RA,r-a` | Resource *r* attribute *a* (r in TAS f8) | TIME |
| `SA,a` | System attribute *a* | TIME |

Schema: `ValueRef{kind: DS|SC|UF|IA|RA|SA, param: int|float, resource: int|None}`.
- **OCR-AMBIGUOUS (Q15):** TAS/ATA/ISA say SC divides by "scale factor (Field 12 of GEN card)", IRA says "Field 2 1", but GEN lists the scale factor as **field 10** (UM p.40). DESIGN DECISION: GEN f10.
- The SC parameter field is typed **I** (integer) on TAS f7, ATA f8, IRA f5, ISA f4, so fractional constants come from the scale factor (e.g. `SC,575` with scale 100 = 5.75). DESIGN DECISION: the legacy parser truncates reals per UM rule 7b with a warning; the modern schema accepts floats directly.
- In the card OCR "PA" appears where "RA" is meant (TAS f8, ATA f4, PRO f3, CFI f7); the parser accepts both.

### 4.2 Task record (schema `Task`)
| Field | Code | Card/field | Type | Default | Notes |
|---|---|---|---|---|---|
| `id` | TSK | TAS f2 | int ≥1 | — | UM p.60 |
| `label` | LABL | TAS f3 | str (8 significant) | "" | UM p.15 |
| `pr1` | — | TAS f4 | int | 0 if source else 1 | |
| `pr2` | — | TAS f5 | int | 9999 | |
| `time` | TIME | TAS f6–f8 | ValueRef | `SC,0` | baseline TTIME |
| `priority` | PRTY | TAS f9 | float | 0.0 | dynamic via PRIOR/PUTPR |
| `role` | — | TAS f10 | NS/SO/SI | NS | |
| `diff` | DIFF | TAS f11 | bool | False | |
| `incm` | INCM | TAS f12–13 | FIRST/LAST/BIG/SMALL + attr | LAST | |
| `prec` | PREC | TAS f14 | float | 0.0 | higher processed first at equal times |
| `resources` | RESR | TAS f15–20 | AND/OR, ≤5 ascending ids | AND, [] | |
| `mark`,`stat` | MARK/STAT | STA | §4.4 | none | |
| `utch` | UTCH | UTC f3–27 | {1..25: float} | {} | |
| `moderators` | MODF | MOD | ≤10 (mfn, ACT/DEACT, TASK/PERM) | [] | §4.7 |
| `assignments` | ATAS | ATA | ≤6, one timing | [] | §4.8 |
| `branching` | output side | DET/PRO/CFI/CAL | §4.5 | none | no card ⇒ no successors |
| `network_mods` | Fig.2 | NMO | ≤10 (old, new) | [] | |
| `dist_mods` | DMOD | DMO | ≤10 (old, new) | [] | |
| `task_clear` | TCLR | TCL | ≤10 (task, signal\|0) | [] | |
| `resource_clear` | RCLR | RCL | ≤10 (res, signal\|0) | [] | |
| `switches` | SWIT | SWI | ≤10 (switch, int) | [] | |
| `regulations` | REGL | REG | ≤2 | [] | |

### 4.3 Semantics of the 17 task description codes (UM Table 1 p.13; examples pp.12–22)
1. **ATAS** — attribute assignments at REL, STA or COM (UM p.12–14, ATA p.65). Targets: IA (task's packet), RA (resource r attribute a), SA. Sources: DS/SC/UF. One ATA card per task and the timing field (f3) is outside the repeat group f4–f8 ⇒ **one timing point per task** in legacy input; the symbolism example on p.14 shows two assignments both at REL. Modern schema allows a timing per assignment (DESIGN DECISION; the legacy writer rejects mixed timings).
2. **DIFF** — if YES, only completions of *different* predecessors count toward release ([SO]: otherwise "the multiple occurrence of any predecessor may cause the task to be prematurely released"; UM p.14, TAS f11). ASSUMPTION: the set of counted predecessors resets at each release; signals (clearing/monitor) always count.
3. **DMOD** — on completion, references to DS *old* are redirected to DS *new* (UM p.14–15, p.73). POP f8 selects **I**nterchange vs **M**ultiple replacement (UM p.41). ASSUMPTION (Q19): Interchange swaps old↔new (a second application restores); Multiple applies a transitive alias map `ds_alias[old] = new`.
4. **INCM** — packet kept when several predecessor packets arrive before release: FIRST, LAST (default), BIG k (largest IA k), SMALL k (UM p.15, p.61). DESIGN DECISION: BIG/SMALL ties keep the earlier packet.
5. **LABL** — 8 significant characters (UM p.15).
6. **MARK** — mark the packet with TNOW at FPC (first predecessor completion), REL, STA or COM; STA f3–f4, default time COM (UM p.15–16, p.62). Read by TMARK; used by INT statistics.
7. **MODF** — moderator functions applied to the task (UM p.16). Initial status IMO (default inactive, p.54); per-task MOD card activates/deactivates for Task-only or Permanent duration (p.64). When a task's performance is being scheduled, MODRF(MFN, NNODE) is called for each **active** moderator function and may alter TTIME and PFIRB (p.92). ASSUMPTION: a MODF row on the symbol corresponds to MOD-card activations with duration *Task*.
8. **PREC** — for simultaneous completions the higher PREC is processed first (UM p.16–17). Default 0.
9. **PRTY** — scheduling priority (UM p.17, TAS f9). Ranking rule POP f9: 1 low value first, 2 high value first, 3 FIFO (default), 4 LIFO (UM p.41; the OCR prints "LILO" for LIFO; QRANK p.97 confirms LIFO). QRANK changes the rule at run time; PRIOR(ITASK) recomputes priority immediately before resources are assigned to released tasks (p.92); GETPR/PUTPR (p.97).
10. **RCLR** — on completion, for each (resource r, signal s): if r is busy, its current task is halted and r is freed; if s ≠ 0 task s is signaled. "If resource is not busy, no clearing is performed" (UM p.75). ASSUMPTION (Q7): no signal when nothing was cleared (UM p.27 ties signaling to a clearing).
11. **REGL** — on completion SS(i) ← op(SS(i), v), v = CADD + CMULT·X with X = SS(j) if j>0, DD(−j) if j<0, 0 if j=0; op ∈ Equal/Increase/Decrease; CMULT default 1, CADD 0, op default printed "E." ⇒ Equal (Q16); ≤2 per task (UM p.17–18, p.77). Example p.21: `SS(4) += SS(27)+3.25` ⇒ REG,54,4,27,1.,3.25,I.
12. **RESR** — AND: all listed resources required; OR: one of the listed resources required (UM p.18, TAS f15–20, ≤5, ascending). DESIGN DECISION: OR picks the lowest-numbered idle listed resource. No resources ⇒ task starts at release.
13. **STAT** — see §4.4.
14. **SWIT** — on completion IS(k) ← integer value (UM p.19, p.76).
15. **TCLR** — on completion, for each (task t, signal s): t, if in progress, is halted; if s ≠ 0 task s is signaled (UM p.19–20, p.74). ASSUMPTION (Q7): only in-progress instances are cleared; released-but-waiting instances remain.
16. **TIME** — baseline time from a ValueRef (UM p.20, TAS f6–f8). Negative TTIME after moderators ⇒ error 3007.
17. **UTCH** — values of user task characteristics 1..25 (UM p.20, p.63).

### 4.4 Statistics tasks (STAT) and the "16 combinations"
STA card (UM p.62): mark flag/time f3–f4; **statistic type** f5 ∈ {FIR, ALL, BET, INT, NUM, NO}; **collection time** f6 ∈ {REL, STA, COM, CLR}; histogram cells f7 (25), first-cell upper limit f8 (0.0), cell width f9 (1.0). Symbolism: `STAT BET STA (25.,20.,15.)` = between starts, 25 cells, first upper limit 20, width 15 (UM p.18–19).

[SO] says "there are sixteen possible combinations of interval and task completion statistics". **ASSUMPTION (Q1):** the four time-valued types (FIR, ALL, BET, INT) × four collection events (REL, STA, COM, CLR) = 16; NUM is a count statistic. Definitions (DESIGN DECISION following GASP/P-GERT conventions, to be verified):

| Type | Value recorded when collection event *E* occurs | Obs./iteration |
|---|---|---|
| **FIR** first | TNOW of the first occurrence of E | ≤1 |
| **ALL** | TNOW of every occurrence of E | n |
| **BET** between | TNOW − TNOW(previous E); first E only sets the reference | n−1 |
| **INT** interval | TNOW − packet mark time ("time since the last marking", UM p.21 Ex.2) | n |
| **NUM** number | count of occurrences of E (recorded at iteration end) | 1 |

The 16: FIR-REL, FIR-STA, FIR-COM, FIR-CLR, ALL-REL, ALL-STA, ALL-COM, ALL-CLR, BET-REL, BET-STA, BET-COM, BET-CLR, INT-REL, INT-STA, INT-COM, INT-CLR. Each statistic yields n, mean, sd, min, max and a histogram; summaries are controlled by OUT f6–7, f15–17.

### 4.5 Branching (UM Table 2 p.23; cards pp.67–71)
| Type | Card | Rule |
|---|---|---|
| Deterministic | DET (≤20) | all branches selected |
| Probabilistic | PRO (≤10) | exactly one selected at random; probability direct `(p)` or from attribute `(T,A)`, T ∈ IA, RA r, SA (Table 3 p.24) |
| Conditional take-first | CFI (≤5 conditional + 6th unconditional) | test in rank order; select first satisfied |
| Conditional take-all | CAL | select all satisfied |

Probabilistic: probabilities ≥0 (else 3004) and summing to 1.0 (else 3003) (UM p.105); PFIRB = probability of the first listed branch, may be changed by MODRF, must lie in [0,1] (3008/3009). ASSUMPTION (Q4): after PFIRB changes, the other branches are rescaled proportionally to sum to 1−PFIRB. DESIGN DECISION: sum tolerance 1e-6.

Conditional branch codes (UM Table 4 p.25; CFI fields p.69–70); TNOW = completion time, v(T,A) = attribute A of type T:
| Code | Condition |
|---|---|
| TLV,x / TGV,x | TNOW ≤ x / TNOW > x |
| TLA,T,A / TGA,T,A | TNOW ≤ v(T,A) / TNOW > v(T,A) |
| TVC,N / TVN,N | task N has / has not been completed |
| TAC,T,A / TAN,T,A | task number v(T,A) has / has not been completed |
| ALV,T,A,x / AGV,T,A,x | v(T,A) ≤ x / v(T,A) > x |
| ALA,T,A,B / AGA,T,A,B | v(T,A) ≤ v(T,B) / v(T,A) > v(T,B) |
| NO | unconditional (last branch only) |

CFI field mapping: f3 successor; f4 code; f5 value x, or the attribute holding the comparison value (A for TLA/TGA/TAC/TAN, B for ALA/AGA); f6 attribute compared (ALV/AGV/ALA/AGA); f7 attribute type (default IA if needed, else NO); f8 resource if RA. ASSUMPTION (Q5): "has been completed" = at least one completion in the current iteration. DESIGN DECISION: no CFI branch satisfied ⇒ no successor (logged).

### 4.6 Distributions (DIS card, UM p.45–46)
f2 set no., f3 type (default CO), f4–f7 parameters. **Samples are clamped**: below min ⇒ min, above max ⇒ max; "not sampling from a truncated distribution" (UM p.45).
| Code | Name | f4 | f5 | f6 | f7 | pySAINT generator |
|---|---|---|---|---|---|---|
| CO | Constant | value | – | – | – | value |
| NO | Normal | mean | min | max | sd | normal(mean, sd) → clamp |
| LO | Lognormal | mean | min | max | sd | lognormal with mean/sd of the variate → clamp (ASSUMPTION Q6) |
| BE | Beta | mean | min | max | sd | beta on [min,max] by moments (ASSUMPTION Q6) |
| GA | Gamma | mean | min | max | sd | shape (m/sd)², scale sd²/m → clamp (ASSUMPTION Q6) |
| UN | Uniform | – | min | max | – | uniform(min, max) |
| ER | Erlang | mean of each exponential (Erlang mean ÷ f7) | min | max | k | sum of k exponentials; k=1 ⇒ exponential → clamp |
| PO | Poisson | mean − min | min | max | – | min + Poisson(f4) → clamp ("not usually used to represent an interval of time") |
| BP | Beta-PERT | mode m | a (optimistic) | b (pessimistic) | – | beta on [a,b], mean (a+4m+b)/6, sd (b−a)/6 (ASSUMPTION Q6) |
| TR | Triangular | mode m | a | b | – | triangular(a, m, b) |
| WE | Weibull | α > 0 | min | max | β > 0 | F(x)=1−exp(−αx^β) ⇒ x=(−ln U/α)^(1/β) → clamp |
The routines BETA, ERLNG, GAMM, NPOSN, RLOGN, RNORM, TRNGL, UNFRM, WEIBL (UM Table 11 p.98) are exposed in `ctx.rng` with errors 3101–3127.

**Random streams (DESIGN DECISION):** numpy `Generator(PCG64)` from GEN f9 (default 71268659, UM p.40). `SeedSequence(seed, spawn_key=(iteration,))` per iteration, spawned into independent streams for task times, branching, attribute assignment and user `ctx.drand()`. Any iteration can be reproduced alone and run in parallel. `--legacy-single-stream` uses one stream in call order.

### 4.7 Moderator functions
Count POP f6; IMO initial status (≤24 per card, default inactive); MOD per task (≤10 updates; status default D, duration default T). Called when the task is scheduled to start, for each active mfn in ascending order: `moderator(ctx, mfn, task)` may set `ctx.ttime`, `ctx.pfirb` (UM p.92). ASSUMPTION (Q8): *Task* duration applies while that task is scheduled, then reverts; *Perm* lasts "until end of simulation or next status update" (p.64), interpreted as end of iteration because all state is re-initialized per iteration.

### 4.8 Attribute assignment timing and event ordering
ATA f3: REL | STA | COM (default COM). DESIGN DECISION (Q9) for ordering within an event:
- **Release:** INCM packet choice → MARK(FPC handled at first arrival) → MARK(REL) → ATAS(REL) → STAT(REL) → enter waiting file.
- **Start:** resources seized → ATAS(STA) → MARK(STA) → TTIME evaluated → moderators → validation → STAT(STA) → schedule completion.
- **Completion:** resources freed → ATAS(COM) → MARK(COM) → STAT(COM) → MOD updates → NMO → DMO → TCL → RCL → SWI → REG → sink count → branching.
Rationale: an assignment made at an event must be visible to statistics and time evaluations at that event (e.g. `TIME IA,5` needs ATAS(REL/STA) first).

### 4.9 Resources
Count POP f2; attributes per resource POP f3; initial attributes IRA (≤10 per card; DS/SC/UF); labels LRE. Runtime: idle/busy, current task instance, busy-time accumulator, tasks performed. One task at a time per resource (implied by "busy performing other tasks", [WDS]).

### 4.10 Monitors (MON/MTA/MSW, UM p.79–81; symbolism p.29–31)
`Monitor{id, label, var (SS i>0 | DD −i; 0 = error), thr_var (SS>0 | none 0 | DD<0), cmult=1, cadd=0, direction POS|NEG|BOTH = BOTH, tol=0, signal_tasks ≤10, switch_sets ≤10}`. Threshold function `g(t) = X(t) − (CADD + CMULT·Y(t))`. Positive crossing: g from <0 to ≥0; negative: >0 to ≤0. On a crossing: MSWT switch sets, then MTAS signals (DESIGN DECISION, so signaled tasks see new switch values). Example (p.31): monitor 15 watches SS(3) increasing beyond SS(10)+17.2 with tolerance 0.5; signals task 35; sets IS(1)=3, IS(5)=40.

---

## 5. Legacy Input (Card Format) and Modern Format
### 5.1 Lexical grammar (UM p.32–37)
```
deck         := network ("SIM" network)* "FIN"
network      := record+
record       := card_id "," fields terminator
card_id      := ALNUM+            ; first 3 characters significant
fields       := field ("," field)*   ; ≤ 50 fields per input record
field        := EMPTY | skip? value
skip         := "(" INT ")"       ; jump to field n; skipped fields take defaults
value        := INTEGER | REAL | EFORMAT | ALPHA
terminator   := "*" | end of card whose last non-blank char is not ","
continuation := last non-blank char is "," ⇒ next card continues the record (no ID); may chain
```
Rules: leading and embedded blanks in numeric fields ignored; fields cannot span cards; alphanumerics may start with letter or digit, ≤8 significant characters, extra characters ignored (only the underlined code letters matter); integer→real converted; real→integer truncated; E-format = number + `E` + 1–2 digit signed/unsigned exponent without decimal point; **E-format in an integer field ⇒ warning** (UM p.36). Omitted field (`,,` or blanks then comma), skipped field, or early termination ⇒ default. Example `POP ,4,,5 , (8)MULTIPLE*` ⇒ f2=4, f3 default, f4=5, f5–7 default, f8=M, f9 default (UM p.37).

Deck rules (UM p.37): GEN, SGE (if any), POP, OUT, DIS precede all other cards; VAR follows its PLO, UVA follows its UPL; the last card of a network is SIM (more follow) or FIN; other cards in any order; only needed cards are supplied.

DESIGN DECISIONS: case-insensitive; no 80-column limit; optional comment lines (`C ` / `!`) as an extension disabled by `--strict`. Code-prefix tables (the underlines are lost in OCR): Y/N; I/M (Interchange/Multiple); SO/SI/NS; F/L/B/S (INCM); A/O (AND/OR); M/N (mark); FPC/REL/STA/COM/CLR; FIR/ALL/BET/INT/NUM/NO; A/D and T/P (MOD); I/E/D (REG); P/N/B (MON direction); Q/P/T/B (plot option); M/V/R (scale keys); N/W/F (SGE severity); SA/IA/RA/PA/NO.

### 5.2 Field-by-field card tables
Format `fN type default — description` (A alpha, I integer, R real). Pages are UM printed pages; f1 is always the card ID.

**GEN — General information (p.40):** f2 A — user name (8) · f3 I 1 month · f4 I 1 day · f5 I 2001 year · f6 I 1 project number · f7 I 1 **iterations** · f8 I 1 **sink completions required to complete the network** · f9 I 71268659 **seed** · f10 R 1.0 **scale factor for SC** · f11 A Y print echo check (Y/N).

**SGE — State variable general information (p.40; only if state variables):** f2 I 0 NNEQD (number/largest index of DD equations) · f3 I 0 NNEQS (number of SS equations) · f4 R 0.01·DTMAX DTMIN · f5 R min(DTSAV,1E20) DTMAX · f6 R 1E20 DTSAV (>0 interval between communication points; =0 every accepted update; <0 only at event times) · f7 R 1E-5 AAERR · f8 R 1E-5 RRERR · f9 A W severity when accuracy cannot be kept in updates or threshold searches (None/Warning/Fatal). Criterion: error ≤ AAERR + RRERR·SS(I) for all I.

**POP — Program options (p.41):** f2 I 0 resources (largest number) · f3 I 0 attributes per resource · f4 I 0 information attributes per packet · f5 I 0 system attributes · f6 I 0 moderator functions · f7 A I network-modification mode (Interchange/Multiple) · f8 A I DS-modification mode · f9 I 3 ranking of waiting file (1 low priority first, 2 high first, 3 FIFO, 4 LIFO).

**OUT — Output options (p.42–43):** iteration ranges, begin default 0, end default = begin: f2/f3 detailed iteration output · f4/f5 resource utilization summary · f6/f7 statistics-task summary · f8/f9 initial and final state values · f10/f11 state statistics · f12/f13 state plots/tables · f14 A Y print resource-utilization summary · f15 A Y print statistics-task summary · f16 A N histograms of statistics tasks from iteration 1 · f17 A N histograms from summary report. (ASSUMPTION: iteration 0 = none.)

**DIS — Distribution set (p.45–46):** f2 I set number · f3 A CO type · f4–f7 R 0 parameters (§4.6). One card per set.

**SIM** — end of input for a network when another network follows · **FIN** — end of all input (p.33, p.37).

**UBO — User statistics on observations (p.47):** repeat {f2 I statistic number (UCLCT arg), f3 A label} ≤24.
**UTI — User time-persistent statistics (p.48):** repeat {f2 I statistic number (UTMST/UTMSA arg), f3 A label, f4 R 0 initial value} ≤16.
**UHI — User histograms (p.49):** repeat {f2 I histogram number (UHIST arg), f3 A label, f4 I 25 cells, f5 R 0 upper limit of first cell, f6 R 1 cell width} ≤9.
**UPL — User plot/table (p.51):** f2 I plot number (UPLOT arg) · f3 A "TIME" independent-axis label · f4 I 0 storage (>0 file unit, needed for multiple plots; =0 core UPSET(), only one plot and f2 must be 1) · f5 A P option (Quick/Plot/Table/Both) · f6 R 5 increment of independent variable between points.
**UVA — User plot variables (p.52–53):** f2 I plot number · repeat {f3 I variable number, f4 symbol (default f3), f5 A label, f6 A M lower-scale key (Minimum observed / Value in f8 / Rounded down to multiple of f8), f7 A M upper-scale key (Maximum / Value in f9 / Rounded up to multiple of f9), f8 R 0 lower value, f9 R 0 upper value} ≤6.
**IMO — Initial moderator status (p.54):** repeat {f2 I mfn, f3 A I Inactive/Active} ≤24; unspecified ⇒ inactive.
**IRA — Initial resource attributes (p.55):** f2 I resource · repeat {f3 I attribute, f4 A SC function DS/SC/UF, f5 I 0 parameter} ≤10.
**ISA — Initial system attributes (p.56):** repeat {f2 I attribute, f3 A SC function, f4 I 0 parameter} ≤10.
**LRE — Resource labels (p.57):** repeat {f2 I resource, f3 A label} ≤10.
**LSV — State variable labels (p.58):** repeat {f2 I state variable, f3 A label} ≤10.
**TAS — Task characteristics (p.60–61):** f2 I task · f3 A label · f4 I 0 (source)/1 PR1 · f5 I 9999 PR2 · f6 A SC time function DS/SC/UF/IA/RA/SA · f7 I 0 parameter · f8 I 0 resource when RA · f9 R 0 priority · f10 A NS SOurce/SInk/NS · f11 A N DIFF Yes/No · f12 A L INCM First/Last/Big/Small · f13 I 0 INCM attribute · f14 R 0 completion precedence · f15 A A resource code And/Or · f16–f20 I resources (ascending, ≤5).
**STA — Statistics task (p.62; ≤1 per task):** f2 I task · f3 A N mark M/N · f4 A COM mark time FPC/REL/STA/COM · f5 A NO type FIR/ALL/BET/INT/NUM/NO · f6 A COM collection REL/STA/COM/CLR · f7 I 25 cells · f8 R 0 first-cell upper limit · f9 R 1 width.
**UTC — User task characteristics (p.63; ≤1 per task):** f2 I task · f3–f27 R 0 characteristics 1–25 (field 3 = characteristic 1).
**MOD — Moderator status (p.64; ≤1 per task):** f2 I task · repeat {f3 I mfn, f4 A D Deactivate/Activate, f5 A T Task/Perm} ≤10.
**ATA — Attribute assignment (p.65; ≤1 per task):** f2 I task · f3 A COM REL/STA/COM · repeat {f4 A IA type SA/IA/RA, f5 I 0 resource if RA, f6 I 0 attribute, f7 A SC function DS/SC/UF, f8 I 0 parameter} ≤6.
**DET — Deterministic (p.67):** f2 task · f3 successor, repeated ≤20.
**PRO — Probabilistic (p.68):** f2 task · f3 A NO attribute type SA/IA/RA/NO · f4 I 0 resource if RA · repeat {f5 I successor, f6 R probability (0–1) or attribute number} ≤10; the first pair is the "first branch".
**CFI — Conditional take-first (p.69–70):** f2 task · repeat {f3 I successor, f4 A NO condition code, f5 R 0 value or attribute, f6 I 0 attribute for two-attribute comparisons, f7 A IA-if-attribute-needed-else-NO attribute type SA/IA/RA/NO, f8 I 0 resource if RA} ≤5; a sixth successor is taken unconditionally.
**CAL — Conditional take-all (p.71):** same as CFI.
**NMO — Network modifications (p.72; ≤1 per task):** f2 task · repeat {f3 task replaced, f4 task inserted} ≤10.
**DMO — DS modifications (p.73; ≤1 per task):** f2 task · repeat {f3 set replaced, f4 set inserted} ≤10.
**TCL — Task clearing (p.74; ≤1 per task):** f2 task · repeat {f3 task in progress to halt, f4 I 0 task to signal} ≤10.
**RCL — Resource clearing (p.75; ≤1 per task):** f2 task · repeat {f3 resource (no clearing if not busy), f4 I 0 task to signal} ≤10.
**SWI — Switching (p.76; ≤1 per task):** f2 task · repeat {f3 switch, f4 I 0 value} ≤10.
**REG — Regulation (p.77; ≤1 per task):** f2 task · repeat {f3 I SS index regulated, f4 I 0 SS(+)/DD(−)/none, f5 R 1 CMULT, f6 R 0 CADD, f7 A E Increase/Equal/Decrease} ≤2.
**MON — Monitor (p.79):** f2 I monitor · f3 A label · f4 I variable SS(+)/DD(−), 0 = error · f5 I 0 threshold variable SS(+)/none/DD(−) · f6 R 1 CMULT · f7 R 0 CADD · f8 A B direction Positive/Both/Negative · f9 R 0 tolerance. (Field number of f5 is lost in the OCR; inferred from sequence, Q16.)
**MTA — Monitor task signaling (p.80; ≤1 per monitor):** f2 monitor · f3 task, repeated ≤10.
**MSW — Monitor switching (p.81; ≤1 per monitor):** f2 monitor · repeat {f3 switch, f4 I 0 value} ≤10.
**SST — State variable statistics (p.82):** repeat {f2 I statistic number, f3 I SS(+)/DD(−) index, f4 A label, f5 R 0 initial value} ≤10.
**PLO — State plot/table (p.83):** f2 I plot · f3 A TIME label · f4 I 0 storage (as UPL; core array QPSET) · f5 A P option Quick/Plot/Table/Both · f6 R 5 increment.
**VAR — State plot variables (p.84–85):** f2 I plot · repeat {f3 I variable number, f4 I SS(+)/DD(−) index (0 = error), f5 symbol (default f3), f6 A label, f7 A M lower key, f8 A M upper key, f9 R 0 lower value, f10 R 0 upper value} ≤6.

UM Table 6 "Condensed Data Input Description" (p.87–90) is illegible in the OCR; the detailed descriptions above are authoritative.

### 5.3 Parser design
1. **Lexer** — lines → join continuations → split on commas → strip `*` → `Record(card_id, raw_fields, line_span)`.
2. **Field binder** — data-driven `CardSpec(fields=[FieldSpec(idx, type, default, enum_prefixes)], repeat=(start, end, max))`; handles `(n)` skips and repeats; emits `InputDiagnostic(code, severity, card, field, line, message)`.
3. **Assembler** — splits networks at SIM/FIN; enforces deck-order rules; builds `Model`; merges per-task cards.
4. **Validator** — referenced tasks/DS/resources/attributes/monitors exist and lie within POP counts; ascending resources; uniqueness of per-task cards; probability ranges; CFI `NO` only last; monitor/VAR index ≠ 0; core-storage plot rules; at least one source and reachable sink (warning).
5. **Writer** — Model → canonical deck (round-trip property tests).

### 5.4 Modern YAML/JSON format (worked example)
```yaml
saint: "1.0"
general: {name: FIXSINK, iterations: 200, sinks_to_complete: 1, seed: 71268659, scale: 1.0}
options: {ranking: FIFO, network_mod_mode: interchange, dist_mod_mode: interchange}
counts: {info_attrs: 5, resource_attrs: 15, system_attrs: 2, moderators: 7}
distributions:
  3:  {type: NO, mean: 5.75, min: 2.0, max: 12.0, sd: 1.2}
  10: {type: CO, value: 10}
  21: {type: TR, mode: 6, low: 4, high: 9}
resources:
  1: {label: PLUMBER}
  3: {label: HAMMER}
  5: {label: WRENCH}
tasks:
  1: {label: CALL, role: source, time: {SC: 1}, branching: {type: DET, successors: [5]}}
  5:
    label: FIXSINK
    time: {DS: 3}
    resources: {mode: AND, ids: [1, 3, 5]}
    moderators:
      - {mfn: 1, status: activate, duration: task}
      - {mfn: 7, status: activate, duration: task}
    stat: {type: INT, at: COM, hist: {cells: 25, first: 0, width: 1}}
    branching:
      type: PRO
      branches: [{to: 9, p: 0.9}, {to: 1, p: 0.1}]
  9: {label: DONE, role: sink, time: {SC: 0}, mark: {at: REL}}
state:
  nneqd: 2
  nneqs: 0
  dtmin: 0.001
  dtmax: 0.1
  dtsav: 0.5
  aaerr: 1.0e-5
  rrerr: 1.0e-5
  on_accuracy_fail: warning
monitors:
  15:
    label: SOLCONC
    var: SS3
    threshold: {var: SS10, cmult: 1.0, cadd: 17.2}
    direction: positive
    tol: 0.5
    signal: [35]
    switches: {1: 3, 5: 40}
plugins: {module: examples.fixsink_plugins}
outputs: {resource_util: true, stats_summary: true, hist_summary: true, export: [parquet, csv]}
```
The canonical JSON Schema is generated from the pydantic models (`saint schema > saint.schema.json`).

---

## 6. Simulation Algorithm
### 6.1 Runtime state
`TNOW`; event calendar (binary heap) of task-completion events plus continuous save points and monitor crossings (§7). Per task: outstanding requirement `req`, `released_once`, `diff_seen`, accumulated packets since last release, completions count, in-progress instances (start time, resources, packet, TTIME, PFIRB), last-event times (BET), counts (NUM). Waiting file with ranking rule. Resources; system attributes; switches IS(); SS/DD/SSL vectors; DS alias table; task substitution table; moderator status.

### 6.2 Calendar ordering (DESIGN DECISION, partly UM-based)
Key = `(time, class, −PREC, seq)`; class order at equal times: 0 monitor crossing, 1 task completion (higher PREC first, UM p.16), 2 continuous save point. Remaining ties FIFO by scheduling sequence (ASSUMPTION Q3; the original uses GASP file order).

### 6.3 Run / iteration loop
```
for net in deck.networks:
    bind plugins; user_input(ctx)          # UINPT
    clear_user_stats()                      # CLEAR
    for it in 1..GEN.iterations:
        reset runtime state; init resources (IRA), system attrs (ISA), moderators (IMO)
        if continuous: init_state(ctx)      # INTLC -> SS, IS; evaluate STATE at t=0
        TNOW = 0
        for t in tasks with role SOURCE (or PR1 = 0): release(t, new_packet())
        try_start_waiting()
        loop:
            t_next = calendar.peek_time()   # +inf if empty
            if continuous: advance_continuous(TNOW, t_next)   # may insert a crossing event (§7.3)
            if calendar empty:
                if sinks_done < GEN.sinks_required: raise ExecError(3010)  # nothing in progress
                break
            ev = calendar.pop(); TNOW = ev.time
            handle(ev)                      # completion | crossing | save point
            try_start_waiting()
            if sinks_done >= GEN.sinks_required: break
        finalize iteration (NUM counts, time-persistent integrals, utilization)
        end_iteration(ctx, it)              # ENDIT
    summaries; user_output(ctx)             # UOTPT; reports; exports
```
DESIGN DECISION: in-progress tasks at network completion are abandoned (not completed). Optional safety limits `max_time` / `max_events` raise `SimulationLimitExceeded` (not in SAINT). If there are no events but state variables remain and monitors could still fire, integration continues to `max_time` (ASSUMPTION; error 3010 wording "no other tasks are being performed" suggests SAINT stops — Q3).

### 6.4 Core procedures
```
predecessor_completed(succ, from_task, packet):
    s = resolve_substitution(succ)                      # NMO table
    if s.diff and from_task in s.diff_seen:             # DIFF: repeated predecessor
        offer packet to INCM; return
    s.diff_seen.add(from_task); offer packet to INCM
    if first arrival since last release: MARK(FPC)
    s.req -= 1
    if s.req <= 0: release(s)

signal(task):                                          # clearing / monitor
    s = resolve_substitution(task); s.req -= 1
    if s.req <= 0: release(s)                           # packet: held one, else new empty (ASSUMPTION Q10)

release(s):
    packet = INCM choice (FIRST | LAST | BIG k | SMALL k)
    s.req = s.pr2 ; s.released_once = True ; s.diff_seen.clear()
    MARK(REL); ATAS(REL); STAT(REL)
    waiting_file.insert(s, packet, t_enter=TNOW)        # for TIMEQ, FIFO/LIFO

try_start_waiting():
    for w in waiting_file: if PRIOR hook: w.priority = priority(ctx, w.task)
    order by ranking rule (1 low, 2 high, 3 FIFO, 4 LIFO; ties FIFO)
    for w in order:                                     # whole file scanned (ASSUMPTION Q2)
        if resources_available(w.task):                 # AND all idle | OR any listed idle (lowest no.)
            seize; remove w; start(w)

start(w):
    ATAS(STA); MARK(STA)
    ttime = eval(w.task.time); pfirb = first-branch probability
    for mfn in sorted(active_moderators): moderator(ctx, mfn, w.task)
    if ttime < 0: raise 3007 ; if pfirb < 0: 3008 ; if pfirb > 1: 3009
    STAT(STA)
    calendar.push(Completion(TNOW + ttime, w))

complete(inst):
    free resources (utilization)
    t.completions += 1 ; ATAS(COM); MARK(COM); STAT(COM)
    apply MOD updates; revert Task-duration moderators
    NMO: update substitution table (interchange | multiple)
    DMO: update DS alias table (interchange | multiple)
    TCL: for (x, s): if x in progress: clear(x); if s: signal(s)
    RCL: for (r, s): if r busy: clear(task_on(r)); if s: signal(s)
    SWI: IS[k] = v
    REG: SS[i] = op(SS[i], CADD + CMULT*X); mark continuous discontinuity
    if t.role == SINK: sinks_done += 1
    for succ in select_branches(t, inst.packet, pfirb):
        predecessor_completed(succ, t, copy(inst.packet))   # independent copy per branch (ASSUMPTION)

clear(inst):
    remove its completion event; free its resources; STAT(CLR) at the cleared task
    # cleared task does NOT complete: no ATAS(COM), effects, or branching
```

### 6.5 Iterations, runs, randomness
- Every iteration fully re-initializes network state, resources, attributes, switches, state variables (via INTLC), DS/NMO modifications and moderator status (ASSUMPTION Q8, supported by the per-iteration re-initialization file NRENT, UM p.119).
- SIM separates fully independent networks (UM p.37).
- Seeding per §4.6; same model + seed + version ⇒ identical results; iterations are embarrassingly parallel.

---

## 7. Continuous Component
### 7.1 STATE API
```python
@saint.state
def state(ctx):
    # 1-based views: ctx.SS[i], ctx.DD[i], ctx.SSL[i]; ctx.TNOW, ctx.DTNOW, ctx.IS[k]
    ctx.DD[1] = ctx.SS[3]                                   # differential (Fig.5 PRESSURE)
    ctx.DD[2] = 4.0 * ctx.SS[1]                             # ACCELERATION
    ctx.SS[4] = ctx.SSL[4] + ctx.DTNOW * (1 - ctx.SS[3])    # difference (STRESS)
```
- DESIGN DECISION (Q11): indices 1..NNEQD are differential (SS integrated from DD); others are algebraic/difference and are computed by STATE. STATE is called with `ctx.phase ∈ {"stage", "accept"}`; difference/algebraic SS values are committed only at accepted steps so RK stages do not advance difference equations.
- `init_state` (INTLC) sets initial SS and IS (UM p.92).

### 7.2 Integrator
- Default: embedded **Runge-Kutta-Fehlberg 4(5)**, the nearest standard analogue to SAINT's variable-step Runge-Kutta-England (4th order with embedded error estimate). Alternative backend: `scipy.integrate.solve_ivp` (RK45/DOP853, dense output).
- Accept a step when `|err_i| ≤ AAERR + RRERR·|SS_i|` for all i (UM p.40); DTMIN ≤ h ≤ DTMAX. If accuracy cannot be met at DTMIN, SGE f9 decides: None → continue silently, Warning → continue and log, Fatal → error 3001.
- Steps are cut to land exactly on the next discrete event ([SO]: time "is also incremented in steps between scheduled task completions"). After REGL/SWIT/MSWT changes, integration restarts from the new state (discontinuity).
- DTSAV: >0 record at multiples of DTSAV via dense output; =0 every accepted step; <0 only at event times. With no state variables, time jumps from event to event.

### 7.3 Threshold crossing location
- After each accepted step evaluate g(t) for all monitors. A sign change in the monitored direction triggers root location on the step interval (Illinois/regula falsi on dense output; option `legacy_bisection` re-integrates with step halving) until |g| ≤ tol or the interval < DTMIN. Failure ⇒ SGE f9 severity (3002 if Fatal).
- State is set to the crossing time; the crossing event is processed (MSWT then MTAS) before continuing; simultaneous crossings in monitor-number order (DESIGN DECISION).
- tol = 0 ⇒ use AAERR (DESIGN DECISION). Re-arm only after g leaves the tolerance band (hysteresis, DESIGN DECISION against chattering).

### 7.4 Discrete ↔ continuous interactions
| Direction | Mechanism | Source |
|---|---|---|
| Task → state | REGL equal/increase/decrease | UM p.17, p.77 |
| Task → logic | SWIT sets IS(k), read by STATE/USERF/conditions | UM p.19, p.76; [SO] |
| State → task | Monitor MTAS signals (requirement −1) | UM p.27, p.80 |
| State → logic | MSWT sets IS(k) | UM p.31, p.81 |
| User code | GET/PUT routines, USERF reading SS | UM §IV–V |

---

## 8. User-Written Subprograms and Support Library
### 8.1 Hooks (UM Table 7, p.92–93)
| Legacy | pySAINT hook | Called |
|---|---|---|
| `ENDIT(NITER)` | `end_iteration(ctx, niter)` | end of each iteration; user iteration report, re-init user stats |
| `INTLC` | `init_state(ctx)` | after state-variable input processing; DESIGN DECISION: also each iteration start (Q20) |
| `MODRF(MFN,NNODE)` | `moderator(ctx, mfn, task)` → sets `ctx.ttime` / `ctx.pfirb` | at scheduling if mfn active |
| `PRIOR(ITASK)` | `priority(ctx, task) -> float` | before resources are assigned to released tasks |
| `STATE` | `state(ctx)` | each state update |
| `UERR(KODE)` | `on_error(ctx, code)` | after an execution-error report |
| `UINPT` | `user_input(ctx)` | after all SAINT input is processed |
| `USERF(JJ)` | `userf(ctx, jj) -> float` | every `UF,jj` reference |
| `UOTPT` | `user_output(ctx)` | after all iterations |
Registration: decorators (`@saint.userf(4)`, `@saint.moderator(1)`), a module named in the model, or entry points `pysaint.plugins`. Per-number registration or one dispatcher (mirrors FORTRAN computed GO TO). A plugin may be pure Python or vectorized numpy; sandboxing is out of scope.

### 8.2 Support API (UM Tables 8–13, p.95–102)
| Group | Legacy | Python |
|---|---|---|
| Attributes | GETIA/PUTIA, GETRA/PUTRA, GETSA/PUTSA | `ctx.ia[n]`, `ctx.ra[r][n]`, `ctx.sa[n]` (3401–3410, 3501–3510) |
| Task characteristics | GETTC/PUTTC | `ctx.utch(task)[n]` (3411–3414, 3511–3514) |
| Scheduling | GETPR/PUTPR, QRANK, TIMEQ, TMARK | `ctx.priority[t]`, `ctx.set_ranking(r)` (3515), `ctx.time_in_queue()` (only inside `priority`), `ctx.mark_time()` |
| Random deviates | BETA, DRAND, ERLNG, GAMM, NPOSN, RLOGN, RNORM, TRNGL, UNFRM, WEIBL | `ctx.rng.beta(ds)`, `ctx.rng.drand()`, … (3101–3127) |
| User statistics | CLEAR, CLRHI, CLROB, CLRPT, CLRTP, UCLCT, UHIST, UPLOT, UTMSA, UTMST | `ctx.stats.observe(i, x)`, `.hist(i, x)`, `.plot(i, t, xs)` (≤10 values), `.time_persistent(i, x, t, trapezoid=False)`, `.clear(kind, i=0)`; legacy "i ≤ 0 = report" calls map to report generators (3201–3320) |
| Status dumps | DMPAR, DMPMF, DMPRS, DMPSA, DMPST, DMPSV | `ctx.dump.waiting()`, `.moderators()`, `.resources()`, `.system_attrs()`, `.tasks()`, `.state()` (3601–3604) |
UTMST: value XX holds over the interval up to T (step function). UTMSA: interval value = average of XX and the previous value (trapezoid) (UM p.101).

A thin `pysaint.legacy_api` module also exposes the original FORTRAN-style names (`GETIA(nat) -> value`) for porting old user code.

---

## 9. Outputs
### 9.1 Reports
1. **Echo check** of input with diagnostics (GEN f11).
2. **Detailed iteration trace** (OUT f2–f3): time-ordered event log (release/start/complete/clear/signal/crossing, task, resources, packet attributes).
3. **Statistics-task summary** (OUT f6–f7, f15): per STA task — label, type/event, n, mean, sd, min, max, iterations observed; histograms per OUT f16 (iteration 1) and f17 (summary) showing relative frequency and cumulative distribution ([SO]).
4. **Resource utilization** (OUT f4–f5, f14): per resource fraction busy, busy time, tasks performed, per iteration and across iterations ([SO]: busy/idle for human and equipment resources).
5. **State variables**: initial/final values (f8–f9); time-integrated statistics of SST variables (time-weighted mean, sd, min, max; f10–f11); plots/tables per PLO/VAR (f12–f13) with Min/Value/Rounded scale keys and ≤10 variables per plot ([SO]).
6. **User reports**: UBO/UTI/UHI/UPL outputs and ENDIT/UOTPT hooks.
7. **Error report** (§10.2).

### 9.2 Machine-readable exports (replacing the SPSS export)
`task_obs.parquet` (network, iteration, task, stat_type, event, value), `task_summary.csv`, `resources.parquet` (iteration, resource, busy_time, utilization, n_tasks), `state_trace.parquet` (iteration, t, SS_1…), `events.parquet` (optional trace), `user_stats.parquet`, `run_manifest.json` (model hash, seed, version, timings). CSV equivalents; documented stable columns. Plots as PNG/SVG.

### 9.3 Multi-iteration summary
Mean, sd, min, max and 95% CI across iterations for every statistic; per-iteration value tables (input for Phase-2 analysis).

---

## 10. Error Handling
### 10.1 Input errors (UM §VI, p.103)
The original has a maximum-checking processor that prints *primary* errors after each card image and *secondary* (cross-card) errors after the complete echo, plus a no-checking processor; undefined non-required inputs take defaults. **This volume lists no input error codes (Q12).** pySAINT catalog (DESIGN DECISION):
| Code | Exception | Examples |
|---|---|---|
| I1xx | `CardSyntaxError` | unknown card ID, >50 fields, malformed number, E-format in integer field (warning), split field |
| I2xx | `FieldValueError` | invalid code, out of range, missing required field |
| I3xx | `DeckOrderError` | GEN/SGE/POP/OUT/DIS after other cards, VAR/UVA without PLO/UPL, missing SIM/FIN |
| I4xx | `CrossReferenceError` | undefined task/DS/resource/attribute/monitor, duplicate per-task card, unsorted resources |
| I5xx | `ConsistencyError` | probabilities ∉[0,1] or Σ≠1, CFI `NO` not last, monitor/VAR index 0, core-storage plot ≠ 1, no source, no reachable sink (warning) |
All diagnostics are collected (not fail-fast) into an `InputReport` printed after the echo, mirroring primary/secondary reporting; `--strict` promotes warnings.

### 10.2 Execution errors (UM §VII, Table 14 p.105–118)
`SaintExecutionError(code, tnow, iteration, location, snapshot)`. After raising, the engine writes a status dump (tasks, waiting file, resources, attributes, moderators, state variables — as UM p.104) and calls `on_error(ctx, code)` (UERR). Python tracebacks replace SAINT's deliberate square root of a negative number.
| Code | Exception | Condition (original location) |
|---|---|---|
| 3001 | `IntegrationAccuracyError` | integration accuracy test failed, Fatal severity (UPDATE) |
| 3002 | `ThresholdLocationError` | crossing-location accuracy failed, Fatal (UPDATE) |
| 3003 | `BranchProbabilitySumError` | PRO probabilities do not sum to 1.0 (GASP) |
| 3004 | `NegativeBranchProbabilityError` | a probability < 0 (GASP) |
| 3005 | `CapacityError` | information-packet storage exhausted (GASP) — only with legacy limits |
| 3006 | `CapacityError` | task file storage exhausted (FILEM) — only with legacy limits |
| 3007 | `NegativeTaskTimeError` | TTIME < 0 (SCHAT) |
| 3008 / 3009 | `FirstBranchProbabilityError` | PFIRB < 0 / > 1 (SCHAT) |
| 3010 | `NetworkDeadlockError` | required sinks not done and no task in progress (RMOVE) |
| 3101–3127 | `DistributionArgumentError` | per generator, three codes each (illegal type / set ≤ 0 / set > largest): BETA 3101–3103, ERLNG 3104–3106, GAMM 3107–3109, NPOSN 3110–3112, RLOGN 3113–3115, RNORM 3116–3118, TRNGL 3119–3121, UNFRM 3122–3124, WEIBL 3125–3127 |
| 3201–3208 | `StatisticsIndexError` | CLRHI/CLROB/CLRPT/CLRTP index < 0 or > largest |
| 3209–3212 | `StatisticsUndefinedError` | clearing requested but none defined (CLRHI, CLROB, CLRTP, CLRPT) |
| 3301–3306, 3308–3309, 3311–3312 | `StatisticsIndexError` | UCLCT/UHIST/UTMSA/UTMST/UPLOT index invalid |
| 3307, 3310, 3313 | `NonMonotonicTimeError` | independent variable decreased (UTMSA, UTMST, UPLOT) |
| 3314–3318 | `StatisticsUndefinedError` | collection/reporting requested but none defined (UHIST, UCLCT, UTMSA, UTMST, UPLOT) |
| 3319–3320 | `PlotDefinitionError` | plot has 0 variables (collection / reporting) |
| 3401–3414 | `AccessorIndexError` | GETIA (3401–02), GETPR (3403–04), GETRA (3405–08), GETSA (3409–10), GETTC (3411–14) |
| 3501–3514 | `AccessorIndexError` | PUTIA (3501–02), PUTPR (3503–04), PUTRA (3505–08), PUTSA (3509–10), PUTTC (3511–14) |
| 3515 | `RankingRuleError` | QRANK argument ∉ {1,2,3,4} |
| 3601–3604 | `StatusDumpError` | DMPMF/DMPRS/DMPSA/DMPSV with nothing defined (DESIGN DECISION: warning by default, error in strict) |
`errors.py` holds the full Table 14 as data: `EXEC_ERRORS[code] = ErrorSpec(location, condition, probable_cause)`.

---

## 11. Modernization Extras (Optional Phase, clearly non-SAINT)
1. **Hierarchical sub-models** ([WDS]: "the output derived from simulating a detailed model may be used as the description of a particular task in an overall system model"): `SubModelRef` task time = run the sub-model N iterations → fit a distribution (scipy fitting with AIC over the 11 SAINT families, or empirical/bootstrap) → cache by sub-model hash; or inline expansion of a sub-network with namespaced task ids.
2. **Batch Monte Carlo**: `saint batch` running iterations in parallel (`concurrent.futures`/`joblib`, seed-spawned streams ⇒ reproducible); t-based and batch-means CIs; sequential stopping on CI half-width; factorial / Latin-hypercube parameter sweeps producing tidy DataFrames.
3. **Plain-language authoring (LLM assist)**: "describe a system → SAINT model + report". Pipeline: text → draft YAML constrained to the JSON Schema → validator diagnostics fed back for automatic repair → user reviews a diff and a rendered network → run → narrative report written only from exported numbers. Guardrails: every invented parameter is flagged "assumed" with provenance; no silent defaults.
4. **Web UI / visualization**: network rendered with SAINT symbols (task box with PR1/PR2, description rows, branching-shaped output side; monitor symbol); auto-layout (Graphviz/ELK); YAML round-trip editor; trace animation; results dashboards.
5. **Model documentation card** using the [CAT] entry format (proponent, developer, purpose, general description, input, output, limitations, hardware/software, time requirements, classification, frequency of use, point of contact), auto-generated as `MODEL_CARD.md`.
6. **Extensions** behind an `extensions:` block, disabled in legacy mode: resource pools with capacity >1, extra distributions, calendar time, time-varying arrival processes.

---

## 12. Test and Validation Plan
### 12.1 Unit tests (pytest + hypothesis)
- **Lexer:** continuation, `*`, `(n)` skip, blanks inside numbers, E-format, E-format-in-integer warning, 8-character truncation, code prefixes, 50-field limit.
- **Card specs:** defaults and repeat groups for all 33 types; property test random valid decks → parse → write → parse equality.
- **Distributions:** clamping behavior; parameter mapping (KS tests vs scipy, 1e5 samples); Erlang k; PERT mean/variance; Weibull CDF form; Poisson offset.
- **Release logic:** PR1/PR2, DIFF, INCM (all 4 modes), signals, source auto-release.
- **Queue:** ranking rules 1–4, dynamic PRIOR, QRANK change, TIMEQ.
- **Resources:** AND/OR, utilization accounting, clearing frees resource.
- **Branching:** DET; PRO direct and attribute-based; every Table 4 code; CFI sixth unconditional branch; CAL multiple; PFIRB modification; errors 3003/3004/3008/3009.
- **Effects:** NMO and DMO interchange/multiple; TCL/RCL with/without signal and idle resource; SWI; REG three operations with SS, DD and none.
- **Statistics:** all 16 type × event combinations plus NUM; histogram cell boundaries (ASSUMPTION Q18: cell 1 = (−∞, U1], width w cells, last cell overflow).
- **Continuous:** exponential decay and harmonic oscillator vs analytic solutions within tolerance; difference-equation semantics; DTSAV modes; crossing located within tol; direction filters; DTMIN failure under each severity.
- **Errors:** every execution error code is raised by a dedicated test.

### 12.2 Regression tests from the manual
The User's Manual contains symbolism examples but **no complete sample problem with printed output** (Q13). Regression set:
| ID | Source | Content | Assertion |
|---|---|---|---|
| R1 | UM p.12–14 ATAS examples | `COM: IA,2=DS,3`; `START: RA,7-4=UF,11`; both at REL | parse + correct timing/targets |
| R2 | UM p.14–20 per-code examples (DIFF, DMOD 3→5, INCM FIRST/SMALL 2, LABL, MARK REL/COM, MODF 1,5, PREC 15, PRTY 5, RCLR (1,53),(5), REGL SS(16)=/−= 5·SS(4)+3, RESR AND 1,5,7 / OR 2,3, STAT BET STA (25,20,15), SWIT IS3=152, TCLR 27→39, TIME DS,3 / RA,1-5, UTCH (1,2.75),(5,1.9),(6,2)) | one micro-model each | semantics per §4.3 |
| R3 | **Example 1** (p.21) task 5 FIX SINK: TIME DS,3; RESR AND 1,3,5; MODF 1,7 (text says "1 and 2", Q14) | model + YAML | DS3 time, moderators applied |
| R4 | **Example 2** (p.21) task 27: TIME RA,3-15; ATAS COM IA,5=UF,4; STAT COM INTERVAL; SWIT IS(5)=20; DIFF YES | | INT vs mark; switch; DIFF |
| R5 | **Example 3** (p.21–22) source task 54: TIME UF,18; PRTY 129.23; MARK REL; RCLR (1,15),(5,23); REGL SS(4) += SS(27)+3.25 | | clearing, signals, regulation |
| R6 | **Example 4** (p.22) task 17: PR1 10, PR2 100 (as drawn; OCR, Q16); TIME SC,10; INCM BIG 11; PREC 10; UTCH (1,2.75),(2,157); DMOD DS10→DS21; TCLR clear 35 signal 14 | | |
| R7 | Branch-code examples (p.24, p.26): (0.75), (IA,7), (RA,5-3), (SA,25); (TLV,5.75), (TGA,IA,7), (TVC,35), (TAN,RA,4-1), (ALV,SA,12,2.3), (AGA,IA,3,5) | | truth tables |
| R8 | **Monitor example** (p.31): monitor 15 SOLUTION CONCENTRATION, SS(3) above SS(10)+17.2, tol 0.5, MTAS 35, MSWT IS(1)=3, IS(5)=40; plus MONF example p.30 (SS(1) below 3·SS(7)+4, tol 0.05) | ramp STATE | analytic crossing time ± tol |
| R9 | **Figure 5** (p.29) state variables: PRESSURE DD(1)=SS(3) init 5.2; ACCELERATION DD(2)=4·SS(1) init 0; OIL LEVEL (no equation shown); STRESS SS(4)=SSL(4)+DTNOW·(1−LEVEL) init 7.39; POSITION SS(5)=SSL(5)+POS·DTNOW init 27.5 | | vs analytic/difference reference |
| R10 | POP free-form example (p.37) `POP ,4,,5 , (8)MULTIPLE*` | | field binding |
| R11 | Analytic networks (DESIGN DECISION): M/M/1 via source loop and one resource; PERT series/parallel; two-operator AND/OR crew | | mean / utilization within CI of theory |
| R12 | [CAT]-inspired scenarios (air-defense crew engagement, sealift loading, ASW contact classification) | | smoke + documentation examples |

### 12.3 Statistical validation and golden outputs
- Goldens are **distributions, not single numbers**: (a) same version + seed ⇒ bit-identical summary (determinism test); (b) across versions/RNG changes ⇒ two-sample KS and Welch t-tests (p > 0.001) plus CI overlap against stored reference samples.
- When original SAINT outputs become available (examples in AMRL-TR-77-61, SPSS example AMRL-TR-77-64, application reports), compare means/variances within 99% CIs.
- Continuous goldens use tolerance comparison against analytic or `solve_ivp(rtol=1e-10)` references.

### 12.4 Coverage and CI
≥90% line coverage on `legacy/` and `kernel/`; CI matrix Python 3.11–3.13 × Linux/macOS/Windows; benchmark target ≥200k task events/s in pure Python (numba optional later).

---

## 13. Roadmap, Risks, Open Questions
### 13.1 Phases
| Phase | Weeks | Deliverables | Acceptance criteria |
|---|---|---|---|
| P0 Foundations | 1 | repo, schema skeleton, enums, errors, CI | `saint validate` works on YAML examples |
| P1 Legacy input | 2–3 | lexer, 33 card specs, assembler, validator, writer | R1–R7 and R10 parse; round-trip property tests green |
| P2 Discrete kernel | 4 | release, queue, resources, branching, effects, statistics tasks, RNG | R3–R7, R11 pass; 3003–3010 tested |
| P3 Continuous | 3 | integrator, STATE API, monitors, REGL/SWIT/MSWT | R8–R9 pass; analytic tests within tolerance |
| P4 Plugins, stats, reports | 2–3 | hooks, ctx API, user statistics, reports, exports, plots | 31xx–36xx tested; reports render; exports schema-checked |
| P5 Hardening (v1.0) | 2 | docs, examples, performance, golden suite | full suite green; docs published |
| P6 Optional extras | 4–8 | hierarchy, batch/CI, LLM assist, web UI | per-feature demos and tests |

### 13.2 Risks
| Risk | Impact | Mitigation |
|---|---|---|
| Fine semantics unverifiable (tie-breaks, DIFF reset, clearing, effect order) | results differ from original SAINT | config switches per ambiguity; obtain AMRL-TR-77-63 |
| No original outputs to compare | weak validation | analytic + statistical tests; seek AMRL-TR-77-61/-64 |
| RKE vs RKF numerical differences | crossing times differ within tolerance | document; optional legacy bisection mode |
| OCR misreads of defaults | wrong defaults | cross-check with Instruction Manual; table-driven specs easy to fix |
| Phase-2 scope creep | delays v1.0 | strict phase gate |

### 13.3 Open questions / ambiguities (need AMRL-TR-77-61 Instruction Manual or AMRL-TR-77-63 Program Documentation)
1. **Q1** Exact definition of the "sixteen combinations" of interval and completion statistics; precise meanings of FIR/ALL/BET/INT/NUM.
2. **Q2** Waiting-file scan: can a lower-ranked task start when the top task is blocked? Allocation order when one completion frees several resources.
3. **Q3** Tie-breaking beyond PREC (completions vs crossings vs releases; equal PREC); behavior when no tasks remain but state variables/monitors are active.
4. **Q4** How other branch probabilities change when MODRF alters PFIRB.
5. **Q5** Scope of "task N has been completed" (this iteration, ever, since last release).
6. **Q6** Parameterization of LO, BE, GA and BP in SAINT's RLOGN/BETA/GAMM routines.
7. **Q7** Whether TCLR removes released-but-waiting instances; fate of packets; STAT(CLR) for resource-cleared tasks; signal when nothing was cleared.
8. **Q8** Moderator Task vs Perm semantics; whether Perm, DS and network modifications persist across iterations.
9. **Q9** Order of completion effects (ATAS, MARK, STAT, MOD, NMO, DMO, TCL, RCL, SWI, REG, branching).
10. **Q10** Packet given to a task released only through a signal.
11. **Q11** SS/DD index layout (NNEQD vs NNEQS) and when difference equations are evaluated.
12. **Q12** Input error code catalog and messages (none listed in UM §VI).
13. **Q13** Complete sample problems with printed outputs for golden regression.
14. **Q14** Example 1: symbol shows MODF 1,7 but text says moderator functions "1 and 2".
15. **Q15** Scale-factor field reference (GEN f10 vs "Field 12" / "Field 21" in TAS/ATA/ISA/IRA).
16. **Q16** OCR-garbled defaults and labels: REG f7 default ("E."), MON f5 field number, Example 4 PR1/PR2 values (10/100?), Example 3 REGL operator glyph, MONF crossing-direction glyphs.
17. **Q17** UM Table 6 (condensed input, p.87–90) and Table 16 (array dimensions, p.123) are illegible; needed only for legacy-limit mode (known: INN = 100 tasks default).
18. **Q18** Histogram cell convention (first-cell upper limit, underflow/overflow cells).
19. **Q19** Interchange vs Multiple semantics for NMO/DMO; whether a substituted task inherits requirement counts and packets.
20. **Q20** INTLC call frequency (per network vs per iteration); RKE coefficients and step growth/shrink factors.

---

## Appendix A — Task and Monitor Description Codes
| Code | Information | Card | Default | UM page |
|---|---|---|---|---|
| ATAS | attribute assignments (REL/STA/COM; IA/RA/SA ← DS/SC/UF) | ATA | COM | 12–14, 65 |
| DIFF | different predecessors required | TAS f11 | NO | 14, 61 |
| DMOD | DS modifications at completion | DMO | – | 14–15, 73 |
| INCM | information choice mechanism | TAS f12–13 | LAST | 15, 61 |
| LABL | label (8 chars) | TAS f3 | blank | 15, 60 |
| MARK | marking at FPC/REL/STA/COM | STA f3–4 | none / COM | 15–16, 62 |
| MODF | moderator functions | MOD (+IMO) | inactive | 16, 54, 64 |
| PREC | completion precedence | TAS f14 | 0 | 16–17, 61 |
| PRTY | priority | TAS f9 | 0 | 17, 60 |
| RCLR | resource clearing + signal | RCL | – | 17, 75 |
| REGL | state variable regulation | REG | Equal | 17–18, 77 |
| RESR | resource requirement AND/OR | TAS f15–20 | AND | 18, 61 |
| STAT | statistics collection | STA f5–9 | NO | 18–19, 62 |
| SWIT | switching | SWI | – | 19, 76 |
| TCLR | task clearing + signal | TCL | – | 19–20, 74 |
| TIME | performance time | TAS f6–8 | SC,0 | 20, 60 |
| UTCH | user task characteristics | UTC | 0 | 20, 63 |
| Monitor LABL | monitor label | MON f3 | – | 30, 79 |
| Monitor MONF | threshold function, direction, tolerance | MON f4–9 | BOTH, 0 | 30, 79 |
| Monitor MTAS | tasks signaled | MTA | – | 30, 80 |
| Monitor MSWT | switches set | MSW | – | 30–31, 81 |

## Appendix B — Data Card Types (UM Table 5, p.33–35)
| Group | Card | Purpose | Repeat (max) | Page |
|---|---|---|---|---|
| General | GEN | general information | – | 40 |
| | SGE | state variable general information | – | 40 |
| | POP | program options | – | 41 |
| | OUT | output options | – | 42–43 |
| | DIS | distribution set | – | 45–46 |
| | SIM | end of a network (more follow) | – | 33 |
| | FIN | end of all input | – | 33 |
| User statistics/plots | UBO | statistics on observations | ×24 | 47 |
| | UTI | time-persistent statistics | ×16 | 48 |
| | UHI | histograms | ×9 | 49 |
| | UPL | plot/table characteristics | – | 51 |
| | UVA | plot/table variables | ×6 | 52–53 |
| Initial status & labels | IMO | initial moderator status | ×24 | 54 |
| | IRA | initial resource attributes | ×10 | 55 |
| | ISA | initial system attributes | ×10 | 56 |
| | LRE | resource labels | ×10 | 57 |
| | LSV | state variable labels | ×10 | 58 |
| Task description | TAS | task characteristics | 5 resources | 60–61 |
| | STA | marking & statistics | – | 62 |
| | UTC | user task characteristics | 25 values | 63 |
| | MOD | moderator status updates | ×10 | 64 |
| | ATA | attribute assignments | ×6 | 65 |
| Branching | DET | deterministic | ×20 | 67 |
| | PRO | probabilistic | ×10 | 68 |
| | CFI | conditional take-first | ×5 (+1 unconditional) | 69–70 |
| | CAL | conditional take-all | ×5 (+1) | 71 |
| Completion effects | NMO | network modification | ×10 | 72 |
| | DMO | DS modification | ×10 | 73 |
| | TCL | task clearing | ×10 | 74 |
| | RCL | resource clearing | ×10 | 75 |
| | SWI | switching | ×10 | 76 |
| | REG | regulation | ×2 | 77 |
| Monitors | MON | monitor characteristics | – | 79 |
| | MTA | monitor task signaling | ×10 | 80 |
| | MSW | monitor switching | ×10 | 81 |
| State statistics/plots | SST | state variable statistics | ×10 | 82 |
| | PLO | plot/table characteristics | – | 83 |
| | VAR | plot/table variables | ×6 | 84–85 |

## Appendix C — Example Models
### C.1 Legacy deck: Examples 1 and 3 in a small runnable network
(Values beyond the manual's examples are illustrative.)
```
GEN,QUINN,10,29,2026,1,100,1,71268659,1.,Y*
POP,5,15,5,2,7,I,I,3*
OUT,1,1,1,100,1,100,,,,,,,Y,Y,N,Y*
DIS,3,NO,5.75,2.,12.,1.2*
TAS,54,DISPATCH,0,1,UF,18,,129.23,SO*
STA,54,M,REL*
RCL,54,1,15,5,23*
DET,54,5*
TAS,5,FIXSINK,1,1,DS,3,,0.,NS,N,L,0,0.,A,1,3,5*
MOD,5,1,A,T,7,A,T*
STA,5,N,COM,INT,COM,25,0.,1.*
DET,5,9*
TAS,9,DONE,1,9999,SC,0,,0.,SI*
TAS,15,RECOVER1,1,1,SC,1*
TAS,23,RECOVER5,1,1,SC,1*
FIN*
```
Requires a plugin module with `userf(18)` and `moderator(1)`, `moderator(7)`. Example 3's REGL needs SGE + STATE and is shown in C.2.

### C.2 Continuous fragment: Example 3 regulation and the p.31 monitor
```
SGE,0,30,0.001,0.1,0.5,1.E-5,1.E-5,W*
REG,54,4,27,1.,3.25,I*
MON,15,SOLCONC,3,10,1.,17.2,P,0.5*
MTA,15,35*
MSW,15,1,3,5,40*
SST,1,3,SOLCONC,0.*
PLO,1,TIME,0,B,0.5*
VAR,1,1,3,C,SOLCONC,M,M*
```

### C.3 Python API sketch
```python
import pysaint as ps

m = ps.load_model("deck.dat")            # or "model.yaml"

@m.plugins.userf(18)
def dispatch_time(ctx, jj):
    return ctx.rng.unfrm(3) if ctx.IS[1] else 2.0

@m.plugins.moderator(1)
def speed(ctx, mfn, task):
    ctx.ttime *= 1.0 + 0.002 * ctx.TNOW     # fatigue-style moderator ([SO])

res = ps.Simulation(m, seed=71268659).run(iterations=500)
res.tasks.summary()                     # pandas DataFrame
res.resources.utilization()
res.export("out/", formats=["parquet", "csv"])
```

### C.4 [CAT]-inspired documentation scenario (not from SAINT sources)
*Air-defense crew engagement:* source task TARGET DETECTED (ER inter-arrival loop) → IDENTIFY → EVALUATE → ASSIGN WEAPON, performed by two console operators (RESR OR 1,2); priority by threat attribute via PRIOR; CFI on `TGA,IA,deadline` → LEAKER sink vs ENGAGE sink; continuous fatigue DD(1) = k raising task times through MODRF; a monitor on fatigue signals a CREW REST task (MTAS) whose completion clears the operators (RCLR) and regulates fatigue down (REGL Decrease).
