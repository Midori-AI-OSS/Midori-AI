| kind | file path | class name | id | display name | __init__ params |
|---|---|---|---|---|---|
| dot | backend/plugins/dots/abyssal_corruption.py | AbyssalCorruption | abyssal_corruption | Abyssal Corruption | damage, turns |
| dot | backend/plugins/dots/abyssal_weakness.py | AbyssalWeakness | abyssal_weakness | Abyssal Weakness | damage, turns |
| dot | backend/plugins/dots/blazing_torment.py | BlazingTorment | blazing_torment | Blazing Torment | damage, turns |
| dot | backend/plugins/dots/bleed.py | Bleed | bleed | Bleed | damage, turns |
| dot | backend/plugins/dots/celestial_atrophy.py | CelestialAtrophy | celestial_atrophy | Celestial Atrophy | damage, turns |
| dot | backend/plugins/dots/charged_decay.py | ChargedDecay | charged_decay | Charged Decay | damage, turns |
| dot | backend/plugins/dots/cold_wound.py | ColdWound | cold_wound | Cold Wound | damage, turns |
| dot | backend/plugins/dots/frozen_wound.py | FrozenWound | frozen_wound | Frozen Wound | damage, turns |
| dot | backend/plugins/dots/gale_erosion.py | GaleErosion | gale_erosion | Gale Erosion | damage, turns |
| dot | backend/plugins/dots/impact_echo.py | ImpactEcho | impact_echo | Impact Echo | turns |
| dot | backend/plugins/dots/poison.py | Poison | poison | Poison | damage, turns |
| dot | backend/plugins/dots/twilight_decay.py | TwilightDecay | twilight_decay | Twilight Decay | damage, turns |
| hot | backend/plugins/hots/player_echo.py | PlayerEcho | player_echo |  | player_name, healing, turns |
| hot | backend/plugins/hots/player_heal.py | PlayerHeal | player_heal |  | player_name, healing, turns |
| hot | backend/plugins/hots/radiant_regeneration.py | RadiantRegeneration | light_radiant_regeneration | Radiant Regeneration | source |
| hot | backend/plugins/hots/regeneration.py | Regeneration | regeneration | Regeneration | healing, turns |

## Stacking / ticking rules (shared system)
- DoTs: instances with the same id stack independently; each instance ticks each turn; optional max_stacks may ignore extra applications (no inherent refresh).
- HoTs: instances accumulate with no inherent stack cap; each instance heals each tick; dead targets immediately clear remaining turns.
- Source: backend/autofighter/effects.py (DamageOverTime, HealingOverTime, EffectManager.add_dot/add_hot).
