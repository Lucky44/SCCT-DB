# Slot Fix Changelog
Changes made to correct scunpacked slot data (session ~2026-03-11).

---

## Earlier Individual Fixes

| Ship | Problem | Fix |
|------|---------|-----|
| Drake Corsair | QD slot_size=0 | Set to S2, default Torrent |
| RSI Perseus | All 6 component slots slot_size=0 | Set all to S3 (PP×2, Cooler×2, Shield×2) |
| Crusader C2 Hercules Starlifter | Spurious 3rd shield_generator slot | Deleted shield_generator#3 |
| Anvil F7A Hornet Mk II | Spurious S1 power_plant#2 | Deleted power_plant#2 |
| Kruger L-22 Alpha Wolf | QD slot_size=0 | Set to S1 |
| Esperia Stinger | Only 1 of 3 cooler slots present; PP, QD, shield sizes wrong | Added 2×S1 cooler (Eco-Flow), 1×S1 PP (Fortitude), 1×S2 shield (FullStop); corrected cooler#1→S1, PP#1→S1, QD#1→S2 |

---

## Drake Cutter Variants — Spurious Slot Cleanup
scunpacked creates duplicate/misnumbered slots for all Cutter variants. Each ship should have exactly 1× cooler, 1× PP, 1× QD, 1× shield.

| Ship | Deleted (spurious) | Set slot#1 to |
|------|--------------------|---------------|
| Drake Cutter | cooler#2, PP#2, PP#3, QD#2, SG#2, SG#3 | S1 BlastChill / S1 LightBlossom / S1 FoxFire / S1 HEX |
| Drake Cutter Rambler | cooler#2, PP#2, PP#3, QD#2, SG#2, SG#3 | S1 BlastChill / S1 LightBlossom / S1 FoxFire / S1 HEX |
| Drake Cutter Scout | cooler#2, PP#2, PP#3, QD#2, SG#2, SG#3 | S2 Boreal / S2 ExoGen / S1 FoxFire / S1 HEX |

---

## Bulk Auto-Fix — slot_size=0 Inferred from Default Component
193 slots where scunpacked reported slot_size=0 but had a known default component. Slot size was set to match the component's size. Import script updated to apply this automatically on future re-imports.

| Ship | Slots Fixed | Resulting Sizes |
|------|------------|-----------------|
| Aegis Hammerhead | QD#1 | QD→S3 (Kama) |
| Aegis Hammerhead 2949 BIS Edition | QD#1 | QD→S3 (Kama) |
| Anvil C8 Pisces | PP#1, SG#1 | PP→S1 (Regulus), SG→S1 (Shimmer) |
| Anvil C8R Pisces Rescue | PP#1, SG#1 | PP→S1 (Regulus), SG→S1 (Shimmer) |
| Anvil C8X Pisces Expedition | PP#1, SG#1 | PP→S1 (Regulus), SG→S1 (Shimmer) |
| Anvil Terrapin | SG#1, SG#2 | SG→S2 (5MA 'Chimalli') ×2 |
| Anvil Terrapin Medic | SG#1, SG#2 | SG→S2 (5MA 'Chimalli') ×2 |
| Anvil Terrapin Medic Wikelo Savior Special | SG#1, SG#2 | SG→S2 (BLOC) ×2 |
| Aopoa San'tok.yāi | Cooler#1, #2, PP#1, #2, QD#1, SG#1 | Cooler→S1 (Polar)×2, PP→S1 (DynaFlux)×2, QD→S1 (Beacon), SG→S2 (FullStop) |
| Corsair PYAM Exec | Cooler#1, #2, PP#1, #2, QD#1, SG#1 | Cooler→S2 (Avalanche)×2, PP→S2 (LuxCore)×2, QD→S2 (Huracan), SG→S3 (FR-86) |
| Crusader Intrepid | Cooler#1, PP#1, QD#1, SG#1 | All→S1 (BlastChill / LightBlossom / FoxFire / HEX) |
| Crusader Intrepid Wikelo Work Special | Cooler#1, PP#1, QD#1, SG#1 | All→S1 (Ultra-Flow / WhiteRose / Atlas / Palisade) |
| Drake Corsair | Cooler#1, #2, PP#1, #2, SG#1 | Cooler→S2 (Frost-Star EX)×2, PP→S2 (DayBreak)×2, SG→S3 (5CA 'Akura') |
| Drake Golem | Cooler#1, PP#1, QD#1, SG#1 | All→S1 (Thermax / Fortitude / Goliath / Bulwark) |
| Drake Golem OX | Cooler#1, PP#1, QD#1, SG#1 | All→S1 (Thermax / Fortitude / Goliath / Bulwark) |
| Drake Golem Teach's Special | Cooler#1, PP#1, QD#1, SG#1 | All→S1 (Thermax / Endurance / Atlas / Guardian) |
| Drake Golem Wikelo Work Special | Cooler#1, PP#1, QD#1, SG#1 | All→S1 (Thermax / Fortitude / Goliath / Bulwark) |
| Drake Vulture | Cooler#1, #2, PP#1, #2, QD#1, SG#1, #2 | All→S1 (Thermax×2 / Fortitude×2 / Goliath / Bulwark×2) |
| Drake Vulture Teach's Special | Cooler#1, #2, PP#1, #2, QD#1, SG#1, #2 | All→S1 (same pattern) |
| Gatac Syulen | Cooler#1, PP#1, SG#1, SG#2 | All→S1 (BlastChill / LightBlossom / HEX×2) |
| Kruger L-21 Wolf | PP#1, QD#1, SG#1, #2 | All→S1 (LightBlossom / FoxFire / HEX×2) |
| Kruger L-21 Wolf Wikelo Sneak Special | PP#1, QD#1, SG#1, #2 | S1 (DeltaMax / Zephyr / Veil×2) |
| Kruger L-21 Wolf Wikelo War Special | PP#1, QD#1, SG#1, #2 | S1 (JS-300 / VK-00 / FR-66×2) |
| Kruger L-22 Alpha Wolf | PP#1, SG#1, #2 | PP→S1 (LightBlossom), SG→S1 (HEX)×2 |
| Mirai Fury | Cooler#1, #2, PP#1, SG#1 | All→S1 (Hydrocel×2 / Roughneck / Cloak) |
| Mirai Fury LX | Cooler#1, #2, PP#1, SG#1 | All→S1 (IcePlunge×2 / Roughneck / Falco) |
| Mirai Fury MX | Cooler#1, #2, PP#1, SG#1 | All→S1 (Hydrocel×2 / Roughneck / Cloak) |
| Mirai Guardian | Cooler#1, PP#1, #2, SG#1 | Cooler→S2 (Arctic), PP→S1 (OverDrive)×2, SG→S2 (FullStop) |
| Mirai Guardian MX | Cooler#1, #2, PP#1, SG#1, #2 | Cooler→S1 (Bracer) + S2 (Arctic), PP→S2 (Maelstrom), SG→S2 (FullStop)×2 |
| Mirai Guardian MX Wikelo War Special | Cooler#1, #2, PP#1, SG#1, #2 | Cooler→S1 (Polar) + S2 (Permafrost), PP→S2 (Bolide), SG→S2 (CoverAll)×2 |
| Mirai Guardian QI | Cooler#1, PP#1, #2, SG#1 | Cooler→S2 (Arctic), PP→S1 (Regulus)×2, SG→S2 (FullStop) |
| Mirai Guardian QI Wikelo Special | Cooler#1, PP#1, #2, SG#1 | Cooler→S2 (AbsoluteZero), PP→S1 (LumaCore)×2, SG→S2 (Haltur) |
| Mirai Guardian Wikelo War Special | Cooler#1, PP#1, #2, SG#1 | Cooler→S1 (Glacier), PP→S1 (QuadraCell)×2, SG→S2 (FR-76) |
| RSI Apollo Medivac | Cooler#1, #2, PP#1, #2, QD#1, SG#1, #2, #5, #6 | Cooler→S2×2, PP→S2×2, QD→S2, SG→S2×4 (SG#3, #4, #7, #8 still S0 — no default comp) |
| RSI Apollo Triage | Cooler#1, #2, PP#1, #2, QD#1, SG#1, #2, #5, #6 | Same as Medivac |
| RSI Aurora CL | PP#1 | PP→S1 (Roughneck) |
| RSI Aurora ES | PP#1 | PP→S1 (ZapJet) |
| RSI Aurora LN | PP#1 | PP→S1 (Charger) |
| RSI Aurora LX | PP#1 | PP→S1 (LumaCore) |
| RSI Aurora MR | PP#1 | PP→S1 (Roughneck) |
| RSI Hermes | Cooler#1, #2, PP#1, #2, QD#1, SG#3, #4, #7, #8 | Cooler→S2×2, PP→S2×2, QD→S2, SG→S2×4 (SG#1, #2, #5, #6 still S0 — no default comp) |
| RSI Polaris | Cooler#1, PP#1, SG#1 | Cooler→S4 (Serac), PP→S4 (Stellate), SG→S4 (Glacis) |
| RSI Salvation | Cooler#1, PP#1, QD#1, SG#1, #2 | All→S1 (Eco-Flow / Fortitude / Colossus / Bulwark×2) |
| RSI Zeus Mk II CL | Cooler#1, #2, PP#1, #2, SG#2, #3, #4 | Cooler→S2×2, PP→S2×2, SG→S2×3 (SG#1 still S0 — no default comp) |
| RSI Zeus Mk II ES | Cooler#1, #2, PP#1, #2, SG#1, #2, #3, #4 | All→S2 |
| RSI Zeus Mk II ES Wikelo Work Special | Cooler#1, #2, PP#1, #2, SG#1, #2, #3, #4 | All→S2 |
| Syulen PYAM Exec | Cooler#1, PP#1, SG#1, #2 | All→S1 (SnowBlind / Slipstream / Mirage×2) |

---

## Still Needs Manual Research
These ships have remaining slot_size=0 entries with no default component — correct sizes unknown:

| Ship | Slots Remaining at S0 |
|------|-----------------------|
| RSI Apollo Medivac | SG#3, SG#4, SG#7, SG#8 |
| RSI Apollo Triage | SG#3, SG#4, SG#7, SG#8 |
| RSI Hermes | SG#1, SG#2, SG#5, SG#6 |
| RSI Zeus Mk II CL | SG#1 |
