import os
import re
import glob
import ctypes
import platform
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from nwn_log_parser import (
    analyze_nwn_log, load_config, save_config,
    DEFAULT_CHARACTERS, IGNORED_NAMES,
)


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


class NWNAnalyzerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NWN Combat Log Analyzer")
        self.geometry("1100x700")
        self.cfg = load_config()
        self.selected_files = []

        self._build_top_bar()
        self._build_char_box()
        self._build_tabs()

    # ---------- Top bar ----------
    def _build_top_bar(self):
        frame = ttk.Frame(self)
        frame.pack(fill="x", padx=10, pady=8)

        ttk.Button(
            frame, text="Select Log File(s)",
            command=self.pick_files
        ).pack(side="left")
        ttk.Button(
            frame, text="Use Default Folder",
            command=self.use_default_folder
        ).pack(side="left", padx=6)
        ttk.Button(
            frame, text="Set Default Folder",
            command=self.set_default_folder
        ).pack(side="left", padx=6)

        self.files_label = ttk.Label(
            frame, text="No files selected", foreground="gray")
        self.files_label.pack(side="left", padx=10)

        ttk.Button(
            frame, text="Analyze", command=self.run_analysis
        ).pack(side="right")

    # ---------- Character roster ----------
    def _build_char_box(self):
        frame = ttk.LabelFrame(self, text="Player / Toon Roster")
        frame.pack(fill="x", padx=10, pady=4)

        list_frame = ttk.Frame(frame)
        list_frame.pack(
            side="left", fill="both", expand=True, padx=6, pady=6
        )

        self.char_listbox = tk.Listbox(
            list_frame, height=5, selectmode="extended"
        )
        self.char_listbox.pack(side="left", fill="both", expand=True)
        vsb = ttk.Scrollbar(
            list_frame, orient="vertical",
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

        ttk.Button(
            btn_frame, text="Add",
            command=self.add_character).pack(fill="x", pady=2)
        ttk.Button(
            btn_frame, text="Remove Selected",
            command=self.remove_character).pack(fill="x", pady=2)
        ttk.Button(
            btn_frame, text="Save as Default Roster",
            command=self.save_default_roster).pack(
                fill="x", pady=(10, 2))
        ttk.Button(
            btn_frame, text="Reset to Built-in Default",
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
            messagebox.showwarning(
                "Empty roster", "Add at least one character first.")
            return
        self.cfg["characters"] = characters
        save_config(self.cfg)
        messagebox.showinfo(
            "Saved",
            "Default roster updated ({} character(s)).".format(
                len(characters)))

    def reset_default_roster(self):
        self.char_listbox.delete(0, "end")
        for name in DEFAULT_CHARACTERS:
            self.char_listbox.insert("end", name)

    # ---------- File selection ----------
    def pick_files(self):
        paths = filedialog.askopenfilenames(
            title="Select NWN log file(s)",
            initialdir=self.cfg.get("default_log_dir", os.getcwd()),
            filetypes=[("Log files", "*.txt *.log"), ("All files", "*.*")]
        )
        if paths:
            self.selected_files = list(paths)
            self.files_label.config(
                text="{} file(s) selected".format(len(paths)))

    def use_default_folder(self):
        folder = self.cfg.get("default_log_dir", os.getcwd())
        found = sorted(
            glob.glob(os.path.join(folder, "nwclientLog*.txt")),
            key=lambda p: int(re.search(r"(\d+)", os.path.basename(p))
                               .group(1))
            if re.search(r"(\d+)", os.path.basename(p)) else 0
        )
        if not found:
            messagebox.showwarning(
                "No files found",
                "No 'nwclientLog*.txt' files found in:\n" + folder)
            return
        self.selected_files = found
        self.files_label.config(
            text="{} file(s) from default folder".format(len(found)))

    def set_default_folder(self):
        folder = filedialog.askdirectory(title="Select default log folder")
        if folder:
            self.cfg["default_log_dir"] = folder
            save_config(self.cfg)
            messagebox.showinfo(
                "Saved", "Default log folder updated to:\n" + folder)

    def _build_tabs(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=6)

        self.tree_char = self._make_char_tab(
            "Character Stats",
            ["Kills", "Total Dmg", "Avg/Hit", "Detail"])
        self.tree_mon = self._make_tab(
            "Monster Stats",
            ["Monster", "Max AB", "AC Range", "Avg Dmg"])
        self.tree_saves = self._make_tab(
            "Saving Throws (All)",
            ["Name", "Category", "Check", "Count",
             "Roll Range", "DC Range", "Avg Roll"])
        self.tree_mit = self._make_tab(
            "Mitigation & Threat (All)",
            ["Name", "Category", "DR", "Immunity", "Concealed",
             "Avg Conceal %", "Threat Count", "Threat Max", "Threat Avg"])
        self.tree_dmg_types = self._make_tab(
            "Damage Types (All)",
            ["Name", "Category", "Damage Type",
             "Dealt", "Taken"])

    def _make_char_tab(self, title, columns):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=title)
        tree = ttk.Treeview(
            tab, columns=columns, show="tree headings")
        tree.heading("#0", text="Character / Detail")
        tree.column("#0", width=220, anchor="w")
        for c in columns:
            tree.heading(c, text=c)
            tree.column(c, width=110, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        return tree

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

    # ---------- Analysis ----------
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
         extra_stats) = analyze_nwn_log(self.selected_files, characters)

        if errors:
            messagebox.showwarning(
                "Missing files", "Could not find:\n" + "\n".join(errors))
        if files_processed == 0:
            messagebox.showerror("Error", "No log files could be processed.")
            return

        self._fill_character_tab(stats_pc, characters, extra_stats)
        self._fill_monster_tab(stats_m, characters)
        self._fill_saves_tab(extra_stats, characters)
        self._fill_mitigation_tab(extra_stats, characters)
        self._fill_damage_types_tab(extra_stats, characters)
        messagebox.showinfo(
            "Done", "Processed {} file(s) successfully.".format(
                files_processed))

    def _clear_tree(self, tree):
        for row in tree.get_children():
            tree.delete(row)
    
    def _fill_character_tab(self, stats_pc, characters, extra_stats):
        self._clear_tree(self.tree_char)
        for p in characters:
            d = stats_pc[p]
            avg = d["dmg_tot"] / d["hits_count"] if d["hits_count"] else 0
            parent = self.tree_char.insert(
                "", "end", text=p, values=(
                    d["kills"], d["dmg_tot"], round(avg, 2), ""))

            ex = extra_stats.get(p)
            if not ex:
                continue

            dealt = ex["dmg_dealt_types"]
            taken = ex["dmg_taken_types"]
            all_types = sorted(set(dealt.keys()) | set(taken.keys()))
            for dtype in all_types:
                self.tree_char.insert(
                    parent, "end",
                    text="  Damage: " + dtype,
                    values=("", "", "",
                            "Dealt {} / Taken {}".format(
                                dealt.get(dtype, 0),
                                taken.get(dtype, 0))))

            for check_key, res in sorted(ex["checks"].items()):
                totals = res["totals"]
                if not totals:
                    continue
                dcs = res["dcs"]
                self.tree_char.insert(
                    parent, "end",
                    text="  Save: " + check_key,
                    values=("", "", "",
                            "Roll {}-{} vs DC {}-{}".format(
                                min(totals), max(totals),
                                min(dcs), max(dcs))))

            if ex["dr_absorbed"] or ex["immunity_absorbed"] or \
                    ex["concealed_against"]:
                self.tree_char.insert(
                    parent, "end",
                    text="  Mitigation",
                    values=("", "", "",
                            "DR {} / Immune {} / Concealed {}x".format(
                                ex["dr_absorbed"], ex["immunity_absorbed"],
                                ex["concealed_against"])))

            if ex["threat_rolls"]:
                tr = ex["threat_rolls"]
                self.tree_char.insert(
                    parent, "end",
                    text="  Threat Rolls",
                    values=("", "", "",
                            "Count {} / Max {} / Avg {:.2f}".format(
                                len(tr), max(tr), sum(tr) / len(tr))))



    def _fill_monster_tab(self, stats_m, characters):
        self._clear_tree(self.tree_mon)
        for m, d in sorted(stats_m.items()):
            if m in characters or m in IGNORED_NAMES:
                continue
            max_ab = max(d["ab"]) if d["ab"] else 0
            hi_miss = max(d["misses_ac"]) + 1 if d["misses_ac"] else "?"
            lo_hit = min(d["hits_ac"]) if d["hits_ac"] else "?"
            avg_m = d["dmg_val"] / d["dmg_count"] if d["dmg_count"] else 0
            self.tree_mon.insert(
                "", "end",
                values=(m, max_ab, "{} - {}".format(hi_miss, lo_hit),
                         round(avg_m, 2)))

    def _fill_saves_tab(self, extra_stats, characters):
        self._clear_tree(self.tree_saves)
        for name, d in sorted(extra_stats.items()):
            if name in IGNORED_NAMES:
                continue
            category = "Character" if name in characters else "Monster"
            for check_key, res in sorted(d["checks"].items()):
                totals = res["totals"]
                if not totals:
                    continue
                dcs = res["dcs"]
                self.tree_saves.insert(
                    "", "end",
                    values=(
                        name, category, check_key, len(totals),
                        "{} - {}".format(min(totals), max(totals)),
                        "{} - {}".format(min(dcs), max(dcs)),
                        round(sum(totals) / len(totals), 2)))

    def _fill_mitigation_tab(self, extra_stats, characters):
        self._clear_tree(self.tree_mit)
        for name, d in sorted(extra_stats.items()):
            if name in IGNORED_NAMES:
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
                "", "end",
                values=(
                    name, category, d["dr_absorbed"],
                    d["immunity_absorbed"], d["concealed_against"],
                    round(avg_pct, 1), len(tr),
                    max(tr) if tr else 0,
                    round(sum(tr) / len(tr), 2) if tr else 0))

    def _fill_damage_types_tab(self, extra_stats, characters):
        self._clear_tree(self.tree_dmg_types)
        for name, d in sorted(extra_stats.items()):
            if name in IGNORED_NAMES:
                continue
            dealt = d["dmg_dealt_types"]
            taken = d["dmg_taken_types"]
            if not dealt and not taken:
                continue
            category = "Character" if name in characters else "Monster"
            all_types = sorted(set(dealt.keys()) | set(taken.keys()))
            for dtype in all_types:
                self.tree_dmg_types.insert(
                    "", "end",
                    values=(
                        name, category, dtype,
                        dealt.get(dtype, 0), taken.get(dtype, 0)))


if __name__ == "__main__":
    _fix_windows_dpi_scaling()
    app = NWNAnalyzerApp()
    app.mainloop()
