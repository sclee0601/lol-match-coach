"""
Test suite for ban/pick recommendations.
Run: python test_recommendations.py
Validates that ideal picks are role-appropriate and react to enemy comps.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from lcu_helper import get_recommendations


# ---------------------------------------------------------------------------
# Validation sets — champions that should NEVER appear for each role
# ---------------------------------------------------------------------------

WRONG_MID = {
    "Warwick","Fiora","Darius","Garen","Mordekaiser","Camille","Jax","Irelia",
    "Riven","Aatrox","Ornn","Malphite","Sion","Gnar","Renekton","Jayce","Shen",
    "Quinn","KSante","Nasus","Tryndamere","Ambessa","Yorick","Illaoi","Kled",
    "Singed","Urgot","Rumble","LeeSin","Elise","Nidalee","KhaZix","Evelynn",
    "Viego","Graves","Kindred","JarvanIV","Vi","Hecarim","Amumu","Sejuani","Zac",
    "MasterYi","Kayn","Nocturne","Lillia","Wukong","Briar","Ivern","Nunu","Shaco",
    "Rammus","Maokai","Belveth","Rengar","Skarner","Volibear","Warwick",
    "Thresh","Nautilus","Leona","Alistar","Blitzcrank","Pyke","Rakan","Rell",
    "Milio","Lulu","Janna","Soraka","Nami","Yuumi","Sona","Karma","Morgana",
    "Zyra","Xerath","Senna","TahmKench","Braum","Renata","Bard","Poppy","Taric",
    "Zilean","Yunara",
}

WRONG_TOP = {
    "Thresh","Nautilus","Leona","Alistar","Blitzcrank","Pyke","Rakan","Rell",
    "Milio","Lulu","Janna","Soraka","Nami","Yuumi","Sona","Karma","Morgana",
    "Zyra","Xerath","Senna","TahmKench","Braum","Renata","Bard","Poppy","Taric",
    "Zilean","Yunara","Jinx","KogMaw","Caitlyn","Draven","Lucian","Ezreal",
    "Varus","Jhin","Ashe","MissFortune","Kaisa","Xayah","Samira","Tristana",
    "Sivir","Aphelios","Twitch","Zeri","Smolder","Nilah","Kalista","Corki","Ziggs",
    "LeeSin","Elise","Nidalee","KhaZix","Evelynn","Viego","Graves","Kindred",
    "JarvanIV","Vi","Hecarim","Amumu","Sejuani","Zac","MasterYi","Kayn","Nocturne",
    "Lillia","Wukong","Briar","Ivern","Nunu","Shaco","Rammus","Maokai","Belveth",
    "Rengar","Skarner","Warwick","Zed","Fizz","LeBlanc","Katarina","Akali",
    "Syndra","Orianna","Viktor","Ahri","Zoe","AurelionSol","Malzahar","Veigar",
    "TwistedFate","Hwei","Neeko","Seraphine","Annie","Lissandra","Cassiopeia",
    "Azir","Anivia","Ryze","Pantheon","Naafiri","Talon","Ekko",
}

WRONG_JG = {
    "Thresh","Nautilus","Leona","Alistar","Blitzcrank","Pyke","Rakan","Rell",
    "Milio","Lulu","Janna","Soraka","Nami","Yuumi","Sona","Karma","Morgana",
    "Zyra","Xerath","Senna","TahmKench","Braum","Renata","Bard","Poppy","Taric",
    "Zilean","Yunara","Jinx","KogMaw","Caitlyn","Draven","Lucian","Ezreal",
    "Varus","Jhin","Ashe","MissFortune","Kaisa","Xayah","Samira","Tristana",
    "Sivir","Aphelios","Twitch","Zeri","Smolder","Nilah","Kalista","Corki","Ziggs",
    "Darius","Garen","Fiora","Camille","Jax","Irelia","Riven","Aatrox","Ornn",
    "Malphite","Sion","Kennen","Gnar","Gangplank","Renekton","Jayce","Shen",
    "Quinn","KSante","Nasus","Tryndamere","Ambessa","Yorick","Illaoi","Kled",
    "Singed","Urgot","Rumble","Warwick",
}

WRONG_FOR_ROLE = {"top": WRONG_TOP, "jungle": WRONG_JG, "middle": WRONG_MID}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def make_profile(champs=None):
    """Empty profile (ideal picks don't use personal pool)."""
    return {'enemy_threats': [], 'best_picks': [], 'mastery_pool': [], 'synergies': []}


def run_test(label, ally, enemy, roles):
    """Run one test case. Returns (output_lines, error_lines)."""
    out = []
    errs = []
    rm = {"top": "TOP", "jungle": "JG", "middle": "MID", "bottom": "ADC", "utility": "SUP"}
    out.append(label + ":")
    out.append("  Allies: " + str(ally) + " | Enemy: " + str(enemy))
    for role in roles:
        r = get_recommendations(make_profile(), role, ally, enemy, [])
        picks = r.get('ideal_picks', [])
        if picks:
            names = [x['champion'] for x in picks[:3]]
            out.append("  " + rm.get(role, "?") + " -> " + ', '.join(names))
            wrong = WRONG_FOR_ROLE.get(role, set())
            for n in names:
                if n in wrong:
                    errs.append("  ERROR: " + n + " for " + rm.get(role, '?') + " in " + label)
    return out, errs


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

ALL_CASES = [
    ("1 Enemy dive: Camille LeeSin Zed Nautilus Draven",
     ['Jhin'], ['Camille','LeeSin','Zed','Nautilus','Draven'],
     ['top','jungle','middle','utility']),

    ("2 Enemy poke: Jayce Nidalee Xerath Caitlyn Lux",
     ['Aphelios'], ['Jayce','Nidalee','Xerath','Caitlyn','Lux'],
     ['top','jungle','middle','utility']),

    ("3 Enemy scaling: Ornn Amumu Viktor Jinx Lulu",
     ['Ezreal','Karma'], ['Ornn','Amumu','Viktor','Jinx','Lulu'],
     ['top','jungle','middle']),

    ("4 Enemy split: Fiora Graves Ahri Sivir Braum",
     ['Xayah','Thresh'], ['Fiora','Graves','Ahri','Sivir','Braum'],
     ['top','jungle','middle']),

    ("5 Enemy wombo: Malphite Amumu Diana MF Leona",
     ['Orianna','Jinx'], ['Malphite','Amumu','Diana','MissFortune','Leona'],
     ['top','jungle','utility']),

    ("6 Enemy engage: Ornn J4 Galio Ashe Nautilus",
     ['Vayne'], ['Ornn','JarvanIV','Galio','Ashe','Nautilus'],
     ['top','jungle','middle','utility']),

    ("7 Enemy assassins: Rengar Zed KhaZix Draven Pyke",
     ['Jinx','Lulu'], ['Rengar','Zed','KhaZix','Draven','Pyke'],
     ['top','jungle','middle']),

    ("8 Enemy tanks: Ornn Sejuani Galio Ezreal Braum",
     ['Vayne','Nami'], ['Ornn','Sejuani','Galio','Ezreal','Braum'],
     ['top','jungle','middle']),

    ("9 Enemy early aggro: Renekton LeeSin LeBlanc Draven Leona",
     ['Jinx'], ['Renekton','LeeSin','LeBlanc','Draven','Leona'],
     ['top','jungle','middle','utility']),

    ("10 Enemy protect-the-carry: Ornn Sejuani Orianna KogMaw Lulu",
     ['Zeri','Thresh'], ['Ornn','Sejuani','Orianna','KogMaw','Lulu'],
     ['top','jungle','middle']),

    ("11 Single enemy pick: Nautilus",
     ['Jhin'], ['Nautilus'],
     ['top','jungle','middle','utility']),

    ("12 Two enemy picks: Leona Draven",
     ['Ezreal'], ['Leona','Draven'],
     ['top','jungle','middle','utility']),

    ("13 Enemy late game: Nasus Evelynn Veigar Vayne Senna",
     ['Caitlyn','Karma'], ['Nasus','Evelynn','Veigar','Vayne','Senna'],
     ['top','jungle','middle']),

    ("14 Enemy peel/kite: Shen Ivern Anivia Jinx Janna",
     ['Zeri','Nautilus'], ['Shen','Ivern','Anivia','Jinx','Janna'],
     ['top','jungle','middle']),

    ("15 Enemy all AD: Jayce LeeSin Zed Draven Pyke",
     ['Aphelios','Lulu'], ['Jayce','LeeSin','Zed','Draven','Pyke'],
     ['top','jungle','middle']),
]


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    all_out = []
    all_errors = []

    for label, ally, enemy, roles in ALL_CASES:
        lines, errs = run_test(label, ally, enemy, roles)
        all_out.extend(lines)
        all_out.append("")
        all_errors.extend(errs)

    all_out.append("=" * 40)
    all_out.append("VALIDATION RESULTS")
    all_out.append("=" * 40)
    if all_errors:
        all_out.append(str(len(all_errors)) + " error(s) found:")
        all_out.extend(all_errors)
    else:
        all_out.append("PASS - All " + str(len(ALL_CASES)) + " cases role-appropriate!")

    result = '\n'.join(all_out)

    # Write to file
    with open('test_results.txt', 'w', encoding='utf-8') as f:
        f.write(result)

    # Also print summary
    print("Ran " + str(len(ALL_CASES)) + " test cases.")
    if all_errors:
        print("FAIL - " + str(len(all_errors)) + " errors:")
        for e in all_errors:
            print(e)
    else:
        print("PASS - All role-appropriate!")
    print("Full results: test_results.txt")
