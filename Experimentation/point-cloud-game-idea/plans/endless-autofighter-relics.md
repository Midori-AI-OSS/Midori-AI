| file path | class name | id | name | stars | summarized_about (or full_about) | numeric_vars |
|---|---|---|---|---|---|---|
| backend/plugins/relics/arcane_flask.py | ArcaneFlask | arcane_flask | Arcane Flask | 2 | Grants shield based on max hp after using ultimate |  |
| backend/plugins/relics/bent_dagger.py | BentDagger | bent_dagger | Bent Dagger | 1 | Boosts atk; killing enemies grants permanent atk boost | effects.atk=0.03 |
| backend/plugins/relics/blood_debt_tithe.py | BloodDebtTithe | blood_debt_tithe | Blood Debt Tithe | 4 | Defeated foes grant rare drop rate; future foes are empowered based on defeats |  |
| backend/plugins/relics/cataclysm_engine.py | CataclysmEngine | cataclysm_engine | Cataclysm Engine | 5 | Trades HP for overwhelming tempo; detonates at battle start to supercharge allies while bleeding HP each turn for escalating mitigation |  |
| backend/plugins/relics/catalyst_vials.py | CatalystVials | catalyst_vials | Catalyst Vials | 2 | Ally DoT ticks heal and boost effect hit rate |  |
| backend/plugins/relics/command_beacon.py | CommandBeacon | command_beacon | Command Beacon | 3 | Fastest ally sacrifices hp at turn start to boost other allies' speed |  |
| backend/plugins/relics/copper_siphon.py | CopperSiphon | copper_siphon | Copper Siphon | 1 | Allies gain lifesteal when dealing damage; excess healing becomes shields |  |
| backend/plugins/relics/echo_bell.py | EchoBell | echo_bell | Echo Bell | 2 | First action each battle has a chance to trigger extra hits |  |
| backend/plugins/relics/echoing_drum.py | EchoingDrum | echoing_drum | Echoing Drum | 3 | First attack each battle has a chance to trigger extra hits and boost atk |  |
| backend/plugins/relics/eclipse_reactor.py | EclipseReactor | eclipse_reactor | Eclipse Reactor | 5 | Drains hp at battle start for massive temporary boost; then continuous drain |  |
| backend/plugins/relics/ember_stone.py | EmberStone | ember_stone | Ember Stone | 2 | Burns attackers when they hit low-HP allies |  |
| backend/plugins/relics/entropy_mirror.py | EntropyMirror | entropy_mirror | Entropy Mirror | 4 | Enemies gain atk but suffer recoil when dealing damage |  |
| backend/plugins/relics/event_horizon.py | EventHorizon | event_horizon | Event Horizon | 5 | Damages foes and drains acting ally each ally turn |  |
| backend/plugins/relics/fallback_essence.py | FallbackEssence | fallback_essence | Essence of 6858 | 6 | Fallback relic granted when card pool exhausted; boosts all core combat stats | effects.atk=0.01, effects.crit_damage=0.01, effects.crit_rate=0.01, effects.defense=0.01, effects.effect_hit_rate=0.01, effects.effect_resistance=0.01, effects.max_hp=0.01 |
| backend/plugins/relics/featherweight_anklet.py | FeatherweightAnklet | featherweight_anklet | Featherweight Anklet | 1 | Boosts spd; first action each battle grants temporary spd burst | effects.spd=0.02 |
| backend/plugins/relics/field_rations.py | FieldRations | field_rations | Field Rations | 1 | Heals and grants ultimate charge to all allies after each battle |  |
| backend/plugins/relics/frost_sigil.py | FrostSigil | frost_sigil | Frost Sigil | 2 | Hits apply chill dealing aftertaste damage based on atk |  |
| backend/plugins/relics/graviton_locket.py | GravitonLocket | graviton_locket | Graviton Locket | 4 | Applies gravity debuff to enemies at battle start; drains party HP while gravity is active |  |
| backend/plugins/relics/greed_engine.py | GreedEngine | greed_engine | Greed Engine | 3 | Lose hp on each action but gain significantly more gold and rare drops |  |
| backend/plugins/relics/guardian_charm.py | GuardianCharm | guardian_charm | Guardian Charm | 2 | Grants def bonus to lowest-HP ally at battle start |  |
| backend/plugins/relics/herbal_charm.py | HerbalCharm | herbal_charm | Herbal Charm | 1 | Heals all allies slightly at the start of each turn |  |
| backend/plugins/relics/killer_instinct.py | KillerInstinct | killer_instinct | Killer Instinct | 2 | Ultimates boost atk; kills boost spd |  |
| backend/plugins/relics/lucky_button.py | LuckyButton | lucky_button | Lucky Button | 1 | Boosts crit rate; missed crits grant a damage boost next turn | effects.crit_rate=0.03 |
| backend/plugins/relics/momentum_gyro.py | MomentumGyro | momentum_gyro | Momentum Gyro | 2 | Rewards focused assault on same target with stacking buffs and enemy debuffs; resets on target switch |  |
| backend/plugins/relics/null_lantern.py | NullLantern | null_lantern | Null Lantern | 4 | Removes shops and rests; battles grant pull tokens but enemies grow stronger with each fight |  |
| backend/plugins/relics/old_coin.py | OldCoin | old_coin | Old Coin | 1 | Increases gold earned; refunds part of first shop purchase |  |
| backend/plugins/relics/omega_core.py | OmegaCore | omega_core | Omega Core | 5 | Massively boosts all stats for entire fight but drains hp after delay | effects.atk=6.0, effects.defense=6.0 |
| backend/plugins/relics/paradox_hourglass.py | ParadoxHourglass | paradox_hourglass | Paradox Hourglass | 5 | May sacrifice allies at battle start to supercharge survivors and shred foe defense | effects.atk=2.0, effects.defense=2.0 |
| backend/plugins/relics/plague_harp.py | PlagueHarp | plague_harp | Plague Harp | 3 | Echoes damage from DoTs to other foes but drains caster HP |  |
| backend/plugins/relics/pocket_manual.py | PocketManual | pocket_manual | Pocket Manual | 1 | Boosts atk; every 10th hit triggers bonus Aftertaste damage | effects.atk=0.03 |
| backend/plugins/relics/rusty_buckle.py | RustyBuckle | rusty_buckle | Rusty Buckle | 1 | Bleeds allies each turn; massive party hp loss triggers aftertaste volleys at enemies |  |
| backend/plugins/relics/safeguard_prism.py | SafeguardPrism | safeguard_prism | Safeguard Prism | 2 | Grants emergency shield and mitigation when allies drop below a health threshold |  |
| backend/plugins/relics/shiny_pebble.py | ShinyPebble | shiny_pebble | Shiny Pebble | 1 | Boosts def; first hit on each ally grants mitigation burst | effects.defense=0.03 |
| backend/plugins/relics/siege_banner.py | SiegeBanner | siege_banner | Siege Banner | 3 | Debuffs enemy def at battle start; killing enemies grants permanent atk and def boosts |  |
| backend/plugins/relics/soul_prism.py | SoulPrism | soul_prism | Soul Prism | 5 | Boosts def and mitigation; revives fallen allies with hp penalty and buffs | effects.defense=0.05, effects.mitigation=0.05 |
| backend/plugins/relics/stellar_compass.py | StellarCompass | stellar_compass | Stellar Compass | 3 | Critical hits grant permanent atk and gold rate increases |  |
| backend/plugins/relics/tattered_flag.py | TatteredFlag | tattered_flag | Tattered Flag | 1 | Boosts max hp; ally deaths grant permanent atk boost to survivors | effects.max_hp=0.03 |
| backend/plugins/relics/threadbare_cloak.py | ThreadbareCloak | threadbare_cloak | Threadbare Cloak | 1 | Grants shield at battle start based on max hp |  |
| backend/plugins/relics/timekeepers_hourglass.py | TimekeepersHourglass | timekeepers_hourglass | Timekeeper's Hourglass | 4 | Each turn, chance to grant ready allies a brief speed boost |  |
| backend/plugins/relics/travelers_charm.py | TravelersCharm | travelers_charm | Traveler's Charm | 4 | When hit, gain temporary defensive bonuses next turn |  |
| backend/plugins/relics/vengeful_pendant.py | VengefulPendant | vengeful_pendant | Vengeful Pendant | 2 | Reflects a portion of damage taken back to attackers |  |
| backend/plugins/relics/wooden_idol.py | WoodenIdol | wooden_idol | Wooden Idol | 1 | Boosts effect res; resisting debuffs grants effect res bonus next turn | effects.effect_resistance=0.03 |