# Endless-Autofighter: Card/Relic UI flow notes (read-only)

## Frontend
- `frontend/src/lib/components/OverlayHost.svelte`: hosts global overlays; mounts `RewardOverlay.svelte`; wires `rewardOpen` / `setRewardOverlayOpen` and passes staged/choice data (cards/relics) from room state.
- `frontend/src/lib/components/RewardOverlay.svelte`: main reward UX for phases (drops/cards/relics/battle review). Handles highlighting, pending selections, and confirm/cancel flows.
  - Key props: `awaitingCard`, `awaitingRelic`, `cardChoiceOptions`, `relicChoiceOptions`, `stagedCards`, `stagedRelics`, `rewardProgression` (shape comes from backend state).
  - Emits selection intent to parent via events consumed in `frontend/src/routes/+page.svelte` (see `handleRewardSelect` / `handleRewardAdvance`).
  - Has fallback/legacy behavior when reward progression looks invalid (search for "falling back to legacy overlay").
- `frontend/src/routes/+page.svelte`: orchestrates reward actions.
  - `handleRewardSelect(detail)`: dispatches to `chooseCard(id)` / `chooseRelic(id)` or `confirmCard()` / `confirmRelic()` depending on `detail.type` + `detail.intent`.
  - `handleRewardAdvance(detail)`: drives advancing reward phases / room progression.
- `frontend/src/lib/systems/uiApi.js`: client wrapper around `/ui/action`.
  - `chooseCard(cardId)`, `chooseRelic(relicId)`, `confirmCard()`, `confirmRelic()`, `cancelCard()`, `cancelRelic()`.
  - `sendAction(action, params)` posts to `/ui/action`.
- Inventory/catalog surfaces:
  - `frontend/src/lib/components/ShopMenu.svelte`: loads catalogs via `getCardCatalog()` / `getRelicCatalog()` and displays mixed lists.
  - `frontend/src/lib/components/RelicInventory.svelte` (and likely `CardInventory.svelte`): inventory UI.
  - `frontend/src/lib/systems/api.js`: catalog endpoints `getCardCatalog()` -> `/catalog/cards`, `getRelicCatalog()` -> `/catalog/relics`.

## Backend
- `backend/routes/ui/state.py`: `GET /ui` returns complete UI state, including `game_state`, `available_actions`, and reward-related flags/progression.
  - Reward gating signals come from `state.get("awaiting_card")`, `state.get("awaiting_relic")`, `state.get("awaiting_loot")`, and `state.get("reward_progression")`.
- `backend/routes/ui/actions.py`: `POST /ui/action` dispatches UI actions.
  - Reward-specific actions: `choose_card`, `choose_relic`, `confirm_card`, `confirm_relic`, `cancel_card`, `cancel_relic`.
  - Uses services: `services.reward_service.select_card/select_relic/confirm_reward/cancel_reward`.
- Reward progression constants referenced in `backend/routes/ui/actions.py`:
  - `runs.lifecycle.REWARD_STEP_CARDS`, `runs.lifecycle.REWARD_STEP_RELICS`, `runs.lifecycle.REWARD_STEP_DROPS`, `runs.lifecycle.REWARD_STEP_BATTLE_REVIEW`.
- Catalog endpoints (metadata for inventory/builders): search in backend for routes serving `/catalog/cards` and `/catalog/relics` (frontend calls them via `frontend/src/lib/systems/api.js`).
