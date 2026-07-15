import re
import os
import json
import glob
import ctypes
import platform
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from collections import defaultdict

CONFIG_PATH = os.path.join(
    os.path.expanduser("~"),
    ".nwn_log_analyzer_config.json")

DEFAULT_CHARACTERS = ["Klanita Brina"]


def _fix_windows_dpi_scaling():

    if platform.system() != "Windows":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"default_log_dir": os.getcwd(), "characters": DEFAULT_CHARACTERS}


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def analyze_nwn_log(file_paths, character_names):
    stats_pc = {name: {"kills": 0, "dmg_tot": 0, "hits_count": 0}
                for name in character_names}
    stats_m = defaultdict(
        lambda: {
            "ab": [],
            "hits_ac": [],
            "misses_ac": [],
            "dmg_val": 0,
            "dmg_count": 0})
    extra_stats = defaultdict(
        lambda: {
            "checks": defaultdict(
                lambda: {
                    "totals": [],
                    "dcs": [],
                    "success": 0,
                    "fail": 0}),
            "dr_absorbed": 0,
            "immunity_absorbed": 0,
            "concealed_against": 0,
            "concealment_pcts": [],
            "threat_rolls": []})

    re_atk = re.compile(
        r"^(.*?) attacks (.*?) : \*(.*?)\* : \((\d+) \+ (\d+) = (\d+)"
        r"(?: : Threat Roll: (\d+) \+ (\d+) = (\d+))?\)"
    )
    re_dmg = re.compile(r"^(.*?) damages (.*?): (\d+)(?: \((.*?)\))?")
    re_kill = re.compile(r"^(.*?) killed (.*)")
    re_save = re.compile(
        r"^(.*?) : (.*?) : \*(.*?)\* : \((\d+) \+ (\d+) = "
        r"(\d+) vs\. DC: (\d+)\)")
    re_dr = re.compile(r"^(.*?) : Damage Resistance absorbs (\d+) damage")
    re_immune = re.compile(r"^(.*?) : Damage Immunity.*?absorbs (\d+) damage")

    files_processed, errors = 0, []
    for file_path in file_paths:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.replace("[CHAT WINDOW TEXT] ", "")
                    line = re.sub(r"\[.*?\]\s*", "", line).strip()
                    if not line:
                        continue
                    m_atk = re_atk.search(line)
                    if m_atk:
                        (atk, tgt, res, roll, bonus, total, threat_roll,
                         threat_bonus, threat_total) = m_atk.groups()
                        atk, tgt, res_l = atk.strip(), tgt.strip(), res.lower()
                        if " : " in atk:
                            atk = atk.split(" : ")[-1]
                        if " : " in tgt:
                            tgt = tgt.split(" : ")[-1]
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
                            extra_stats[atk]["threat_rolls"].append(
                                int(threat_total))
                        continue
                    m_save = re_save.search(line)
                    if m_save:
                        (name, check_name, result, roll, bonus,
                         total, dc) = m_save.groups()
                        name = name.strip()
                        if " : " in name:
                            name = name.split(" : ")[-1]
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
                        extra_stats[name.strip(
                        )]["immunity_absorbed"] += int(amount)
                        continue
                    m_dmg = re_dmg.search(line)
                    if m_dmg:
                        atk, tgt, val, details = m_dmg.groups()
                        atk, tgt, val = atk.strip(), tgt.strip(), int(val)
                        if " : " in atk:
                            atk = atk.split(" : ")[-1]
                        if " : " in tgt:
                            tgt = tgt.split(" : ")[-1]
                        if atk in stats_pc:
                            stats_pc[atk]["dmg_tot"] += val
                            if (atk == "Rayna Ralien" or atk ==
                                    "Selkie Smoothhand") and \
                                    details and "Divine" in details:
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
                        if " : " in kil:
                            kil = kil.split(" : ")[-1]
                        if kil in stats_pc:
                            stats_pc[kil]["kills"] += 1
        except FileNotFoundError:
            errors.append(file_path)
            continue
        else:
            files_processed += 1

    return files_processed, errors, stats_pc, stats_m, extra_stats


class NWNAnalyzerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NWN Combat Log Analyzer")
        self.geometry("1000x650")
        self.cfg = load_config()
        self.selected_files = []

        self._build_top_bar()
        self._build_char_box()
        self._build_tabs()

    def _build_top_bar(self):
        frame = ttk.Frame(self)
        frame.pack(fill="x", padx=10, pady=8)

        ttk.Button(
            frame,
            text="Select Log File(s)",
            command=self.pick_files).pack(
            side="left")
        ttk.Button(
            frame,
            text="Use Default Folder",
            command=self.use_default_folder).pack(
            side="left",
            padx=6)
        ttk.Button(
            frame,
            text="Set Default Folder",
            command=self.set_default_folder).pack(
            side="left",
            padx=6)

        self.files_label = ttk.Label(
            frame, text="No files selected", foreground="gray")
        self.files_label.pack(side="left", padx=10)

        ttk.Button(
            frame,
            text="Analyze",
            command=self.run_analysis).pack(
            side="right")

    def _build_char_box(self):
        frame = ttk.LabelFrame(self, text="Player / Toon Roster")
        frame.pack(fill="x", padx=10, pady=4)

        list_frame = ttk.Frame(frame)
        list_frame.pack(side="left", fill="both", expand=True, padx=6, pady=6)

        self.char_listbox = tk.Listbox(
            list_frame,
            height=5,
            selectmode="extended")
        self.char_listbox.pack(side="left", fill="both", expand=True)
        vsb = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self.char_listbox.yview)
        self.char_listbox.configure(yscrollcommand=vsb.set)
        vsb.pack(side="left", fill="y")

        for name in self.cfg.get("characters", DEFAULT_CHARACTERS):
            self.char_listbox.insert("end", name)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(side="left", fill="y", padx=6, pady=6)

        self.char_entry = ttk.Entry(btn_frame, width=22)
        self.char_entry.pack(pady=(0, 4))
        self.char_entry.bind("<Return>", lambda e: self.add_character())

        ttk.Button(btn_frame, text="Add",
                   command=self.add_character).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Remove Selected",
                   command=self.remove_character).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Save as Default Roster",
                   command=self.save_default_roster).pack(
                       fill="x", pady=(10, 2))
        ttk.Button(btn_frame, text="Reset to Built-in Default",
                   command=self.reset_default_roster).pack(fill="x", pady=2)

    def add_character(self):
        name = self.char_entry.get().strip()
        if name:
            self.char_listbox.insert("end", name)
            self.char_entry.delete(0, "end")

    def remove_character(self):
        for idx in reversed(self.char_listbox.curselection()):
            self.char_listbox.delete(idx)

    def get_characters(self):
        return list(self.char_listbox.get(0, "end"))

    def save_default_roster(self):
        characters = self.get_characters()
        if not characters:
            messagebox.showwarning("Empty roster",
                                   "Add at least one character first.")
            return
        self.cfg["characters"] = characters
        save_config(self.cfg)
        messagebox.showinfo("Saved",
                            "Default roster updated ({} character(s))."
                            .format(len(characters)))

    def reset_default_roster(self):
        self.char_listbox.delete(0, "end")
        for name in DEFAULT_CHARACTERS:
            self.char_listbox.insert("end", name)

    def _build_tabs(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=6)

        self.tree_char = self._make_tab(
            "Character Stats", [
                "Character", "Kills", "Total Damage", "Avg/Hit"])
        self.tree_mon = self._make_tab(
            "Monster Stats", [
                "Monster", "Max AB", "AC Range", "Avg Dmg"])
        self.tree_saves = self._make_tab(
            "Saving Throws", [
                "Name", "Category", "Check", "Count",
                "Roll Range", "DC Range", "Avg Roll"])
        self.tree_mit = self._make_tab(
            "Mitigation & Threat",
            [
                "Name",
                "Category",
                "DR",
                "Immunity",
                "Concealed",
                "Avg Conceal %",
                "Threat Count",
                "Threat Max",
                "Threat Avg"])

    def _make_tab(self, title, columns):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=title)
        tree = ttk.Treeview(tab, columns=columns, show="headings")
        for c in columns:
            tree.heading(c, text=c)
            tree.column(c, width=120, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        return tree

    def pick_files(self):
        paths = filedialog.askopenfilenames(
            title="Select NWN log file(s)",
            initialdir=self.cfg.get("default_log_dir", os.getcwd()),
            filetypes=[("Log files", "*.txt *.log"), ("All files", "*.*")]
        )
        if paths:
            self.selected_files = list(paths)
            self.files_label.config(
                text="{} file(s) selected".format(
                    len(paths)))

    def use_default_folder(self):
        folder = self.cfg.get("default_log_dir", os.getcwd())
        found = sorted(
            glob.glob(
                os.path.join(
                    folder,
                    "nwclientLog*.txt")),
            key=lambda p: int(
                re.search(
                    r"(\d+)",
                    os.path.basename(p)).group(1)) if re.search(
                        r"(\d+)",
                os.path.basename(p)) else 0)
        if not found:
            messagebox.showwarning(
                "No files found",
                "No 'nwclientLog*.txt' files found in:\n" +
                folder)
            return
        self.selected_files = found
        self.files_label.config(
            text="{} file(s) from default folder".format(
                len(found)))

    def set_default_folder(self):
        folder = filedialog.askdirectory(title="Select default log folder")
        if folder:
            self.cfg["default_log_dir"] = folder
            save_config(self.cfg)
            messagebox.showinfo(
                "Saved", "Default log folder updated to:\n" + folder)

    def run_analysis(self):
        if not self.selected_files:
            messagebox.showwarning(
                "No files",
                "Please select log file(s) or use the default folder.")
            return
        characters = self.get_characters()
        if not characters:
            messagebox.showwarning(
                "No characters", "Please add at least one character name.")
            return

        (files_processed, errors, stats_pc, stats_m,
         extra_stats) = analyze_nwn_log(
            self.selected_files, characters)
        if errors:
            messagebox.showwarning(
                "Missing files",
                "Could not find:\n" +
                "\n".join(errors))
        if files_processed == 0:
            messagebox.showerror("Error", "No log files could be processed.")
            return

        self._fill_character_tab(stats_pc, characters)
        self._fill_monster_tab(stats_m, characters)
        self._fill_saves_tab(extra_stats, characters)
        self._fill_mitigation_tab(extra_stats, characters)
        messagebox.showinfo(
            "Done",
            "Processed {} file(s) successfully.".format(files_processed))

    def _clear_tree(self, tree):
        for row in tree.get_children():
            tree.delete(row)

    def _fill_character_tab(self, stats_pc, characters):
        self._clear_tree(self.tree_char)
        for p in characters:
            d = stats_pc[p]
            avg = d["dmg_tot"] / d["hits_count"] if d["hits_count"] > 0 else 0
            self.tree_char.insert(
                "", "end", values=(
                    p, d["kills"], d["dmg_tot"], round(
                        avg, 2)))

    def _fill_monster_tab(self, stats_m, characters):
        self._clear_tree(self.tree_mon)
        for m, d in sorted(stats_m.items()):
            if m in characters or m in ["Someone", "Object", ""]:
                continue
            max_ab = max(d["ab"]) if d["ab"] else 0
            hi_miss = max(d["misses_ac"]) + 1 if d["misses_ac"] else "?"
            lo_hit = min(d["hits_ac"]) if d["hits_ac"] else "?"
            avg_m = d["dmg_val"] / d["dmg_count"] if d["dmg_count"] > 0 else 0
            self.tree_mon.insert("", "end", values=(
                m, max_ab, "{} - {}".format(hi_miss, lo_hit), round(avg_m, 2)))

    def _fill_saves_tab(self, extra_stats, characters):
        self._clear_tree(self.tree_saves)
        for name, d in sorted(extra_stats.items()):
            if name in ["Someone", "Object", ""]:
                continue
            category = "Character" if name in characters else "Monster"
            for check_key, res in sorted(d["checks"].items()):
                totals = res["totals"]
                if not totals:
                    continue
                dcs = res["dcs"]
                self.tree_saves.insert("", "end", values=(
                    name, category, check_key, len(totals),
                    "{} - {}".format(min(totals), max(totals)),
                    "{} - {}".format(min(dcs), max(dcs)),
                    round(sum(totals) / len(totals), 2)
                ))

    def _fill_mitigation_tab(self, extra_stats, characters):
        self._clear_tree(self.tree_mit)
        for name, d in sorted(extra_stats.items()):
            if name in ["Someone", "Object", ""]:
                continue
            has_data = (d["dr_absorbed"] or d["immunity_absorbed"]
                        or d["concealed_against"] or d["threat_rolls"])
            if not has_data:
                continue
            category = "Character" if name in characters else "Monster"
            avg_pct = (sum(d["concealment_pcts"]) /
                       len(d["concealment_pcts"])) \
                if d["concealment_pcts"] else 0
            tr = d["threat_rolls"]
            self.tree_mit.insert(
                "",
                "end",
                values=(
                    name,
                    category,
                    d["dr_absorbed"],
                    d["immunity_absorbed"],
                    d["concealed_against"],
                    round(
                        avg_pct,
                        1),
                    len(tr),
                    max(tr) if tr else 0,
                    round(
                        sum(tr) /
                        len(tr),
                        2) if tr else 0))


if __name__ == "__main__":
    _fix_windows_dpi_scaling()
    app = NWNAnalyzerApp()
    app.mainloop()
