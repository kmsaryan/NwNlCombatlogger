import re
import os
import glob
import streamlit as st
from collections import defaultdict


SPECIAL_NAMES = {"Someone", "Object", ""}


def _is_special_name(name):
    return name in SPECIAL_NAMES


def _strip_name_prefix(value):
    value = value.strip()
    if " : " in value:
        return value.split(" : ")[-1]
    return value


def _format_range(low, high):
    return "{} - {}".format(low, high)


def _log_sort_key(path):
    basename = os.path.basename(path)
    match = re.search(r"(\d+)", basename)
    return int(match.group(1)) if match else 0


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
                lambda: {
                    "totals": [],
                    "dcs": [],
                    "success": 0,
                    "fail": 0,
                }
            ),
            "dr_absorbed": 0,
            "immunity_absorbed": 0,
            "concealed_against": 0,
            "concealment_pcts": [],
            "threat_rolls": [],
        }
    )

    re_atk = re.compile(
        r"^(.*?) attacks (.*?) : \*(.*?)\* : \((\d+) \+ (\d+) = (\d+)"
        r"(?: : Threat Roll: (\d+) \+ (\d+) = (\d+))?\)"
    )
    re_dmg = re.compile(r"^(.*?) damages (.*?): (\d+)(?: \((.*?)\))?")
    re_kill = re.compile(r"^(.*?) killed (.*)")
    re_save = re.compile(
        r"^(.*?) : (.*?) : \*(.*?)\* : "
        r"\((\d+) \+ (\d+) = (\d+) vs\. DC: (\d+)\)"
    )
    re_dr = re.compile(r"^(.*?) : Damage Resistance absorbs (\d+) damage")
    re_immune = re.compile(
        r"^(.*?) : Damage Immunity.*?absorbs (\d+) damage"
    )

    files_processed = 0
    for file_path in file_paths:
        try:
            with open(
                file_path,
                "r",
                encoding="utf-8",
                errors="ignore",
            ) as f:
                for line in f:
                    line = line.replace("[CHAT WINDOW TEXT] ", "")
                    line = re.sub(r"\[.*?\]\s*", "", line).strip()
                    if not line:
                        continue

                    m_atk = re_atk.search(line)
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
                        res_l = res.lower()
                        if "concealed" in res_l:
                            pct_match = re.search(r"(\d+)%", res)
                            pct = (
                                int(pct_match.group(1))
                                if pct_match
                                else 0
                            )
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
                            extra_stats[atk]["threat_rolls"].append(
                                int(threat_total)
                            )
                        continue

                    m_save = re_save.search(line)
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
                        name = name.strip()
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

                    m_dr = re_dr.search(line)
                    if m_dr:
                        name, amount = m_dr.groups()
                        extra_stats[name.strip()]["dr_absorbed"] += int(amount)
                        continue

                    m_immune = re_immune.search(line)
                    if m_immune:
                        name, amount = m_immune.groups()
                        extra_stats[name.strip()]["immunity_absorbed"] += int(
                            amount
                        )
                        continue

                    m_dmg = re_dmg.search(line)
                    if m_dmg:
                        atk, tgt, val, details = m_dmg.groups()
                        atk = _strip_name_prefix(atk)
                        tgt = _strip_name_prefix(tgt)
                        val = int(val)
                        if atk in stats_pc:
                            stats_pc[atk]["dmg_tot"] += val
                            if (
                                atk == "Rayna Ralien"
                                or atk == "Selkie Smoothhand"
                            ) and details and "Divine" in details:
                                pass
                            else:
                                stats_pc[atk]["hits_count"] += 1
                        elif tgt in stats_pc:
                            stats_m[atk]["dmg_val"] += val
                            stats_m[atk]["dmg_count"] += 1
                        continue

                    m_kil = re_kill.search(line)
                    if m_kil:
                        kil, vic = m_kil.groups()
                        kil = kil.strip()
                        kil = _strip_name_prefix(kil)
                        if kil in stats_pc:
                            stats_pc[kil]["kills"] += 1
        except FileNotFoundError:
            st.warning(
                "File '{}' was not found. Skipping.".format(file_path)
            )
            continue
        else:
            files_processed += 1

    return files_processed, stats_pc, stats_m, extra_stats


st.set_page_config(page_title="NWN Log Analyzer", layout="wide")
st.title("NWN Combat Log Analyzer")

st.sidebar.header("Configuration")

script_dir = os.getcwd()
default_files = sorted(
    glob.glob(os.path.join(script_dir, "nwclientLog*.txt")),
    key=_log_sort_key,
)
default_file_names = [os.path.basename(p) for p in default_files]

uploaded_files = st.sidebar.file_uploader(
    "Upload log file(s)",
    type=["txt", "log"],
    accept_multiple_files=True,
)

selected_local_files = st.sidebar.multiselect(
    "Or select local log files (found in current directory)",
    options=default_file_names,
    default=default_file_names,
)

char_input = st.sidebar.text_area(
    "Character names (one per line)",
    value="Hamar Wetton\nKlanita Brina",
    height=140,
)
character_names = [
    c.strip()
    for c in char_input.splitlines()
    if c.strip()
]

run_button = st.sidebar.button("Analyze Log(s)")

if run_button:
    file_paths = []
    temp_paths = []
    if uploaded_files:
        for uf in uploaded_files:
            tmp_path = os.path.join(
                script_dir,
                "_uploaded_" + uf.name,
            )
            with open(tmp_path, "wb") as out:
                out.write(uf.getbuffer())
            file_paths.append(tmp_path)
            temp_paths.append(tmp_path)
    for fname in selected_local_files:
        file_paths.append(os.path.join(script_dir, fname))

    if not file_paths:
        st.error("No log files selected or uploaded.")
    else:
        files_processed, stats_pc, stats_m, extra_stats = analyze_nwn_log(
            file_paths,
            character_names,
        )
        st.success("Processed {} file(s).".format(files_processed))

        tab1, tab2, tab3, tab4 = st.tabs(
            [
                "Character Stats",
                "Monster Stats",
                "Saving Throws",
                "Mitigation & Threat",
            ]
        )

        with tab1:
            rows = []
            for p in character_names:
                d = stats_pc[p]
                avg = (
                    d["dmg_tot"] / d["hits_count"]
                    if d["hits_count"] > 0
                    else 0
                )
                rows.append(
                    {
                        "Character": p,
                        "Kills": d["kills"],
                        "Total Damage": d["dmg_tot"],
                        "Avg/Hit": round(avg, 2),
                    }
                )
            st.dataframe(rows, use_container_width=True)

        with tab2:
            rows = []
            for m, d in sorted(stats_m.items()):
                if m in character_names or _is_special_name(m):
                    continue
                max_ab = max(d["ab"]) if d["ab"] else 0
                hi_miss = (
                    max(d["misses_ac"]) + 1
                    if d["misses_ac"]
                    else None
                )
                lo_hit = min(d["hits_ac"]) if d["hits_ac"] else None
                ac_range = _format_range(
                    hi_miss if hi_miss is not None else "?",
                    lo_hit if lo_hit is not None else "?",
                )
                avg_m = (
                    d["dmg_val"] / d["dmg_count"]
                    if d["dmg_count"] > 0
                    else 0
                )
                rows.append(
                    {
                        "Monster": m,
                        "Max AB": max_ab,
                        "AC Range": ac_range,
                        "Avg Dmg": round(avg_m, 2),
                    }
                )
            st.dataframe(rows, use_container_width=True)

        def is_character(name):
            return name in character_names

        with tab3:
            st.subheader("Character Saving Throws / Checks")
            rows_c, rows_m = [], []
            for name, d in sorted(extra_stats.items()):
                if _is_special_name(name):
                    continue
                target = rows_c if is_character(name) else rows_m
                for check_key, res in sorted(d["checks"].items()):
                    totals = res["totals"]
                    if not totals:
                        continue
                    dcs = res["dcs"]
                    target.append(
                        {
                            "Name": name,
                            "Check": check_key,
                            "Count": len(totals),
                            "Roll Range": _format_range(
                                min(totals),
                                max(totals),
                            ),
                            "DC Range": _format_range(min(dcs), max(dcs)),
                            "Avg Roll": round(sum(totals) / len(totals), 2),
                        }
                    )
            st.dataframe(rows_c, use_container_width=True)
            st.subheader("Monster Saving Throws / Checks")
            st.dataframe(rows_m, use_container_width=True)

        with tab4:
            st.subheader("Damage Mitigation & Concealment")
            rows = []
            for name, d in sorted(extra_stats.items()):
                if _is_special_name(name):
                    continue
                if (
                    d["dr_absorbed"] == 0
                    and d["immunity_absorbed"] == 0
                    and d["concealed_against"] == 0
                ):
                    continue
                avg_pct = (
                    sum(d["concealment_pcts"]) / len(d["concealment_pcts"])
                    if d["concealment_pcts"]
                    else 0
                )
                rows.append(
                    {
                        "Name": name,
                        "Category": (
                            "Character"
                            if is_character(name)
                            else "Monster"
                        ),
                        "DR Absorbed": d["dr_absorbed"],
                        "Immunity Absorbed": d["immunity_absorbed"],
                        "Concealed Count": d["concealed_against"],
                        "Avg Conceal %": round(avg_pct, 1),
                    }
                )
            st.dataframe(rows, use_container_width=True)

            st.subheader("Threat Rolls")
            rows = []
            for name, d in sorted(extra_stats.items()):
                if _is_special_name(name) or not d["threat_rolls"]:
                    continue
                tr = d["threat_rolls"]
                rows.append(
                    {
                        "Name": name,
                        "Category": (
                            "Character"
                            if is_character(name)
                            else "Monster"
                        ),
                        "Count": len(tr),
                        "Max": max(tr),
                        "Avg": round(sum(tr) / len(tr), 2),
                    }
                )
            st.dataframe(rows, use_container_width=True)

    for tp in temp_paths:
        try:
            os.remove(tp)
        except OSError:
            pass
else:
    st.info("Configure options in the sidebar, then click 'Analyze Log(s)'.")
