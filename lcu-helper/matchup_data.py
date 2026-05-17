"""
Champion matchup data — laning phase and late game strengths.
Used to provide context for ban/pick recommendations.

Tags:
- lane_strong: Dominates lane phase (strong early trades, kill pressure)
- lane_weak: Struggles in lane (needs to farm safely)
- lane_even: Skill matchup in lane
- late_strong: Scales well, strong in teamfights/split late
- late_weak: Falls off, needs to win early
- poke: Harasses from range
- all_in: Commits to fights, high kill pressure
- sustain: Heals/shields through lane
- roam: Leaves lane to impact map
- safe: Hard to kill, good escape tools
"""

# Champion -> {lane_power: 1-5, late_power: 1-5, style: str, tip: str}
# lane_power: 1=very weak laner, 5=lane bully
# late_power: 1=falls off hard, 5=hyperscales

CHAMPION_DATA: dict[str, dict] = {
    # --- Supports ---
    "Karma": {"lane": 4, "late": 2, "style": "poke/utility", "tip": "Strong poke early, falls off late. Win lane hard."},
    "Lulu": {"lane": 3, "late": 5, "style": "enchanter/peel", "tip": "Safe lane, hyperscales with ADC. Best with Kog/Jinx/Twitch."},
    "Milio": {"lane": 3, "late": 4, "style": "enchanter/peel", "tip": "Safe sustain lane, strong disengage. Weak to hard engage."},
    "Nami": {"lane": 4, "late": 3, "style": "enchanter/poke", "tip": "Strong trades with E+auto. Falls off if behind."},
    "Janna": {"lane": 2, "late": 4, "style": "enchanter/peel", "tip": "Weak lane, godlike peel late. Survive to scale."},
    "Soraka": {"lane": 3, "late": 4, "style": "sustain/heal", "tip": "Poke with Q, sustain through lane. Weak to all-in."},
    "Thresh": {"lane": 4, "late": 3, "style": "engage/pick", "tip": "Hook threat zones enemy. Roam with jungler."},
    "Nautilus": {"lane": 4, "late": 3, "style": "engage/tank", "tip": "All-in at 2/3. Point-click R guarantees kills."},
    "Leona": {"lane": 5, "late": 3, "style": "all-in/engage", "tip": "Strongest all-in at 2/3/6. Weak if behind."},
    "Alistar": {"lane": 3, "late": 4, "style": "engage/peel", "tip": "W+Q combo. Can peel or engage. Roam heavy."},
    "Rell": {"lane": 4, "late": 4, "style": "engage/tank", "tip": "Massive teamfight engage. Weak in short trades."},
    "Rakan": {"lane": 3, "late": 4, "style": "engage/enchanter", "tip": "Flash+W+R engage. Pairs best with Xayah."},
    "Morgana": {"lane": 3, "late": 3, "style": "peel/pick", "tip": "Black Shield counters CC. Q pick wins games."},
    "Lux": {"lane": 4, "late": 3, "style": "poke/burst", "tip": "Poke heavy, one Q catch = kill. Squishy."},
    "Pyke": {"lane": 4, "late": 2, "style": "pick/assassin", "tip": "Roam and snowball. Falls off hard late."},
    "Bard": {"lane": 3, "late": 4, "style": "roam/utility", "tip": "Roam for chimes+ganks. R wins teamfights."},
    "Senna": {"lane": 3, "late": 5, "style": "poke/scaling", "tip": "Infinite scaling range+crit. Weak to dive."},
    "Renata": {"lane": 3, "late": 4, "style": "enchanter/utility", "tip": "W saves carries, R wins teamfights."},
    "Braum": {"lane": 3, "late": 4, "style": "peel/tank", "tip": "Shield blocks projectiles. Passive stun in trades."},
    "TahmKench": {"lane": 4, "late": 2, "style": "tank/peel", "tip": "Devour saves allies. Strong 1v1 early."},
    "Poppy": {"lane": 3, "late": 3, "style": "peel/anti-dash", "tip": "W blocks dashes. Counters engage supports."},
    "Galio": {"lane": 3, "late": 4, "style": "engage/roam", "tip": "R follows jungler ganks. Tanky AP."},
    "Blitzcrank": {"lane": 4, "late": 2, "style": "pick/engage", "tip": "One hook = kill. Zoning threat. Falls off if missing Qs."},
    "Zyra": {"lane": 4, "late": 3, "style": "poke/zone", "tip": "Plant poke dominates lane. R zone control in fights."},
    "Brand": {"lane": 4, "late": 4, "style": "poke/burst", "tip": "Passive burn melts teams. High damage support. Squishy."},
    "Xerath": {"lane": 4, "late": 3, "style": "poke/siege", "tip": "Long range poke. Wins lane from distance. No peel."},
    "Vel'Koz": {"lane": 4, "late": 3, "style": "poke/burst", "tip": "True damage passive. Geometry poke. Immobile."},
    "Yuumi": {"lane": 1, "late": 5, "style": "enchanter/attach", "tip": "Untargetable on carry. Hyperscales. Useless alone."},
    "Sona": {"lane": 2, "late": 5, "style": "enchanter/sustain", "tip": "Weak lane, insane teamfight auras late. R stun."},
    "Swain": {"lane": 3, "late": 4, "style": "sustain/engage", "tip": "E pull sets up kills. R drain tank in fights."},
    "Zilean": {"lane": 3, "late": 5, "style": "utility/scaling", "tip": "R revive wins fights. Double bomb stun. XP passive."},
    "Taric": {"lane": 2, "late": 5, "style": "peel/invulnerability", "tip": "R makes team invulnerable. Weak lane. Insane with divers."},
    "Seraphine": {"lane": 3, "late": 5, "style": "poke/enchanter", "tip": "R through team. Scales with items. Huge teamfights."},

    # --- ADCs ---
    "Jinx": {"lane": 2, "late": 5, "style": "hypercarry", "tip": "Weak lane, resets win teamfights. Farm to 3 items."},
    "KogMaw": {"lane": 2, "late": 5, "style": "hypercarry", "tip": "Needs peel. Melts tanks late. Weak without support."},
    "Vayne": {"lane": 2, "late": 5, "style": "hypercarry/duelist", "tip": "Weak early, 1v9 late. Short range = risky."},
    "Caitlyn": {"lane": 5, "late": 3, "style": "poke/siege", "tip": "650 range bully. Trap control. Falls off mid."},
    "Draven": {"lane": 5, "late": 2, "style": "lane bully", "tip": "Must snowball. Loses if even at 20min."},
    "Lucian": {"lane": 5, "late": 2, "style": "burst/lane bully", "tip": "Short trades with passive. Falls off hard."},
    "Ezreal": {"lane": 3, "late": 3, "style": "safe/poke", "tip": "Safe farm with E. Needs to hit Qs. Never hard carries."},
    "Varus": {"lane": 4, "late": 3, "style": "poke/engage", "tip": "Lethality poke or on-hit. R engage wins fights."},
    "Jhin": {"lane": 4, "late": 3, "style": "utility/poke", "tip": "W+R utility. 4th shot trades. No DPS late."},
    "Ashe": {"lane": 3, "late": 3, "style": "utility/engage", "tip": "R engage from anywhere. Perma slow. No escape."},
    "MissFortune": {"lane": 4, "late": 3, "style": "burst/wombo", "tip": "R wins teamfights. Weak to dive."},
    "Kaisa": {"lane": 3, "late": 4, "style": "burst/dive", "tip": "Evolves spike hard. R repositions in fights."},
    "Xayah": {"lane": 3, "late": 4, "style": "safe/burst", "tip": "R untargetable. Feather root. Safe into dive."},
    "Samira": {"lane": 4, "late": 3, "style": "dive/burst", "tip": "All-in with engage support. R in teamfights."},
    "Tristana": {"lane": 4, "late": 4, "style": "burst/safe", "tip": "All-in at 2/3. W reset. Long range late."},
    "Sivir": {"lane": 3, "late": 4, "style": "utility/waveclear", "tip": "Spellshield. R engage. Waveclear safe."},
    "Aphelios": {"lane": 3, "late": 5, "style": "hypercarry", "tip": "Weapon-dependent. Infernum R wins fights."},
    "Twitch": {"lane": 2, "late": 5, "style": "hypercarry/assassin", "tip": "Weak lane, R melts teams. Surprise flanks."},
    "Zeri": {"lane": 2, "late": 5, "style": "hypercarry/mobile", "tip": "Kites forever. Needs 3+ items."},
    "Smolder": {"lane": 2, "late": 5, "style": "scaling/poke", "tip": "Stack Q. 225 stacks = win condition."},
    "Nilah": {"lane": 4, "late": 4, "style": "dive/melee", "tip": "Short range but W dodges. Needs engage support."},
    "Kalista": {"lane": 4, "late": 3, "style": "kite/utility", "tip": "Hop kiting. R saves support. Falls off."},
    "Corki": {"lane": 3, "late": 4, "style": "poke/burst", "tip": "Package roams. Mixed damage. Poke with R."},
    "Ziggs": {"lane": 3, "late": 3, "style": "poke/siege", "tip": "Tower shred with W. Safe waveclear. No DPS."},

    # --- Mid ---
    "Ahri": {"lane": 3, "late": 3, "style": "safe/pick", "tip": "Charm pick. Triple dash escape. Never hard carries."},
    "Syndra": {"lane": 4, "late": 4, "style": "burst/poke", "tip": "Stun + R oneshots. Strong at all stages."},
    "Orianna": {"lane": 3, "late": 5, "style": "teamfight/utility", "tip": "Ball positioning. R wins teamfights."},
    "Viktor": {"lane": 3, "late": 5, "style": "poke/zone", "tip": "Weak pre-augment. Insane waveclear+damage late."},
    "Zed": {"lane": 4, "late": 2, "style": "assassin/split", "tip": "Snowball or useless. Falls off into tanks."},
    "Fizz": {"lane": 3, "late": 3, "style": "assassin/burst", "tip": "E dodges everything. R = kill. Weak waveclear."},
    "LeBlanc": {"lane": 4, "late": 2, "style": "burst/pick", "tip": "W+Q+R oneshot. Falls off if can't pick."},
    "Yone": {"lane": 3, "late": 5, "style": "dive/scaling", "tip": "Weak early, R engage wins late. Needs 2 items."},
    "Yasuo": {"lane": 3, "late": 4, "style": "dive/scaling", "tip": "Windwall. Needs knockup team. 0/10 powerspike meme."},
    "Akali": {"lane": 3, "late": 3, "style": "assassin/dive", "tip": "Shroud untargetable. Snowball or useless."},
    "Katarina": {"lane": 2, "late": 4, "style": "reset/dive", "tip": "Weak lane, resets in teamfights. Roam heavy."},
    "Zoe": {"lane": 4, "late": 4, "style": "poke/pick", "tip": "Bubble = death. Long range poke. Weak to dive."},
    "AurelionSol": {"lane": 3, "late": 5, "style": "scaling/zone", "tip": "Stacks scale infinitely. Weak early."},
    "Malzahar": {"lane": 3, "late": 3, "style": "push/pick", "tip": "R suppresses. Passive blocks burst. Safe farm."},
    "Veigar": {"lane": 2, "late": 5, "style": "scaling/burst", "tip": "Cage zone. Infinite AP scaling. Weak early."},
    "Galio": {"lane": 3, "late": 3, "style": "roam/tank", "tip": "R follows ganks. Anti-AP. Roam bot."},
    "TwistedFate": {"lane": 2, "late": 3, "style": "roam/utility", "tip": "R ganks win sidelanes. Weak 1v1."},
    "Hwei": {"lane": 3, "late": 4, "style": "poke/utility", "tip": "Long range poke. R zone control."},
    "Neeko": {"lane": 3, "late": 3, "style": "burst/engage", "tip": "Disguise. R flash engage. Burst combo."},
    "Seraphine": {"lane": 3, "late": 5, "style": "poke/teamfight", "tip": "R through team. Scales with items."},
    "Annie": {"lane": 3, "late": 3, "style": "burst/engage", "tip": "Flash+R stun. Simple but effective."},
    "Mel": {"lane": 3, "late": 5, "style": "poke/scaling", "tip": "Long range poke, shield utility. Scales hard as APC bot."},
    "Lissandra": {"lane": 3, "late": 4, "style": "engage/lockdown", "tip": "R self or enemy. W root. Counters assassins and divers."},
    "Aurora": {"lane": 3, "late": 4, "style": "burst/kite", "tip": "R zone traps enemies. High mobility. Burst mage."},
    "Swain": {"lane": 3, "late": 4, "style": "sustain/engage", "tip": "E pull into W. R drain tank. Strong bot lane APC."},
    "Brand": {"lane": 4, "late": 4, "style": "poke/burst", "tip": "Passive burn melts teams. R bounces in teamfights."},
    "Karthus": {"lane": 2, "late": 5, "style": "scaling/global", "tip": "R global damage. Passive lets you cast after death. Farm to scale."},
    "Heimerdinger": {"lane": 4, "late": 3, "style": "zone/push", "tip": "Turrets zone lane. Hard to gank. Falls off in teamfights."},
    "Taliyah": {"lane": 3, "late": 4, "style": "burst/zone", "tip": "W+E combo burst. R wall splits teams. Good roams."},
    "Zaahen": {"lane": 3, "late": 3, "style": "dive/bruiser", "tip": "Newest champion. Dive-oriented bruiser."},
    "Yunara": {"lane": 3, "late": 4, "style": "enchanter/mage", "tip": "Enchanter with damage. Flexible bot lane pick."},
    "Cassiopeia": {"lane": 3, "late": 5, "style": "sustain_dps/zone", "tip": "E spam DPS. R stun if facing. No boots needed."},
    "Azir": {"lane": 2, "late": 5, "style": "sustain_dps/siege", "tip": "Soldier poke. R shuffle engage. Hardest champ. Needs 3 items."},
    "Ryze": {"lane": 3, "late": 4, "style": "sustain_dps/utility", "tip": "EQ combos. R team teleport. Short range mage."},
    "Anivia": {"lane": 3, "late": 5, "style": "zone/peel", "tip": "Wall splits teams. R zone. Egg passive. Insane waveclear."},
    "Sylas": {"lane": 3, "late": 4, "style": "dive/burst", "tip": "Steals ults. Healing with W. Flexible AP bruiser."},
    "Talon": {"lane": 4, "late": 2, "style": "roam/assassin", "tip": "Fastest roams with E wall hop. Must snowball sidelanes."},
    "Naafiri": {"lane": 4, "late": 2, "style": "assassin/dive", "tip": "Pack damage. Simple assassin. Falls off late."},
    "Pantheon": {"lane": 5, "late": 1, "style": "burst/roam", "tip": "Point-click stun. R roams. Falls off a cliff after 20min."},
    "Ekko": {"lane": 3, "late": 4, "style": "assassin/safe", "tip": "R undo mistakes. W stun zone. Good waveclear."},
    "Diana": {"lane": 3, "late": 4, "style": "dive/burst", "tip": "R pull + Zhonya. All-in at 6. Weak pre-6."},
    "Xerath": {"lane": 4, "late": 3, "style": "poke/siege", "tip": "Long range artillery. Immobile. Free ganks."},
    "Vel'Koz": {"lane": 4, "late": 3, "style": "poke/burst", "tip": "True damage combo. Geometry angles. Immobile."},
    "Lux": {"lane": 3, "late": 3, "style": "poke/burst", "tip": "Q catch = kill. Shield utility. Immobile."},

    # --- Jungle ---
    "LeeSin": {"lane": 5, "late": 2, "style": "early/pick", "tip": "Strongest early. Insec. Falls off hard."},
    "Elise": {"lane": 5, "late": 1, "style": "early/dive", "tip": "Tower dive queen. Useless after 25min."},
    "Nidalee": {"lane": 5, "late": 1, "style": "early/poke", "tip": "Spear = kill. Must snowball or lose."},
    "KhaZix": {"lane": 4, "late": 3, "style": "assassin/pick", "tip": "Isolation damage. Evolve R or E."},
    "Evelynn": {"lane": 2, "late": 4, "style": "assassin/scaling", "tip": "Weak pre-6. Perma invis oneshots late."},
    "Viego": {"lane": 3, "late": 4, "style": "skirmish/reset", "tip": "Possess resets. Good in extended fights."},
    "Graves": {"lane": 4, "late": 3, "style": "burst/farm", "tip": "Fast clear. Smokescreen. Falls off."},
    "Kindred": {"lane": 3, "late": 4, "style": "scaling/kite", "tip": "Mark stacks = range. R saves team."},
    "Diana": {"lane": 3, "late": 4, "style": "dive/wombo", "tip": "R pull + Zhonya. Needs flash engage."},
    "JarvanIV": {"lane": 4, "late": 3, "style": "engage/gank", "tip": "E+Q+R locks down. Strong ganks."},
    "Vi": {"lane": 4, "late": 3, "style": "dive/pick", "tip": "R point-click. Deletes carries."},
    "Hecarim": {"lane": 3, "late": 3, "style": "engage/dive", "tip": "R fear engage. Ghost run-down."},
    "Amumu": {"lane": 2, "late": 5, "style": "engage/wombo", "tip": "Double Q. R wins teamfights. Weak early."},
    "Sejuani": {"lane": 2, "late": 4, "style": "engage/tank", "tip": "R engage. Passive tanky. Weak clear."},
    "Zac": {"lane": 3, "late": 4, "style": "engage/tank", "tip": "E long range engage. Blob sustain."},
    "MasterYi": {"lane": 2, "late": 5, "style": "hypercarry/split", "tip": "Q untargetable. Resets. Weak to CC."},
    "Kayn": {"lane": 3, "late": 4, "style": "dive/assassin", "tip": "Form at 10min. Red=drain, Blue=burst."},
    "Nocturne": {"lane": 4, "late": 3, "style": "dive/pick", "tip": "R darkness. Point-click dive. Falls off."},
    "Lillia": {"lane": 3, "late": 4, "style": "poke/kite", "tip": "Speed passive. R sleep wombo."},
    "Wukong": {"lane": 3, "late": 4, "style": "engage/wombo", "tip": "Clone mindgames. Double R knockup."},
    "Rammus": {"lane": 3, "late": 3, "style": "engage/tank", "tip": "OK. Taunt locks carries. Armor stacking vs AD."},
    "Maokai": {"lane": 3, "late": 4, "style": "engage/tank", "tip": "Saplings vision. R root wave. Tanky sustain."},
    "Nunu": {"lane": 3, "late": 3, "style": "engage/objective", "tip": "Snowball ganks. Q smite secures objectives."},
    "Shaco": {"lane": 4, "late": 2, "style": "pick/split", "tip": "Boxes and invis ganks. Clone bait. Falls off."},
    "Belveth": {"lane": 3, "late": 5, "style": "hypercarry/split", "tip": "Infinite scaling attack speed. Void coral form."},
    "Briar": {"lane": 4, "late": 3, "style": "dive/burst", "tip": "W frenzy all-in. R global engage. No control."},
    "Ivern": {"lane": 2, "late": 4, "style": "enchanter/support", "tip": "Jungle enchanter. Daisy tank. Shields carries."},
    "Rengar": {"lane": 4, "late": 3, "style": "assassin/pick", "tip": "Bush leap oneshot. R invis hunt. Snowball reliant."},
    "Fiddlesticks": {"lane": 2, "late": 5, "style": "engage/wombo", "tip": "R from fog = teamfight win. Weak early invades."},
    "Volibear": {"lane": 4, "late": 2, "style": "dive/tank", "tip": "R tower dive. Strong early ganks. Falls off."},
    "Warwick": {"lane": 4, "late": 2, "style": "dive/sustain", "tip": "Blood scent chases. R suppress. Simple and strong early."},
    "Xin Zhao": {"lane": 4, "late": 2, "style": "dive/early", "tip": "Strong duelist early. R knockback zone. Falls off."},
    "Udyr": {"lane": 3, "late": 3, "style": "split/tank", "tip": "Fast clear. Stun ganks. Flexible build."},
    "Skarner": {"lane": 3, "late": 3, "style": "engage/pick", "tip": "R suppresses and drags. Spires control."},
    "Taliyah": {"lane": 3, "late": 3, "style": "burst/roam", "tip": "W+E combo burst. R wall cuts off. Good ganks."},

    # --- Top ---
    "Darius": {"lane": 5, "late": 2, "style": "lane bully/juggernaut", "tip": "5 stack = kill. Kite him and he's useless."},
    "Garen": {"lane": 4, "late": 3, "style": "simple/tank", "tip": "Silence+spin. Passive regen. R execute."},
    "Mordekaiser": {"lane": 4, "late": 3, "style": "1v1/split", "tip": "R isolates. Stat-check. QSS counters."},
    "Fiora": {"lane": 4, "late": 5, "style": "split/duelist", "tip": "Vital procs. W parry. Unbeatable split late."},
    "Camille": {"lane": 3, "late": 4, "style": "dive/split", "tip": "R locks target. True damage Q2. Flexible."},
    "Jax": {"lane": 3, "late": 5, "style": "split/scaling", "tip": "E dodges autos. Scales into 1v9 split."},
    "Irelia": {"lane": 4, "late": 3, "style": "dive/sustain", "tip": "5 stack passive = all-in. Weak if behind."},
    "Riven": {"lane": 4, "late": 3, "style": "burst/combo", "tip": "Animation cancel combos. Snowball or useless."},
    "Aatrox": {"lane": 4, "late": 3, "style": "drain/dive", "tip": "Sweetspot Qs. R healing. Falls off to armor."},
    "Ornn": {"lane": 3, "late": 5, "style": "tank/teamfight", "tip": "Upgrades items. R engage. Brittle proc."},
    "Malphite": {"lane": 2, "late": 4, "style": "tank/engage", "tip": "R flash engage. Armor stacks vs AD."},
    "Sion": {"lane": 3, "late": 4, "style": "tank/split", "tip": "Infinite HP scaling. R engage or split."},
    "Kennen": {"lane": 4, "late": 4, "style": "poke/engage", "tip": "R flash stun. Ranged bully top."},
    "Gnar": {"lane": 4, "late": 4, "style": "poke/engage", "tip": "Mini poke, Mega engage. Manage rage bar."},
    "Gangplank": {"lane": 2, "late": 5, "style": "scaling/global", "tip": "Barrel combos. R global. Weak early."},
    "Renekton": {"lane": 5, "late": 1, "style": "lane bully/dive", "tip": "Strongest early. Falls off a cliff."},
    "Jayce": {"lane": 5, "late": 2, "style": "poke/bully", "tip": "Ranged poke. Gate+Q chunks. Falls off."},
    "Shen": {"lane": 3, "late": 4, "style": "utility/split", "tip": "R saves teammates. Taunt engage."},
    "Quinn": {"lane": 5, "late": 2, "style": "roam/bully", "tip": "Ranged top bully. R roams. Falls off."},
    "KSante": {"lane": 3, "late": 4, "style": "tank/dive", "tip": "R goes damage mode. Flexible tank."},
    "Volibear": {"lane": 4, "late": 2, "style": "dive/tank", "tip": "R tower dive. Strong early. Falls off."},
    "Nasus": {"lane": 1, "late": 5, "style": "scaling/split", "tip": "Free lane = win. Stack Q. Wither cripples."},
    "Tryndamere": {"lane": 3, "late": 4, "style": "split/melee carry", "tip": "R undying 5s. Split push. Weak teamfight."},
    "Ambessa": {"lane": 4, "late": 3, "style": "dive/burst", "tip": "Dash combos. Strong skirmish. Falls off."},
    "Rumble": {"lane": 4, "late": 4, "style": "zone/teamfight", "tip": "R equalizer wins fights. Heat management."},
    "Teemo": {"lane": 4, "late": 2, "style": "poke/split", "tip": "Blind counters AA champs. Shrooms map control. Falls off."},
    "Yorick": {"lane": 3, "late": 4, "style": "split/siege", "tip": "Maiden split pushes. Wall traps. Ignored = loses towers."},
    "Illaoi": {"lane": 4, "late": 3, "style": "zone/juggernaut", "tip": "R in teamfights heals insane. Don't fight in tentacles."},
    "Urgot": {"lane": 4, "late": 3, "style": "sustain_dps/tank", "tip": "Shotgun knees. R execute. Tanky ranged."},
    "Cho'Gath": {"lane": 3, "late": 4, "style": "tank/scaling", "tip": "R stacks infinite HP. Silence + knockup. Immobile."},
    "Dr.Mundo": {"lane": 3, "late": 4, "style": "tank/sustain", "tip": "Passive blocks CC. R full heal. Unkillable late."},
    "Singed": {"lane": 2, "late": 3, "style": "proxy/split", "tip": "Proxy farms behind tower. Fling + poison. Unique playstyle."},
    "Gragas": {"lane": 3, "late": 3, "style": "burst/engage", "tip": "E+Flash engage. R displacement. Flexible AP/tank."},
    "Kayle": {"lane": 1, "late": 5, "style": "hypercarry/scaling", "tip": "Useless pre-6. Ranged at 6. God mode at 16."},
    "Pantheon": {"lane": 5, "late": 1, "style": "burst/roam", "tip": "Point-click stun. R roams. Falls off hard."},
    "Wukong": {"lane": 3, "late": 4, "style": "engage/wombo", "tip": "Clone mindgames. Double R knockup."},
}


def get_matchup_context(champion: str) -> dict:
    """Get laning and late game context for a champion."""
    data = CHAMPION_DATA.get(champion, {})
    if not data:
        return {"lane": "?", "late": "?", "style": "unknown", "tip": ""}

    lane_labels = {1: "Very Weak", 2: "Weak", 3: "Even", 4: "Strong", 5: "Dominant"}
    late_labels = {1: "Falls Off", 2: "Weak Late", 3: "Average", 4: "Strong Late", 5: "Hyperscales"}

    return {
        "lane": lane_labels.get(data.get("lane", 3), "?"),
        "late": late_labels.get(data.get("late", 3), "?"),
        "style": data.get("style", ""),
        "tip": data.get("tip", ""),
        "lane_score": data.get("lane", 3),
        "late_score": data.get("late", 3),
    }


# ---------------------------------------------------------------------------
# Matchup counters — who beats who in lane
# Format: {champion: {counter: score}}
# Positive score = good matchup FOR the champion (they beat the counter)
# Negative score = bad matchup (they lose to the counter)
# Scale: -3 (hard countered) to +3 (hard counters)
# ---------------------------------------------------------------------------

MATCHUPS: dict[str, dict[str, int]] = {
    # --- Supports ---
    "Karma": {
        "Nautilus": -2, "Leona": -2, "Alistar": -1, "Thresh": -1,
        "Sona": 2, "Soraka": 1, "Yuumi": 2, "Janna": 1,
    },
    "Lulu": {
        "Zyra": -2, "Brand": -2, "Vel'Koz": -2, "Xerath": -1,
        "Leona": 1, "Nautilus": 1, "Alistar": 1,  # polymorph stops engage
    },
    "Milio": {
        "Nautilus": -2, "Leona": -2, "Blitzcrank": -2,
        "Thresh": -1, "Rell": -1,
        "Janna": 1, "Soraka": 1,
    },
    "Nami": {
        "Leona": -2, "Nautilus": -1, "Alistar": -1,
        "Soraka": 1, "Sona": 2, "Yuumi": 2,
    },
    "Thresh": {
        "Morgana": -3, "Sivir": -1,  # black shield blocks hook
        "Sona": 2, "Soraka": 2, "Janna": 1,
    },
    "Nautilus": {
        "Morgana": -3, "Braum": -1,
        "Sona": 2, "Soraka": 2, "Karma": 2, "Nami": 1,
    },
    "Leona": {
        "Morgana": -3, "Janna": -2, "Alistar": -1,
        "Sona": 3, "Soraka": 2, "Nami": 2, "Karma": 2,
    },
    "Morgana": {
        "Zyra": -1, "Brand": -1, "Vel'Koz": -1,
        "Thresh": 3, "Nautilus": 3, "Leona": 3, "Blitzcrank": 3,
    },
    "Rell": {
        "Janna": -2, "Morgana": -2,
        "Sona": 2, "Soraka": 2, "Lux": 1,
    },
    "Bard": {
        "Leona": -1, "Nautilus": -1,
        "Soraka": 1, "Sona": 1,
    },
    "Senna": {
        "Nautilus": -2, "Leona": -2, "Blitzcrank": -2,
        "Soraka": 1, "Janna": 1,
    },
    "Renata": {
        "Leona": -1, "Nautilus": -1,
        "Sona": 1, "Soraka": 1,
    },
    "Janna": {
        "Zyra": -1, "Brand": -1,
        "Nautilus": 2, "Leona": 2, "Alistar": 1,  # tornado/R disengage counters engage
        "Caitlyn": 1,  # shield + disengage keeps ADC safe vs poke
    },
    "Pyke": {
        "Morgana": -3, "Alistar": -2, "Leona": -1,
        "Sona": 2, "Soraka": 2, "Nami": 1,
    },
    # --- Support vs Support (bot lane matchups) ---
    "Alistar": {
        "Morgana": -2, "Janna": -1,  # black shield/disengage stops combo
        "Caitlyn": -2, "Lux": -1,  # poked out before can engage
        "Sona": 2, "Soraka": 2, "Nami": 1,
        "Jinx": 1, "KogMaw": 1,  # immobile ADCs easy to combo
    },
    "Lulu": {
        "Zyra": -2, "Brand": -2, "Vel'Koz": -2,  # outpoked
        "Leona": 1, "Nautilus": 1, "Alistar": 1,  # polymorph stops engage
        "Draven": -1,  # can't match his lane pressure
    },
    "Soraka": {
        "Nautilus": -2, "Leona": -2, "Blitzcrank": -2,  # all-in kills her
        "Caitlyn": -1,  # poke through her heal
        "Lux": 1,  # sustains through poke
        "Jhin": 1,  # heals through his poke
    },
    "Braum": {
        "Zyra": -2, "Brand": -2, "Vel'Koz": -1,  # poke behind shield
        "Morgana": -1,  # black shield blocks passive
        "Draven": 1, "Lucian": 1,  # passive procs with fast-attacking ADCs
        "Jinx": -1,  # can't reach her in lane
    },
    "Lux": {
        "Nautilus": -2, "Leona": -2, "Blitzcrank": -2,  # hook/engage = dead
        "Thresh": -1,
        "Sona": 2, "Soraka": 1, "Janna": 1,  # outpokes enchanters
        "Jinx": 1, "KogMaw": 1,  # easy to hit immobile ADCs
    },
    "Xerath": {
        "Nautilus": -2, "Leona": -2, "Blitzcrank": -2,
        "Thresh": -1,
        "Sona": 2, "Soraka": 1,
        "Caitlyn": 1,  # outranges even Cait with poke
    },
    "Vel'Koz": {
        "Nautilus": -2, "Leona": -2, "Blitzcrank": -2,
        "Lulu": 2, "Janna": 1, "Soraka": 1,
    },
    "Blitzcrank": {
        "Morgana": -3, "Sivir": -2,  # black shield/spellshield blocks hook
        "Ezreal": -1,  # E dodges hook
        "Sona": 3, "Soraka": 2, "Lux": 2, "Xerath": 2,  # squishy = dead on hook
        "Jinx": 2, "KogMaw": 2, "Aphelios": 1,
    },

    # --- ADC vs Support interactions ---
    "Caitlyn": {
        "Vayne": -1, "Samira": -1,
        "Veigar": -2, "Ziggs": -2, "Yasuo": -2, "Sivir": -1,  # countered by these
        "Nautilus": 1, "Leona": 1,
        "Sona": 2, "Soraka": 1,
        "Kalista": 2, "Aphelios": 2, "KogMaw": 2, "Jinx": 2, "Twitch": 2,  # Cait counters these
    },
    "Draven": {
        "Caitlyn": -1, "Ezreal": -1,
        "Janna": -1, "Lulu": -1,  # peel/polymorph shuts down his aggression
        "Nautilus": 1, "Leona": 1,  # loves engage supports on his team AND enemy (all-in)
        "Jinx": 3, "KogMaw": 3, "Vayne": 2, "Twitch": 2,
    },
    "Ezreal": {
        "Draven": 1, "Caitlyn": -1,
        "Nautilus": 1, "Leona": 1, "Blitzcrank": 1,  # E escape makes hooks less punishing
        "Sivir": -1,
    },
    "Sivir": {
        "Draven": -1,
        "Nautilus": 2, "Leona": 1, "Blitzcrank": 2, "Thresh": 1,  # spellshield blocks everything
        "Lux": 1,  # spellshield blocks Q
    },

    # --- ADCs ---
    "Jinx": {
        "Draven": -3, "Lucian": -2, "Caitlyn": -2, "Tristana": -1,
        "Nautilus": -2, "Leona": -2,
        "Swain": -2, "Veigar": -2, "Twitch": -2, "Nilah": -2,  # hard countered
        "Lux": -1,
        "Kaisa": 2, "Kalista": 2, "Varus": 1, "Zeri": 1,  # Jinx counters these
        "Ezreal": 1, "KogMaw": 1,
    },
    "KogMaw": {
        "Draven": -3, "Lucian": -2, "Samira": -2, "Tristana": -2,
        "Nautilus": -2, "Leona": -2, "Blitzcrank": -2,  # immobile = free target
        "Ezreal": 1, "Jinx": 0,
    },
    "Varus": {
        "Samira": -2, "Lucian": -1,
        "Nautilus": -1, "Leona": -1,
        "MissFortune": -2, "Jinx": -1,  # outscaled/outpoked
        "Kaisa": 2, "KogMaw": 1, "Aphelios": 1,  # Varus counters these
    },
    "Kaisa": {
        "Caitlyn": -2, "Draven": -1,
        "MissFortune": -2, "Jinx": -2, "Xayah": -2, "Varus": -2, "Sivir": -1, "Ashe": -1,  # countered by these
        "Nautilus": 0,
        "Ezreal": 1, "Smolder": 1, "Vayne": 1,  # Kai'Sa counters these
    },
    "Vayne": {
        "Caitlyn": -2, "Draven": -2, "Lucian": -1,
        "Nautilus": -2, "Leona": -2,  # short range + no escape pre-6 = free kills
        "Lux": -1,  # easy to poke/root
        "KogMaw": 1, "Jinx": 1,
    },
    "Aphelios": {
        "Draven": -2, "Lucian": -2, "Caitlyn": -1,
        "Nautilus": -2, "Leona": -2, "Blitzcrank": -2,  # immobile, easy target
        "Ezreal": 1, "Jinx": 0,
    },
    "Samira": {
        "Caitlyn": -1, "Ashe": -1,
        "Nautilus": 1, "Leona": 1,  # W blocks CC, thrives in all-in
        "Lux": 1,  # W blocks Q, can dash in
        "Jinx": 2, "KogMaw": 2, "Varus": 2,
    },
    "Lucian": {
        "Vayne": -1,
        "Nautilus": 1, "Leona": 0,  # mobile, can dash out
        "Lux": 1,  # dashes dodge skillshots
        "KogMaw": 2, "Jinx": 2, "Aphelios": 2,
    },
    "Tristana": {
        "Caitlyn": -1,
        "Nautilus": 1, "Leona": 0,  # W jump escapes, can all-in back
        "KogMaw": 2, "Jinx": 1, "Vayne": 1,
    },
    "Xayah": {
        "Caitlyn": -1, "Draven": -1,
        "Nautilus": 1, "Leona": 1,  # R dodges engage, feather root punishes
        "Lux": 1,  # R dodges Q
    },
    "Ashe": {
        "Draven": -2, "Lucian": -1, "Samira": -1,
        "Nautilus": -1, "Leona": -1,  # immobile, easy engage target
        "Jinx": 1, "KogMaw": 1,
    },
    "MissFortune": {
        "Draven": -1, "Lucian": -1,
        "Nautilus": -1, "Leona": -1,  # immobile during R
        "Nilah": -2, "KogMaw": -2, "Swain": -2, "Yasuo": -2,  # hard countered by these
        "Kaisa": 2, "Kalista": 2, "Varus": 2, "Aphelios": 2, "Samira": 1,  # MF counters these
        "Caitlyn": 1,  # Q poke trades well
        "Jinx": 1, "KogMaw": 1,
    },
    "Smolder": {
        "Draven": -2, "Lucian": -2, "Caitlyn": -1,
        "Nautilus": -1, "Leona": -1,
        "MissFortune": -1, "Jinx": -1,  # punished early
        "Kaisa": -1,  # Kai'Sa counters Smolder
        "Ezreal": 1,
    },

    # --- Mid ---
    "Zed": {
        "Malzahar": -2, "Lissandra": -2, "Galio": -2,
        "Veigar": 2, "Syndra": 1, "Orianna": 1,
    },
    "Fizz": {
        "Malzahar": -2, "Galio": -2, "Lissandra": -1,
        "Veigar": 2, "Viktor": 1, "Syndra": 1,
    },
    "Yone": {
        "Renekton": -2, "Pantheon": -2, "Akali": -1,
        "Veigar": 1, "Viktor": 1,
    },
    "Yasuo": {
        "Renekton": -2, "Pantheon": -2, "Malzahar": -1,
        "Syndra": 1, "Lux": 1,  # windwall blocks
    },
    "AurelionSol": {
        "Fizz": -2, "Zed": -2, "LeBlanc": -2, "Akali": -1,
        "Malzahar": 1, "Viktor": 0,
    },
    "Zoe": {
        "Fizz": -2, "Yasuo": -2, "Zed": -1,
        "Viktor": 1, "Orianna": 1,
    },

    # --- Top ---
    "Darius": {
        "Vayne": -3, "Quinn": -2, "Kayle": -1, "Kennen": -2,
        "Nasus": 2, "Gangplank": 1, "Ornn": 1,
    },
    "Fiora": {
        "Malphite": -2, "Quinn": -1, "Kennen": -1,
        "Darius": 1, "Ornn": 2, "Sion": 2,
    },
    "Nasus": {
        "Darius": -2, "Illaoi": -2, "Vayne": -3,
        "Malphite": 1, "Ornn": 1,
    },
    "Ornn": {
        "Fiora": -2, "Vayne": -2,
        "Darius": -1, "Nasus": -1,
        "Malphite": 1, "Sion": 1,
    },
}


def get_matchup_score(my_champ: str, enemy_champ: str) -> int:
    """
    Get matchup score for my_champ vs enemy_champ.
    Positive = favorable, Negative = unfavorable, 0 = neutral/unknown.
    """
    my_matchups = MATCHUPS.get(my_champ, {})
    return my_matchups.get(enemy_champ, 0)


def evaluate_pick_vs_enemies(my_champ: str, enemy_picks: list[str]) -> dict:
    """
    Evaluate how good a champion pick is against the current enemy draft.
    Returns total score and individual matchup details.
    """
    total_score = 0
    details = []

    for enemy in enemy_picks:
        score = get_matchup_score(my_champ, enemy)
        if score != 0:
            if score > 0:
                details.append(f"vs {enemy}: 유리 (+{score})")
            else:
                details.append(f"vs {enemy}: 불리 ({score})")
            total_score += score

    # Also check reverse — use enemy's matchup data about us
    for enemy in enemy_picks:
        if get_matchup_score(my_champ, enemy) != 0:
            continue  # already counted in forward check
        enemy_matchups = MATCHUPS.get(enemy, {})
        reverse_score = enemy_matchups.get(my_champ, 0)
        if reverse_score > 0:
            # Enemy has a known advantage over us
            details.append(f"vs {enemy}: 불리 (상대 상성)")
            total_score -= reverse_score
        elif reverse_score < 0:
            # Enemy is weak against us (we counter them)
            details.append(f"vs {enemy}: 유리 (상대 약점 +{-reverse_score})")
            total_score += (-reverse_score)

    return {
        "champion": my_champ,
        "matchup_score": total_score,
        "details": details,
    }


# ---------------------------------------------------------------------------
# Champion archetype tags — used for comp classification and pick suggestions
# Tags: engage, peel, poke, burst, sustain_dps, split, pick, tank, enchanter,
#        dive, wombo, hypercarry, hypercarry_enabler, safe, roam, lane_bully, siege, utility
# ---------------------------------------------------------------------------

CHAMPION_TAGS: dict[str, list[str]] = {
    # --- ADCs ---
    "Jinx": ["sustain_dps", "hypercarry"],
    "KogMaw": ["sustain_dps", "hypercarry"],
    "Twitch": ["sustain_dps", "hypercarry"],
    "Vayne": ["sustain_dps", "hypercarry", "split", "short_range"],
    "Aphelios": ["sustain_dps", "hypercarry"],
    "Zeri": ["sustain_dps", "hypercarry"],
    "Smolder": ["sustain_dps", "hypercarry", "poke"],
    "Caitlyn": ["poke", "siege", "long_range", "lane_bully"],
    "Ezreal": ["poke", "safe"],
    "Varus": ["poke", "engage", "long_range"],
    "Jhin": ["poke", "pick", "utility", "long_range"],
    "Ashe": ["utility", "engage", "poke", "long_range"],
    "MissFortune": ["burst", "wombo"],
    "Xayah": ["sustain_dps", "safe"],
    "Kaisa": ["burst", "dive", "sustain_dps", "short_range"],
    "Lucian": ["burst", "lane_bully", "short_range"],
    "Draven": ["burst", "lane_bully", "short_range"],
    "Samira": ["dive", "burst", "short_range"],
    "Nilah": ["dive", "burst", "short_range"],
    "Kalista": ["sustain_dps", "engage", "utility"],
    "Tristana": ["burst", "siege", "safe", "long_range"],
    "Sivir": ["sustain_dps", "siege", "utility"],
    "Ziggs": ["poke", "siege"],
    "Corki": ["poke", "burst"],

    # --- Supports ---
    "Thresh": ["engage", "peel", "pick"],
    "Nautilus": ["engage", "tank", "pick"],
    "Leona": ["engage", "tank"],
    "Alistar": ["engage", "tank", "peel"],
    "Blitzcrank": ["pick", "engage"],
    "Pyke": ["pick", "engage"],
    "Rakan": ["engage", "enchanter"],
    "Rell": ["engage", "tank"],
    "Milio": ["enchanter", "peel"],
    "Lulu": ["enchanter", "peel", "hypercarry_enabler"],
    "Janna": ["enchanter", "peel"],
    "Soraka": ["enchanter", "sustain"],
    "Nami": ["enchanter", "poke", "peel"],
    "Yuumi": ["enchanter", "hypercarry_enabler"],
    "Sona": ["enchanter", "sustain", "wombo"],
    "Karma": ["enchanter", "poke"],
    "Morgana": ["peel", "pick"],
    "Lux": ["poke", "burst", "pick"],
    "Zyra": ["poke", "wombo"],
    "Brand": ["poke", "burst", "wombo"],
    "Xerath": ["poke", "siege"],
    "Vel'Koz": ["poke", "siege"],
    "Senna": ["sustain", "poke", "utility", "long_range"],
    "TahmKench": ["peel", "tank"],
    "Braum": ["peel", "tank"],
    "Renata": ["enchanter", "peel"],
    "Bard": ["pick", "utility", "roam"],
    "Poppy": ["peel", "tank"],
    "Galio": ["engage", "tank", "roam"],
    "Swain": ["sustain_dps", "engage"],
    "Zilean": ["utility", "peel", "safe"],
    "Taric": ["peel", "tank", "engage"],
    "Seraphine": ["wombo", "poke", "enchanter"],

    # --- Junglers ---
    "LeeSin": ["pick", "engage", "dive"],
    "JarvanIV": ["engage", "wombo", "dive"],
    "Amumu": ["engage", "wombo", "tank"],
    "Sejuani": ["engage", "tank", "wombo"],
    "Zac": ["engage", "tank"],
    "Vi": ["pick", "dive"],
    "Hecarim": ["engage", "dive"],
    "Rammus": ["engage", "tank"],
    "Maokai": ["engage", "tank", "peel"],
    "Elise": ["pick", "dive", "burst"],
    "Nidalee": ["poke", "pick"],
    "KhaZix": ["pick", "burst", "split"],
    "Rengar": ["pick", "burst"],
    "Evelynn": ["pick", "burst"],
    "Kayn": ["dive", "burst"],
    "Viego": ["dive", "sustain_dps"],
    "Graves": ["burst", "split"],
    "Kindred": ["sustain_dps", "safe"],
    "Lillia": ["poke", "wombo"],
    "Diana": ["dive", "wombo", "burst"],
    "Wukong": ["engage", "wombo", "dive"],
    "Nocturne": ["pick", "dive"],
    "Shaco": ["pick", "split"],
    "MasterYi": ["sustain_dps", "hypercarry", "split"],
    "Belveth": ["sustain_dps", "hypercarry", "split"],
    "Briar": ["dive", "burst"],
    "Ivern": ["enchanter", "peel"],
    "Nunu": ["engage", "tank", "wombo"],
    "Fiddlesticks": ["engage", "wombo", "burst"],
    "Warwick": ["dive", "sustain_dps", "pick"],
    "XinZhao": ["dive", "engage"],
    "Udyr": ["split", "tank", "dive"],
    "Skarner": ["engage", "pick", "tank"],
    "Taliyah": ["burst", "pick", "roam"],
    "Volibear": ["dive", "tank", "split"],

    # --- Mid laners ---
    "Ahri": ["pick", "burst", "safe"],
    "Syndra": ["burst", "poke"],
    "Orianna": ["wombo", "peel", "poke"],
    "Viktor": ["poke", "wombo", "siege"],
    "Azir": ["sustain_dps", "siege", "peel"],
    "Cassiopeia": ["sustain_dps", "peel"],
    "Zed": ["burst", "pick", "split"],
    "Talon": ["burst", "pick", "roam"],
    "Fizz": ["burst", "pick", "dive"],
    "LeBlanc": ["burst", "pick"],
    "Katarina": ["burst", "dive"],
    "Akali": ["burst", "dive", "split"],
    "Yasuo": ["sustain_dps", "dive", "wombo"],
    "Yone": ["dive", "engage", "wombo"],
    "Sylas": ["dive", "burst"],
    "TwistedFate": ["pick", "roam", "utility"],
    "Ryze": ["sustain_dps", "utility"],
    "Anivia": ["poke", "peel", "siege"],
    "Malzahar": ["pick", "siege"],
    "Veigar": ["burst", "peel", "pick"],
    "AurelionSol": ["poke", "sustain_dps", "siege"],
    "Hwei": ["poke", "wombo", "utility"],
    "Naafiri": ["burst", "pick", "dive"],
    "Zoe": ["poke", "pick", "burst"],
    "Neeko": ["wombo", "engage", "burst"],
    "Seraphine": ["wombo", "poke", "enchanter"],
    "Annie": ["engage", "burst", "wombo"],
    "Mel": ["poke", "utility", "siege"],
    "Lissandra": ["engage", "peel", "burst"],
    "Aurora": ["burst", "dive", "poke"],
    "Swain": ["sustain_dps", "engage", "poke"],
    "Karthus": ["poke", "sustain_dps", "wombo"],
    "Heimerdinger": ["poke", "siege", "zone"],
    "Taliyah": ["burst", "poke", "pick"],
    "Zaahen": ["dive", "burst", "split"],
    "Yunara": ["enchanter", "poke", "utility"],
    "Ekko": ["burst", "dive", "safe"],
    "Pantheon": ["burst", "pick", "roam"],
    "Xerath": ["poke", "siege"],
    "Vel'Koz": ["poke", "siege", "burst"],

    # --- Top laners ---
    "Ornn": ["engage", "tank", "wombo"],
    "Malphite": ["engage", "tank", "wombo"],
    "Sion": ["engage", "tank", "split"],
    "KSante": ["engage", "tank", "dive"],
    "Gnar": ["engage", "tank", "poke"],
    "Darius": ["lane_bully", "split"],
    "Garen": ["split", "tank"],
    "Mordekaiser": ["split", "dive"],
    "Fiora": ["split", "sustain_dps"],
    "Camille": ["split", "pick", "dive"],
    "Jax": ["split", "sustain_dps", "dive"],
    "Irelia": ["dive", "sustain_dps", "split"],
    "Riven": ["dive", "burst", "split"],
    "Aatrox": ["dive", "sustain_dps"],
    "Renekton": ["dive", "lane_bully"],
    "Jayce": ["poke", "siege", "split"],
    "Kennen": ["engage", "wombo"],
    "Rumble": ["wombo", "poke"],
    "Gangplank": ["poke", "split", "wombo"],
    "Shen": ["peel", "engage", "split"],
    "Quinn": ["split", "pick", "roam"],
    "Teemo": ["split", "poke"],
    "Nasus": ["split", "sustain_dps"],
    "Tryndamere": ["split", "sustain_dps"],
    "Yorick": ["split", "siege"],
    "Illaoi": ["split", "sustain_dps"],
    "Volibear": ["dive", "tank", "split"],
    "Urgot": ["sustain_dps", "tank"],
    "Cho'Gath": ["tank", "peel"],
    "Dr.Mundo": ["tank", "split"],
    "Singed": ["split", "engage"],
    "Gragas": ["engage", "peel", "burst"],
    "Ambessa": ["dive", "burst", "split"],
    "Kayle": ["hypercarry", "sustain_dps", "split"],
    "Wukong": ["engage", "wombo", "dive"],
    "Pantheon": ["burst", "pick", "roam"],
}
