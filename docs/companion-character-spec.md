# Pawgress Companion Character Specification — v1
### Status: LOCKED (character direction + v1 scope). Frontend implementation IN PROGRESS —
### `CompanionCharacter` + `useCompanionBehavior` built 2026-08-15 (Layers A–D, header wiring).
### See docs/PROGRESS.md for current status; this document's design content is otherwise unchanged.

---

## 1. What This Document Is For

This is the canonical reference for the Pawgress companion character —
what it looks like, how it's allowed to behave, and what it explicitly
does not do. It exists so the frontend companion system (`CompanionCharacter`
+ `useCompanionBehavior`, not yet built) is built *against* a locked
design, rather than the design being improvised alongside the code.

This document is subordinate to the existing foundational documents
(Blueprint, Brand Identity, Domain Model, Functional Requirements) — where
anything here conflicts with one of those, the foundational document wins
and this spec needs revising, not the other way around. It supersedes the
placeholder glyph-based companion system that shipped in Polish Sprint
Slice 1 and the Empty States slice, once real assets and the rebuilt
frontend land.

**Two things are locked as of this document: the character's visual
identity, and v1's exact scope.** Everything marked Post-MVP/Future below
is real, considered, and deliberately not being built yet — not forgotten,
not rejected.

---

## 2. Canonical Character

Reference: Sarah-provided model sheet and expression/pose sheet (2026-08-08),
treated as canonical visual direction. Not to be redesigned or reinterpreted
by whoever builds the frontend — if the production assets ever seem to
drift from this description, the assets are the source of truth for
appearance; this document is the source of truth for *behavior rules*.

- **Breed inspiration:** Ragdoll + Siamese colorpoint.
- **Coloring:** mostly cream/white body, darker seal-brown points on ears,
  face/mask, paws, and tail.
- **Eyes:** blue.
- **Build:** young adult (~1 year), fluffy, chunky/healthy — NOT a tiny
  kitten. Cute + handsome-cute rather than babyish; head-to-body
  proportions read as a sturdy young cat, not an exaggerated big-eyed
  chibi mascot.
- **Gender:** neutral — no accessories or styling implying gender.
- **Primary reference angle:** 3/4 view (most usable for a small,
  peripheral UI element seen at an angle, not straight-on).
- **Personality register (governs expression/pose choices, not visual
  design):** active, curious, affectionate, mischievous, slightly
  dramatic, easily distracted, playful, occasionally hilarious,
  occasionally full gremlin, food-motivated as *flavor only* (see §7),
  supportive without being a coach. A little creature living alongside
  the user — not a mascot performing enthusiasm on demand, not a virtual
  pet with needs the user manages.

**Style note, carried forward explicitly:** the reference art is soft,
painterly, fur-shaded — a "well-illustrated children's book animal," per
Brand Identity §7. Preserving that identity takes priority over forcing a
particular technical rig. Where clean part-separated SVG can hold the
style, use it. Where it can't without flattening the art into something
generic, layered transparent PNG is the correct choice instead. See §6.

---

## 3. V1 Locked Scope

Exactly this, nothing more, for the first real-asset implementation:

- **1 canonical character** (§2)
- **2 poses:** Idle/Sitting, Sleeping
- **6 expressions:** Calm, Curious, Affectionate, Sleepy, Playful, Mischievous
- **Animation-only behaviors** (no additional art): blink, gaze shift,
  head tilt, ear twitch, tail flick, stretch
- **Backend mood stays exactly:** `Neutral` / `Content` / `Attentive` —
  no new enum values, no new persisted fields (Domain Model §7, §4.5 —
  unchanged, not up for revision by this document)
- **Personality and ambient behavior are entirely frontend-driven** — see §5
- **Explicitly excluded from v1:** growth system, feeding mechanic, any
  gamification, any virtual-pet mechanic (needs bar, care requirement,
  neglect state) — see §7 and §8 for why, not just that

---

## 4. Full Expression / Pose / Context Catalog

Documented in full — including everything deferred past v1 — so future
sessions don't have to re-derive this list from chat history, and so
"deferred" reads as a decision, not an omission.

### 4.1 Expressions

| Expression | v1 status | Notes |
|---|---|---|
| Calm / Neutral | **v1 — real art** | Baseline, always available |
| Curious | **v1 — real art** | Maps to `Attentive` |
| Affectionate | **v1 — real art** | Maps to `Content` |
| Sleepy | **v1 — real art** | Ambient-only |
| Playful | **v1 — real art** | Weighted toward `Content` |
| Mischievous | **v1 — real art** | Ambient personality, mood-independent |
| Distracted | Free via animation (Calm eyes + gaze-offset) — no new art needed unless it doesn't read well on real assets | |
| Alert / looking-around | Free via animation first attempt (Curious eyes + head-turn); promote to real art only if the animation-only version doesn't read clearly | |
| Dramatic | Post-MVP | Illustrated on reference sheet, not in v1 |
| Focused | Post-MVP, **build with care if ever built** — risks reading as the cat evaluating the user's work, which FR-6.4 bans outright | |
| Surprised | Future | Not illustrated on any reference sheet yet |
| Hungry | Future | Not illustrated on any reference sheet yet; see §7 on scope limits |

### 4.2 Poses / Behaviors

| Pose/behavior | v1 status | Notes |
|---|---|---|
| Idle / Sitting | **v1 — real art** | The base pose everything else builds from |
| Sleeping / Curl | **v1 — real art** | |
| Stretch | Free via animation (transform-based, already proven at glyph scale in Polish Sprint Slice 1) | |
| Head tilt | Free via animation (rotate head layer) | |
| Tail flick | Free via animation (rotate/translate tail layer) | |
| Ear twitch | Free via animation, IF ears are a separable layer (see §6's style caveat — may fold into head-base) | |
| Blink | Free via animation (eyes layer) | |
| Gaze shift | Free via animation (eyes layer) | |
| Grooming | Post-MVP — needs real art | |
| Play bow / Pawing / Chasing / Hunt mode | Post-MVP — real art, the "playful cluster" | |
| Relaxed lounge | Post-MVP — real art | |
| Belly up (trust) | Post-MVP — real art | |
| Food excitement | Post-MVP — real art; flavor only, see §7 | |
| Little gremlin (+ box prop) | Future — needs a prop asset in addition to the character, extra scene complexity | |

### 4.3 Contextual Reactions

| Context | Behavior | Status |
|---|---|---|
| Capture succeeded | Brief Curious/Alert glance, small, reverts after — never the primary visual focus | v1-compatible once Alert exists (real or animated) |
| Ordinary task completion | **No override.** Whatever's already showing keeps showing (UX Philosophy §5.3) | Unchanged, already settled outside this document |
| Rare earned-delight completion | The one place a bigger reaction belongs (Brand §10) | **Architecturally reserved, not built** — the actual trigger (e.g. "task circled back to multiple times") needs status-history tracking that doesn't exist yet (flagged previously as a real Domain Model gap). This document only reserves the override slot. |
| Empty states (no tasks / no goals) | Re-skin of the glyph-level treatment already shipped (Sleeping pose / Curious-or-Alert expression) | Conceptually shipped, needs real-asset re-skin once available |
| Returning after absence | **Explicitly NOT a trigger.** No unique behavior tied to gap length, ever. | Locked per FR-6.2 / UX Philosophy §5.5 — this was proposed and explicitly rejected earlier in this same design process |
| Within-session inactivity (minutes, not days) | Not a special trigger — just the ambient timer (§5.3) naturally producing more sleepy/distracted moments over time. Framed as ordinary personality, never as "reacting to" the user. | |
| Food-related moments | Ambient flavor only | See §7 — hard boundary, not a future mechanic |

---

## 5. Behavior Model — Four Layers

This is the direct answer to "the cat shouldn't feel like a UI component
translating backend states into expressions." Backend mood is one input
among several, not the sole driver.

### 5.A Backend mood (unchanged)
`Neutral` / `Content` / `Attentive`. Computed live (`CatMoodStateCalculator`,
ADR 0002), never persisted as history, never expanded. This document adds
nothing to this layer and has no authority to change it — Domain Model §7
governs it.

### 5.B Personality / expression state (frontend-only, weighted random)
**Not a lookup table.** Mood shifts probability weights toward certain
expressions but never excludes any of them:

- `Attentive` → weights toward Curious, Alert
- `Content` → weights toward Affectionate, Playful
- `Neutral` → weights toward Sleepy, Distracted, Mischievous

A Playful moment can still surface at low probability while mood is
`Neutral` — that's the specific mechanism that makes this read as an
autonomous creature with its own inclinations, rather than a state machine
wearing a cat costume. Reroll timing follows the same principle already
shipped for companion copy variety: rerolls when mood changes, plus its
own slower independent cadence so the expression doesn't feel frozen for
the entire duration of one mood.

### 5.C Ambient personality timer (mood-independent)
Generalizes the stretch-timer already shipped in Polish Sprint Slice 1.
On a loose, infrequent cadence, layers one of the animation-only behaviors
(blink, tail-flick, head-tilt, ear-twitch, stretch) on top of whatever
pose/expression is currently showing — regardless of mood or personality
state. This is where "the cat does things simply because it's a cat"
lives. Occasional and subtle by design (Sarah's explicit instruction) —
not constant, not attention-seeking.

### 5.D Contextual reactions (event-driven, highest priority, brief)
Only capture-succeeded and (once buildable) rare earned-delight moments.
Takes priority over B and C when active, then hands control back. Everything
in §4.3 marked "not a trigger" is deliberately absent from this layer —
that absence is enforced by this document, not left to implementation
discretion.

### 5.E Growth stage (reserved, not built)
Not part of v1. When built, uses the same trick mood already uses: derived
live from permanent history (e.g. lifetime completions), never a new
stored field — consistent with Domain Model §4.5's current-value-only
design for `CatCompanionState`. Purely additive when it eventually exists:
swaps which art variant renders, touches nothing in layers A–D. The
hard rule carried forward from every prior discussion of this idea:
**growth reflects accumulated progress, never daily performance** — a
missed task or a bad day must never shrink, un-fluff, sadden, or otherwise
visibly punish the character. This is a direct extension of FR-6.2, not a
new rule invented here.

---

## 6. Asset & Layer Requirements for v1

### Minimum art order
1. Idle/Sitting — the one asset the whole system depends on; build and
   validate the pipeline against this first.
2. Sleeping/Curl.
3. Six expression variants (Calm, Curious, Affectionate, Sleepy, Playful,
   Mischievous) — applied to the Idle pose only. Across the reference
   sheet, the head silhouette barely changes between expressions; only
   eyes and mouth do. **Expressions do not need six full alternate heads
   — only swappable eyes + mouth sub-layers on one shared head shape.**
   This is the single biggest cost-saver in the whole asset list.

That's the complete v1 commission: 2 poses × (1 shared head-base + 6
eyes/mouth variants for Idle, none needed for Sleeping since a sleeping
cat's expression barely varies).

### Recommended layer structure
Same named layer groups in every pose, so the frontend can address them
identically regardless of which pose is active:

- `body` — torso, legs, paws, body fluff
- `tail` — separate, so it can flick independently
- `head-base` — skull, fur, ear silhouette; shared across all 6 expressions
- `eyes` — separate (enables blink, gaze-shift, expression swap)
- `mouth` — separate (same reason)
- `ears` — separate **if the chosen format/style tolerates clean
  separation without breaking the fur shading** (see format note below);
  otherwise fold into `head-base` as a v1 simplification and lose only
  the ear-twitch micro-animation, not the whole layer system

### Format: SVG preferred, layered PNG acceptable — style governs the choice, not the other way around
- **Try SVG first.** If the painterly style vectorizes cleanly (clean
  layer boundaries, shading that survives as vector fills/gradients
  without looking flattened), this is the better long-term choice: crisp
  at any size, tiny file size, plain-CSS-animatable, no new runtime
  dependency.
- **Layered, transparent PNG is the explicit, sanctioned fallback**, not
  a compromise to apologize for, if SVG would force flattening the fur
  shading into something generic. Requirements if PNG is used: identical
  canvas size and identical anchor/origin point across every layer and
  every pose, so swapping and positioning layers in CSS behaves
  predictably regardless of which pose is active.
- **The character's visual identity governs this decision, not the
  reverse.** If neither format holds the style well at the fidelity
  needed, that's a real finding to bring back before committing to a
  production pipeline — not something to force through.

---

## 7. Hard Boundaries (carried forward, restated here for this system specifically)

- **No feeding mechanic.** Hunger/food is ambient personality flavor only
  ("the cat is just hungry sometimes, for no reason") — it must never
  imply the user should feed the cat, and must never unlock, reward, or
  gate anything. Direct extension of the unlockables ban (FR-6.3,
  Blueprint §16).
- **No virtual-pet mechanics of any kind** — no needs bar, no care
  requirement, no neglect state, no visible consequence of the user not
  "tending" to the companion. The companion is presence, not a system to
  manage (Blueprint §7).
- **No gamification** — no XP, no unlockables, no unlock-by-streak, no
  points tied to any of this.
- **Return-after-absence produces zero unique behavior**, regardless of
  gap length (§4.3, restated because it's the rule most likely to get
  quietly reintroduced by a well-intentioned future addition).
- **Growth (when eventually built) is accumulation-only** — never
  reversible by missed days, never a punishment signal (§5.E).
- **The cat never delivers instructional or evaluative content** (FR-6.4)
  — this applies to every expression and pose in this document, including
  ones that might tempt it (Focused, Dramatic).

---

## 8. What This Document Does Not Cover

- The actual `CompanionCharacter` component and `useCompanionBehavior`
  hook — not built, intentionally, until real production assets exist.
- Exact probability weights for §5.B's random selection — a tuning
  decision for implementation time, not a design decision to lock now.
- The exact visual re-skin of the already-shipped Empty States glyph
  treatment onto real assets — small follow-up once assets land, not a
  new design decision.
- Anything in the Post-MVP/Future columns of §4 — real, considered,
  intentionally not scoped further until v1 ships and is lived with.

---

*This document is the canonical reference for the Pawgress companion
character going forward. It should be revisited only when: (a) v1 ships
and real usage suggests a locked decision was wrong, (b) Sarah provides
updated or additional reference art, or (c) a Post-MVP/Future item gets
explicitly promoted into a new version's scope — not speculatively, and
not by whoever happens to be implementing at the time.*
