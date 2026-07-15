import re
import os
import json
from collections import defaultdict

CONFIG_PATH = os.path.join(
    os.path.expanduser("~"), ".nwn_log_analyzer_config.json"
)

DEFAULT_CHARACTERS = ["Klanitha"]

IGNORED_NAMES = ["Someone", "Object", ""]

RE_ATK = re.compile(
    r"^(.*?) attacks (.*?) : \*(.*?)\* : \((\d+) \+ (\d+) = (\d+)"
    r"(?: : Threat Roll: (\d+) \+ (\d+) = (\d+))?\)"
)
RE_DMG = re.compile(r"^(.*?) damages (.*?): (\d+)(?: \((.*?)\))?")
RE_KILL = re.compile(r"^(.*?) killed (.*)")
RE_SAVE = re.compile(
    r"^(.*?) : (.*?) : \*(.*?)\* : \((\d+) \+ (\d+) = "
    r"(\d+) vs\. DC: (\d+)\)"
)
RE_DR = re.compile(r"^(.*?) : Damage Resistance absorbs (\d+) damage")
RE_IMMUNE = re.compile(
    r"^(.*?) : Damage Immunity.*?absorbs (\d+) damage"
)
RE_DMG_TYPE_PAIR = re.compile(r"([A-Za-z][A-Za-z ]*?)\s+(\d+)")


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "default_log_dir": os.getcwd(),
        "characters": DEFAULT_CHARACTERS,
    }


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def _new_monster_bucket():
    return {
        "ab": [], "hits_ac": [], "misses_ac": [],
        "dmg_val": 0, "dmg_count": 0,
    }


def _new_extra_bucket():
    return {
        "checks": defaultdict(lambda: {
            "totals": [], "dcs": [], "success": 0, "fail": 0
        }),
        "dr_absorbed": 0,
        "immunity_absorbed": 0,
        "concealed_against": 0,
        "concealment_pcts": [],
        "threat_rolls": [],
        "dmg_dealt_types": defaultdict(int),
        "dmg_taken_types": defaultdict(int),
        "hits_dealt": 0,
        "hits_taken": 0,
    }


def _strip_prefix(name):
    if " : " in name:
        return name.split(" : ")[-1]
    return name


def _parse_damage_types(details, fallback_val):
    """Return list of (type_name, amount) pairs from a details string
    like 'Physical 138, Cold 13'. Falls back to a single 'Physical'
    entry if no breakdown is present."""
    if not details:
        return [("Physical", fallback_val)]
    pairs = RE_DMG_TYPE_PAIR.findall(details)
    if not pairs:
        return [("Physical", fallback_val)]
    return [(dtype.strip(), int(amt)) for dtype, amt in pairs]


def analyze_nwn_log(file_paths, character_names):
    stats_pc = {
        name: {"kills": 0, "dmg_tot": 0, "hits_count": 0}
        for name in character_names
    }
    stats_m = defaultdict(_new_monster_bucket)
    extra_stats = defaultdict(_new_extra_bucket)

    files_processed, errors = 0, []

    for file_path in file_paths:
        try:
            with open(
                file_path, "r", encoding="utf-8", errors="ignore"
            ) as f:
                for line in f:
                    line = line.replace("[CHAT WINDOW TEXT] ", "")
                    line = re.sub(r"\[.*?\]\s*", "", line).strip()
                    if not line:
                        continue

                    if _handle_attack_line(line, stats_pc, stats_m,
                                            extra_stats):
                        continue
                    if _handle_save_line(line, extra_stats):
                        continue
                    if _handle_dr_line(line, extra_stats):
                        continue
                    if _handle_immunity_line(line, extra_stats):
                        continue
                    if _handle_damage_line(line, stats_pc, stats_m,
                                            extra_stats):
                        continue
                    if _handle_kill_line(line, stats_pc):
                        continue
        except FileNotFoundError:
            errors.append(file_path)
            continue
        else:
            files_processed += 1

    return files_processed, errors, stats_pc, stats_m, extra_stats


def _handle_attack_line(line, stats_pc, stats_m, extra_stats):
    m_atk = RE_ATK.search(line)
    if not m_atk:
        return False

    (atk, tgt, res, roll, bonus, total,
     threat_roll, threat_bonus, threat_total) = m_atk.groups()
    atk, tgt = _strip_prefix(atk.strip()), _strip_prefix(tgt.strip())
    res_l = res.lower()

    if "concealed" in res_l:
        pct_match = re.search(r"(\d+)%", res)
        pct = int(pct_match.group(1)) if pct_match else 0
        extra_stats[tgt]["concealed_against"] += 1
        extra_stats[tgt]["concealment_pcts"].append(pct)
    elif atk in stats_pc:
        if "hit" in res_l:
            stats_m[tgt]["hits_ac"].append(int(total))
        elif "miss" in res_l and int(roll) > 1:
            stats_m[tgt]["misses_ac"].append(int(total))
    elif tgt in stats_pc:
        stats_m[atk]["ab"].append(int(bonus))

    if threat_total is not None:
        extra_stats[atk]["threat_rolls"].append(int(threat_total))
    return True


def _handle_save_line(line, extra_stats):
    m_save = RE_SAVE.search(line)
    if not m_save:
        return False

    name, check_name, result, roll, bonus, total, dc = m_save.groups()
    name = _strip_prefix(name.strip())
    check_key = check_name.split(" vs.")[0].strip()

    bucket = extra_stats[name]["checks"][check_key]
    bucket["totals"].append(int(total))
    bucket["dcs"].append(int(dc))
    if "success" in result.lower():
        bucket["success"] += 1
    else:
        bucket["fail"] += 1
    return True


def _handle_dr_line(line, extra_stats):
    m_dr = RE_DR.search(line)
    if not m_dr:
        return False
    name, amount = m_dr.groups()
    extra_stats[name.strip()]["dr_absorbed"] += int(amount)
    return True


def _handle_immunity_line(line, extra_stats):
    m_immune = RE_IMMUNE.search(line)
    if not m_immune:
        return False
    name, amount = m_immune.groups()
    extra_stats[name.strip()]["immunity_absorbed"] += int(amount)
    return True


def _handle_damage_line(line, stats_pc, stats_m, extra_stats):
    m_dmg = RE_DMG.search(line)
    if not m_dmg:
        return False

    atk, tgt, val, details = m_dmg.groups()
    atk, tgt, val = _strip_prefix(atk.strip()), _strip_prefix(
        tgt.strip()), int(val)

    for dtype, amt in _parse_damage_types(details, val):
        extra_stats[atk]["dmg_dealt_types"][dtype] += amt
        extra_stats[tgt]["dmg_taken_types"][dtype] += amt

    if atk in stats_pc:
        stats_pc[atk]["dmg_tot"] += val
        if (atk == "Rayna Ralien" or atk == "Selkie Smoothhand") and \
                details and "Divine" in details:
            pass
        else:
            stats_pc[atk]["hits_count"] += 1
    elif tgt in stats_pc:
        stats_m[atk]["dmg_val"] += val
        stats_m[atk]["dmg_count"] += 1

    extra_stats[atk]["hits_dealt"] += 1
    extra_stats[tgt]["hits_taken"] += 1
    return True


def _handle_kill_line(line, stats_pc):
    m_kil = RE_KILL.search(line)
    if not m_kil:
        return False
    kil, vic = m_kil.groups()
    kil = _strip_prefix(kil.strip())
    if kil in stats_pc:
        stats_pc[kil]["kills"] += 1
    return True
