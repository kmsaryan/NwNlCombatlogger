import argparse
import glob
import os
import re
from collections import defaultdict


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SPECIAL_NAMES = {"Someone", "Object", ""}
QUOTE_CHARS = " \t\r\n'\"‘’“”"

RE_ATK = re.compile(
    r"^(.*?) attacks (.*?) : \*(.*?)\* : \((\d+) \+ (\d+) = (\d+)"
    r"(?: : Threat Roll: (\d+) \+ (\d+) = (\d+))?\)"
)
RE_DMG = re.compile(r"^(.*?) damages (.*?): (\d+)(?: \((.*?)\))?")
RE_KILL = re.compile(r"^(.*?) killed (.*)")
RE_SAVE = re.compile(
    r"^(.*?) : (.*?) : \*(.*?)\* : \((\d+) \+ (\d+) = (\d+) vs\. DC: (\d+)\)"
)
RE_DR = re.compile(r"^(.*?) : Damage Resistance absorbs (\d+) damage")
RE_IMMUNE = re.compile(r"^(.*?) : Damage Immunity.*?absorbs (\d+) damage")


def _clean_line(line):
    line = line.replace("[CHAT WINDOW TEXT] ", "")
    return re.sub(r"\[.*?\]\s*", "", line).strip()


def _strip_name_prefix(value):
    value = value.strip()
    if " : " in value:
        return value.split(" : ")[-1]
    return value


def _format_range(low, high):
    return "{} - {}".format(low, high)


def _resolve_log_path(raw_path):
    arg = raw_path.strip().strip(QUOTE_CHARS)
    candidates = [
        arg,
        os.path.join(os.getcwd(), arg),
        os.path.join(SCRIPT_DIR, arg),
        os.path.abspath(arg),
    ]

    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate

    return None


def _sorted_log_files(pattern):
    matches = glob.glob(pattern)

    def log_sort_key(path):
        match = re.search(r"(\d+)", os.path.basename(path))
        return int(match.group(1)) if match else 0

    return sorted(matches, key=log_sort_key)


def analyze_nwn_log(file_paths, character_names):
    stats_pc = {
        name: {"kills": 0, "dmg_tot": 0, "hits_count": 0}
        for name in character_names
    }
    stats_m = defaultdict(
        lambda: {
            "ab": [],
            "hits_ac": [],
            "misses_ac": [],
            "dmg_val": 0,
            "dmg_count": 0,
        }
    )
    extra_stats = defaultdict(
        lambda: {
            "checks": defaultdict(
                lambda: {"totals": [], "dcs": [], "success": 0, "fail": 0}
            ),
            "dr_absorbed": 0,
            "immunity_absorbed": 0,
            "concealed_against": 0,
            "concealment_pcts": [],
            "threat_rolls": [],
        }
    )

    files_processed = 0

    for raw_path in file_paths:
        file_path = _resolve_log_path(raw_path)
        if not file_path:
            print(
                "Warning: The file '{}' was not found. Skipping.".format(
                    raw_path
                )
            )
            continue

        try:
            with open(
                file_path,
                "r",
                encoding="utf-8",
                errors="ignore",
            ) as file_handle:
                for raw_line in file_handle:
                    line = _clean_line(raw_line)
                    if not line:
                        continue

                    m_atk = RE_ATK.search(line)
                    if m_atk:
                        (
                            atk,
                            tgt,
                            res,
                            roll,
                            bonus,
                            total,
                            threat_roll,
                            threat_bonus,
                            threat_total,
                        ) = m_atk.groups()
                        atk = _strip_name_prefix(atk)
                        tgt = _strip_name_prefix(tgt)
                        res_lower = res.lower()

                        if "concealed" in res_lower:
                            pct_match = re.search(r"(\d+)%", res)
                            pct = int(pct_match.group(1)) if pct_match else 0
                            extra_stats[tgt]["concealed_against"] += 1
                            extra_stats[tgt]["concealment_pcts"].append(pct)
                        elif atk in stats_pc:
                            if "hit" in res_lower:
                                stats_m[tgt]["hits_ac"].append(int(total))
                            elif "miss" in res_lower and int(roll) > 1:
                                stats_m[tgt]["misses_ac"].append(int(total))
                        elif tgt in stats_pc:
                            stats_m[atk]["ab"].append(int(bonus))

                        if threat_total is not None:
                            extra_stats[atk]["threat_rolls"].append(
                                int(threat_total)
                            )
                        continue

                    m_save = RE_SAVE.search(line)
                    if m_save:
                        (
                            name,
                            check_name,
                            result,
                            roll,
                            bonus,
                            total,
                            dc,
                        ) = m_save.groups()
                        name = _strip_name_prefix(name)
                        check_key = check_name.split(" vs.")[0].strip()

                        bucket = extra_stats[name]["checks"][check_key]
                        bucket["totals"].append(int(total))
                        bucket["dcs"].append(int(dc))
                        if "success" in result.lower():
                            bucket["success"] += 1
                        else:
                            bucket["fail"] += 1
                        continue

                    m_dr = RE_DR.search(line)
                    if m_dr:
                        name, amount = m_dr.groups()
                        extra_stats[name.strip()]["dr_absorbed"] += int(amount)
                        continue

                    m_immune = RE_IMMUNE.search(line)
                    if m_immune:
                        name, amount = m_immune.groups()
                        extra_stats[name.strip()][
                            "immunity_absorbed"
                        ] += int(amount)
                        continue

                    m_dmg = RE_DMG.search(line)
                    if m_dmg:
                        atk, tgt, val, details = m_dmg.groups()
                        atk = _strip_name_prefix(atk)
                        tgt = _strip_name_prefix(tgt)
                        val = int(val)

                        if atk in stats_pc:
                            stats_pc[atk]["dmg_tot"] += val
                            if (
                                atk in {"Rayna Ralien", "Selkie Smoothhand"}
                                and details
                                and "Divine" in details
                            ):
                                pass
                            else:
                                stats_pc[atk]["hits_count"] += 1
                        elif tgt in stats_pc:
                            stats_m[atk]["dmg_val"] += val
                            stats_m[atk]["dmg_count"] += 1
                        continue

                    m_kill = RE_KILL.search(line)
                    if m_kill:
                        killer, _victim = m_kill.groups()
                        killer = _strip_name_prefix(killer)
                        if killer in stats_pc:
                            stats_pc[killer]["kills"] += 1

        except FileNotFoundError:
            print(
                "Warning: The file '{}' was not found. Skipping.".format(
                    raw_path
                )
            )
            continue

        files_processed += 1

    if files_processed == 0:
        print("Error: None of the specified log files were found.")
        return

    def is_character(name):
        return name in character_names

    print("\n" + "=" * 70)
    print(
        "{:<20} | {:<7} | {:<12} | {}".format(
            "CHARACTER",
            "KILLS",
            "TOTAL DMG",
            "AVG/HIT",
        )
    )
    print("-" * 70)
    for character_name in character_names:
        data = stats_pc[character_name]
        avg = (
            data["dmg_tot"] / data["hits_count"]
            if data["hits_count"] > 0
            else 0
        )
        print(
            "{:<20} | {:<7} | {:<12,} | {:.2f}".format(
                character_name,
                data["kills"],
                data["dmg_tot"],
                avg,
            )
        )

    print("\n" + "=" * 90)
    print(
        "{:<25} | {:<8} | {:<15} | {}".format(
            "MONSTER TYPE",
            "MAX AB",
            "AC RANGE",
            "AVG DMG",
        )
    )
    print("-" * 90)
    for monster_name, data in sorted(stats_m.items()):
        if monster_name in character_names or monster_name in SPECIAL_NAMES:
            continue

        max_ab = max(data["ab"]) if data["ab"] else 0
        hi_miss = max(data["misses_ac"]) + 1 if data["misses_ac"] else "?"
        lo_hit = min(data["hits_ac"]) if data["hits_ac"] else "?"
        avg_m = (
            data["dmg_val"] / data["dmg_count"]
            if data["dmg_count"] > 0
            else 0
        )

        print(
            "{:<25} | {:<8} | {:<15} | {:.2f}".format(
                monster_name,
                max_ab,
                _format_range(hi_miss, lo_hit),
                avg_m,
            )
        )

    for label, include_character in (
        ("CHARACTER SAVING THROWS / CHECKS", True),
        ("MONSTER SAVING THROWS / CHECKS", False),
    ):
        print("\n" + "=" * 100)
        print(label)
        print("-" * 100)
        print(
            "{:<20} | {:<22} | {:<6} | {:<14} | {:<14} | {}".format(
                "NAME",
                "CHECK TYPE",
                "COUNT",
                "ROLL RANGE",
                "DC RANGE",
                "AVG ROLL",
            )
        )

        for name, data in sorted(extra_stats.items()):
            if (
                name in SPECIAL_NAMES
                or is_character(name) != include_character
            ):
                continue

            for check_key, result in sorted(data["checks"].items()):
                totals = result["totals"]
                if not totals:
                    continue

                dcs = result["dcs"]
                row_format = (
                    "{:<20} | {:<22} | {:<6} | {:<14} | {:<14} | {:.2f}"
                )
                print(
                    row_format.format(
                        name,
                        check_key,
                        len(totals),
                        _format_range(min(totals), max(totals)),
                        _format_range(min(dcs), max(dcs)),
                        sum(totals) / len(totals),
                    )
                )

    for label, include_character in (
        ("CHARACTER DAMAGE MITIGATION & CONCEALMENT", True),
        ("MONSTER DAMAGE MITIGATION & CONCEALMENT", False),
    ):
        print("\n" + "=" * 90)
        print(label)
        print("-" * 90)
        print(
            "{:<20} | {:<12} | {:<12} | {:<10} | {}".format(
                "NAME",
                "DR ABSORBED",
                "IMM ABSORBED",
                "CONCEALED",
                "AVG CONCEAL %",
            )
        )

        for name, data in sorted(extra_stats.items()):
            if (
                name in SPECIAL_NAMES
                or is_character(name) != include_character
            ):
                continue
            if (
                data["dr_absorbed"] == 0
                and data["immunity_absorbed"] == 0
                and data["concealed_against"] == 0
            ):
                continue

            avg_pct = (
                sum(data["concealment_pcts"]) / len(data["concealment_pcts"])
                if data["concealment_pcts"]
                else 0
            )
            print(
                "{:<20} | {:<12} | {:<12} | {:<10} | {:.1f}%".format(
                    name,
                    data["dr_absorbed"],
                    data["immunity_absorbed"],
                    data["concealed_against"],
                    avg_pct,
                )
            )

    for label, include_character in (
        ("CHARACTER THREAT ROLLS", True),
        ("MONSTER THREAT ROLLS", False),
    ):
        print("\n" + "=" * 70)
        print(label)
        print("-" * 70)
        print(
            "{:<20} | {:<10} | {:<10} | {}".format(
                "NAME",
                "COUNT",
                "MAX",
                "AVG",
            )
        )

        for name, data in sorted(extra_stats.items()):
            if (
                name in SPECIAL_NAMES
                or is_character(name) != include_character
            ):
                continue
            if not data["threat_rolls"]:
                continue

            threat_rolls = data["threat_rolls"]
            print(
                "{:<20} | {:<10} | {:<10} | {:.2f}".format(
                    name,
                    len(threat_rolls),
                    max(threat_rolls),
                    sum(threat_rolls) / len(threat_rolls),
                )
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze an NWN combat log file."
    )
    parser.add_argument(
        "logfiles",
        nargs="*",
        default=None,
        help=(
            "One or more log file names (expected in the same directory as "
            "this script). If omitted, the script auto-detects files matching "
            "'nwclientLog*.txt' "
            "in the script's directory and processes all of them."
        ),
    )
    parser.add_argument(
        "-c",
        "--characters",
        nargs="+",
        default=[
            "Milky",
            "Oria Silverchain",
            "Hamar Wetton",
            "Balmafula Bloodfire",
            "Ashalynne Darkwine",
            "Elvorfilia Muner ",
            "Merri",
        ],
        help=(
            "List of character names to track (space-separated, use quotes "
            "for multi-word names)."
        ),
    )
    args = parser.parse_args()

    if args.logfiles:
        log_files = args.logfiles
    else:
        pattern = os.path.join(SCRIPT_DIR, "nwclientLog*.txt")
        log_files = _sorted_log_files(pattern)
        if not log_files:
            log_files = ["nwclientLog1.txt"]

    analyze_nwn_log(log_files, args.characters)
