# FloodLens Lifelines Design System

## Product surface

FloodLens Lifelines is a Cape Fear civic technology experience for exploring how floods may interrupt road access to hospitals and fire stations. The interface must preserve uncertainty and must never use green or color alone to imply that a road is safe.

## Visual direction

Playful civic technology: a modern climate-tech mapping product with the clarity of a field instrument and the warmth of a public-facing science exhibit. Data is serious; interaction and small details bring personality. Target roughly 85% polished interface and 15% expressive accents.

## Palette

| Token | Hex | Use |
|---|---|---|
| Background | `#F9F9F7` | Main page surface |
| Ink | `#111111` | Primary text |
| Blue | `#2D5DA1` | Water, route, focus, primary action |
| Red | `#CC0000` | Disruption and risk emphasis |
| Yellow | `#FFF9C4` | Explanatory notes and small highlights |
| Soft blue | `#E8F0FA` | Map and supporting surfaces |
| Soft red | `#F7E1E1` | Risk context |
| Muted | `#737373` | Secondary text |

Risk always includes a text label and context. Use patterns to reinforce higher risk; never encode meaning with color alone.

## Typography

- Display: Playfair Display 700/900 for expressive headlines.
- Body: Lora for readable explanatory copy.
- Interface: Inter for navigation, labels, and controls.
- Data: JetBrains Mono for timestamps, values, and forecast metadata.

The serif gives the product personality; layout, controls, and map remain digital and functional.

## Shape and depth

- Use slightly rounded surfaces (12-24px) for map frames, inputs, and cohesive information panels.
- Use full pills only for compact metadata and filters.
- Keep some structure unboxed with spacing and dividers; do not repeat identical metric cards.
- Use restrained soft shadows only to distinguish floating controls and important panels.
- Use occasional purposeful stickers, pins, underlines, circles, and yellow notes. Do not make components wobbly or decorate every surface.

## Composition

- Responsive single-column-first layout, with asymmetric desktop splits where useful.
- Address lookup is the primary action in the hero.
- The map is the main visual and interactive surface, with compact floating controls and a legible risk key.
- Pair the map with one cohesive route-situation panel.
- Keep the crossing ranking and location watchlist scannable and truthful about illustrative or unavailable data.
- Keep Florence replay discoverable from navigation without implying the current sample map is a live historical simulation.

## Motion and accessibility

- Use quick, purposeful transitions for feedback and state changes.
- Respect `prefers-reduced-motion`.
- Preserve visible keyboard focus, readable contrast, semantic controls, and touch targets of at least 44px.
- Explain unavailable or illustrative data in text; never allow placeholder values to read as real forecasts.
