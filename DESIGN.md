# Verdana Health Design System

## Project Context

This design system is the visual layer of the **AI Medical Record Generator**. Clinicians draft, review, and finalise records with help from a locally-hosted Gemma 4 E4B model. Three things follow:

- **Japanese clinical typography.** UI strings are Japanese; line-height, minimum body size (≥16 px), and tabular numerals for lab values are non-negotiable.
- **AI-vs-human distinction.** AI-generated text must always be visually distinguishable from clinician-authored text (see _AI Output Patterns_).
- **PHI safety first.** No patient identifier appears in screenshots, logs, or error states. See `.claude/rules/local-llm-and-phi.md`.

Frontend implementation maps these patterns onto the Atomic Design layout in `frontend/src/components/{atoms,molecules,organisms}/`. See _Atomic Design Mapping_ below.

## Overview

Verdana Health is a calm, trustworthy design system built for digital health platforms, telehealth dashboards, and patient-facing wellness applications. Its foundation of deep navy and soft sage greens evokes clinical precision tempered by warmth. The system prioritizes readability, accessibility, and a sense of reassurance across every touchpoint.

---

## Colors

- **Primary Navy** (#0F172A): Primary actions, strong headers
- **Secondary Slate** (#64748B): Secondary text, borders
- **Tertiary Sage** (#059669): Links, CTAs, highlights
- **Background** (#F8FAFC): Page background
- **Surface Default** (#FFFFFF): Card backgrounds
- **Success** (#22C55E): Confirmed, healthy range
- **Warning** (#EAB308): Pending results, caution
- **Error** (#EF4444): Critical, out of range
- **Info** (#0EA5E9): Informational, new feature

## Typography

- **Headline Font**: Plus Jakarta Sans
- **Body Font**: DM Sans
- **Mono Font**: Fira Code

- **Display**: Plus Jakarta Sans 40px bold, 1.15 line height
- **H1**: Plus Jakarta Sans 32px bold, 1.2 line height
- **H2**: Plus Jakarta Sans 24px semibold, 1.25 line height
- **H3**: Plus Jakarta Sans 20px semibold, 1.3 line height
- **H4**: Plus Jakarta Sans 16px medium, 1.35 line height
- **Body LG**: DM Sans 18px regular, 1.6 line height
- **Body**: DM Sans 16px regular, 1.6 line height
- **Body SM**: DM Sans 14px regular, 1.5 line height
- **Caption**: DM Sans 12px medium, 1.4 line height
- **Code**: Fira Code 14px regular, 1.6 line height

---

## Spacing

Base unit: **8px**

- **xs**: 4px — Inline icon gaps
- **sm**: 8px — Tight component padding
- **md**: 16px — Default padding
- **lg**: 24px — Card padding
- **xl**: 32px — Section gaps
- **2xl**: 48px — Layout sections
- **3xl**: 64px — Page-level spacing

## Border Radius

- **sm** (4px): Badges, small tags
- **DEFAULT** (8px): Buttons, cards, inputs
- **md** (12px): Modals, dropdown panels
- **lg** (16px): Large containers, hero sections
- **full** (9999px): Avatars, status indicators

## Elevation

Gentle, diffused shadows — clinical yet approachable.

- **sm**: 1px offset, 3px blur, #0F172A at 3%. Buttons, chips.
- **DEFAULT**: 2px offset, 6px blur, #0F172A at 5%. Cards, dropdowns.
- **md**: 4px offset, 16px blur, #0F172A at 7%. Elevated cards.
- **lg**: 8px offset, 32px blur, #0F172A at 10%. Modals, panels.

## Components

### Buttons

#### Variants

- **Primary**: #0F172A fill, #FFFFFF text, no border, #020617 hover fill.
- **Secondary**: transparent fill, #0F172A text, 1px #0F172A border, #0F172A0A hover fill.
- **Ghost**: transparent fill, #475569 text, no border, #F1F5F9 hover fill.
- **Destructive**: #EF4444 fill, #FFFFFF text, no border, #DC2626 hover fill.

#### Sizes

Sizes: sm (6px 14px, 14px, 32px), md (10px 22px, 14px, 42px), lg (12px 28px, 16px, 48px).

#### Disabled State

0.4 opacity.

- disabled cursor
- All hover and focus states suppressed

---

### Cards

- **Default**: #FFFFFF fill, 1px #E2E8F0 border, no shadow, 8px radius.
- **Elevated**: #FFFFFF fill, no border, md shadow, 8px radius.
  ** 24px **padding, ** top slot, border-radius 8px 8px 0 0 **image area, ** optional tinted header strip (#0F172A) with white text for category labels **header bar.

---

### Inputs

- **Default**: 1px #E2E8F0 border, #FFFFFF fill, no shadow.
- **Hover**: 1px #0F172A border, #FFFFFF fill, no shadow.
- **Focus**: 2px #0F172A border, #FFFFFF fill, 3px ring #0F172A18 shadow.
- **Error**: 2px #EF4444 border, #FFFFFF fill, 3px ring #EF444418 shadow.
- **Disabled**: 1px #E2E8F0 border, #F1F5F9 fill, no shadow.
  ** 42px | **Padding:** 10px 14px | **Radius:** 8px **height, ** DM Sans 14px/500, color #0F172A, bottom margin 6px **label, ** DM Sans 12px/400, color #475569, top margin 4px **helper text, ** DM Sans 12px/400, color #EF4444, top margin 4px **error text.

---

### Chips

- **Filter**: #F8FAFC fill, #0F172A text, 1px #E2E8F0 border.
- **Filter Active**: #0F172A fill, #FFFFFF text, no border.
- **Status Success**: #22C55E15 fill, #16A34A text, no border.
- **Status Warning**: #EAB30815 fill, #CA8A04 text, no border.
- **Status Error**: #EF444415 fill, #DC2626 text, no border.
  ** 4px 12px | **Radius:** 4px | **Font:** 12px/500, uppercase, tracking 0.5px **padding.

---

### Lists

## ** 48px **row height, ** 8px 16px **padding, ** 1px #F1F5F9 **divider, ** #F8FAFC **hover background, ** #0F172A06 **active background, ** DM Sans 16px/400 for label, 14px/400 #475569 for description **font.

### Checkboxes

## ** 18px x 18px | **Radius:** 4px **size, ** border 1.5px #CBD5E1, background #FFFFFF **unchecked, ** background #0F172A, border none, checkmark #FFFFFF **checked, ** background #0F172A, dash #FFFFFF **indeterminate, ** 40% opacity, disabled cursor **disabled, ** 8px left of label text **label spacing.

### Radio Buttons

## ** 18px x 18px | **Radius:** full (circle) **size, ** border 1.5px #CBD5E1, background #FFFFFF **unchecked, ** border 2px #0F172A, inner dot 8px #0F172A **selected, ** 40% opacity, disabled cursor **disabled, ** 8px left of label text **label spacing.

### Tooltips

## ** #0F172A **background, ** #F8FAFC, DM Sans 12px/400 **text, ** 6px 12px | **Radius:** 8px **padding, ** 6px triangle matching background **arrow, ** 240px **max width, ** 150ms show, 0ms hide **delay.

## Atomic Design Mapping

Use this table as the placement rule when creating or moving components. New components MUST land in the correct layer; cross-layer composition flows in one direction (organisms → molecules → atoms).

| Layer     | Path                                 | Components                                                                                         |
| --------- | ------------------------------------ | -------------------------------------------------------------------------------------------------- |
| Atoms     | `frontend/src/components/atoms/`     | Button, Input, Chip, Checkbox, Radio Button, Tooltip, Badge                                        |
| Molecules | `frontend/src/components/molecules/` | FormField (label + Input + helper/error), LabValueRow, AIIndicatedText, MaskToggle, ConfidencePill |
| Organisms | `frontend/src/components/organisms/` | RecordDraftEditor, RecordList, EncounterPanel, InferenceProgress                                   |

No data-fetching inside any component. Data flows in via props from a hook (`src/hooks/`); hooks call services (`src/services/`); services own `fetch`.

## AI Output Patterns

These patterns make AI-generated text immediately distinguishable from clinician-authored text and offer the three actions clinicians always want.

- **AI-Generated Indicator.** Wrap AI text in `<AIIndicatedText>`: 3 px left border in **Tertiary Sage** (#059669), inline AI icon at the start, text in **Body** size. Background unchanged from the surrounding surface.
- **Streaming Text.** During Gemma streaming, append a 1 px caret cursor (Body size, 70 % opacity) at the live insertion point. Remove the cursor on stream completion. Do NOT show a separate spinner alongside streaming text.
- **Regenerate / Edit / Approve.** Every AI block exposes three actions in this fixed order: Regenerate (Secondary button, refresh icon), Edit (Ghost button, pencil icon, switches the block to inline edit), Approve (Primary button, check icon, commits to the next stage in the record_draft → record_final flow).
- **Confidence / Uncertainty.** When the model emits a confidence score ≤0.5, surface a `<ConfidencePill variant="warning">` adjacent to the AI block; copy: "信頼度低 — 確認してください". Above 0.5, the pill is suppressed.

## Medical-Specific Patterns

- **Lab Values.** Lab tables and inline lab readings render in **Fira Code** for tabular numeral alignment. Numeric columns are right-aligned. Status colours (Success / Warning / Error) follow clinical bands: in-range / borderline / out-of-range.
- **PHI Mask Toggle.** A `<MaskToggle>` molecule sits in the encounter header and toggles patient identifier visibility (name, MRN, DOB, address, phone). Default state on shared screens: masked. Toggling is local-only and is never persisted to storage.
- **Status Semantics (clinical).** Success = within reference range or clinician-confirmed. Warning = pending result or borderline value. Error = out-of-range or system-level failure. Never use Info colour for clinical status — Info is reserved for product-level notices.

## Inference Latency UX

Local Gemma inference is variable. Bind the user-visible feedback to these bands so the UI never appears stalled.

| Elapsed      | Feedback                                                                                                           |
| ------------ | ------------------------------------------------------------------------------------------------------------------ |
| ≤300 ms      | No visible loading state.                                                                                          |
| 300 ms – 1 s | Subtle spinner inside the triggering control (replaces icon).                                                      |
| 1 – 3 s      | Skeleton in the target output area; triggering control shows in-progress state.                                    |
| 3 – 10 s     | Skeleton + textual hint: "ローカルモデル応答待ち".                                                                 |
| > 10 s       | Append a Cancel button (Secondary). On cancel, abort the request and return the UI to idle without partial output. |

Never silently hold the UI past 1 s without a visible signal. Never display partial output below the AI Indicator without the streaming caret.

## Accessibility Bar

Medical use raises the floor. These thresholds are gate-checked by the Evaluator.

- **Standard:** WCAG 2.2 AA minimum on every shipping page.
- **Body text:** ≥16 px. Caption (12 px) is reserved for non-essential metadata; never use it for clinical content.
- **Contrast:** ≥4.5:1 for body text, ≥3:1 for large text and UI components, ≥7:1 (AAA) for any text overlaid on imagery.
- **Focus visible:** Every interactive element shows a 3 px ring focus state. Keyboard tab order matches reading order.
- **Iconography:** Every icon-only control has a text alternative via `aria-label` or visually-hidden text.
- **Motion:** Respect `prefers-reduced-motion`; streaming caret blink and skeleton shimmer become static.

## Do's and Don'ts

1. **Do** use the Navy + White contrast as the primary visual rhythm; Sage green is reserved for interactive elements and positive states only.
2. **Do** lean on generous whitespace and breathing room — health interfaces should never feel cramped.
3. **Do** use softer radius (8px) consistently; rounded corners convey approachability and calm.
4. **Don't** introduce harsh neons or saturated accent colors — Verdana Health is calming and clinical.
5. **Don't** use condensed or decorative fonts; Plus Jakarta Sans and DM Sans are chosen for legibility at all sizes.
6. **Do** use uppercase chip labels with tracking for a polished, medical-grade feel.
7. **Don't** overload dashboards with dense data; use progressive disclosure, collapsible sections, and guided flows.
8. **Do** include clear iconography alongside text labels for accessibility.
9. **Don't** use heavy drop shadows; the diffused elevation system maintains the clean, clinical aesthetic.
10. **Do** ensure lab results and vitals use Fira Code for clear tabular numeral alignment.
11. **Don't** display AI-generated text without the AI Indicator; clinicians must always know which content the model produced.
12. **Don't** show raw PHI in screenshots, logs, error states, or AI prompt previews; mask before render.

## Frontend design

**Design quality**: Does the design feel like a coherent whole rather than a collection of parts? Strong work here means the colors, typography, layout, imagery, and other details combine to create a distinct mood and identity.

**Originality**: Is there evidence of custom decisions, or is this template layouts, library defaults, and AI-generated patterns? A human designer should recognize deliberate creative choices. Unmodified stock components—or telltale signs of AI generation like purple gradients over white cards—fail here.

**Craft**: Technical execution: typography hierarchy, spacing consistency, color harmony, contrast ratios. This is a competence check rather than a creativity check. Most reasonable implementations do fine here by default; failing means broken fundamentals.

**Functionality**: Usability independent of aesthetics. Can users understand what the interface does, find primary actions, and complete tasks without guessing?
