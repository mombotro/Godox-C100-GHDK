#!/usr/bin/env python3
"""Desktop GUI for the C100 firmware tool."""
from __future__ import annotations

import argparse
import contextlib
import io
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import c100


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("C100 firmware")
        self.minsize(720, 600)
        self.geometry("780x680")
        self._q: queue.Queue[tuple[str, bool]] = queue.Queue()
        self._busy = False
        self._test_for = tk.StringVar(value="none")
        self._volume = tk.IntVar(value=100)
        self._vol_label = tk.StringVar(value="100%")
        self._slot_vars = [tk.StringVar() for _ in c100.SLOTS]
        self._slot_mute = [tk.BooleanVar() for _ in c100.SLOTS]
        self._slot_meow = [tk.BooleanVar() for _ in c100.SLOTS]
        self._status = tk.StringVar(value="starting…")
        self._build()
        self.refresh_status()
        self.after(200, self._drain)

    def _build(self) -> None:
        pad = {"padx": 10, "pady": 6}
        root = ttk.Frame(self, padding=10)
        root.pack(fill=tk.BOTH, expand=True)

        ttk.Label(root, textvariable=self._status).pack(anchor=tk.W)
        ttk.Button(root, text="Refresh", command=self.refresh_status).pack(anchor=tk.W, pady=(0, 8))

        fw = ttk.LabelFrame(root, text="Firmware", padding=8)
        fw.pack(fill=tk.X, **pad)
        row = ttk.Frame(fw)
        row.pack(fill=tk.X)
        ttk.Button(row, text="Save stock firmware…", command=self.dump_vault).pack(side=tk.LEFT, padx=2)
        ttk.Button(row, text="Save stock from card…", command=self.dump_card).pack(side=tk.LEFT, padx=2)

        card = ttk.LabelFrame(root, text="Write to card (keeps RESTORE)", padding=8)
        card.pack(fill=tk.X, **pad)
        row = ttk.Frame(card)
        row.pack(fill=tk.X)
        ttk.Button(row, text="Write to card", command=self.write_card).pack(side=tk.LEFT, padx=2)
        ttk.Button(row, text="Save firmware…", command=self.build_sounds).pack(side=tk.LEFT, padx=2)
        ttk.Button(row, text="Restore stock", command=lambda: self.stage("stock")).pack(side=tk.LEFT, padx=2)

        snd = ttk.LabelFrame(root, text="Sounds (11.025 kHz; blank = keep stock)", padding=8)
        snd.pack(fill=tk.X, **pad)
        ttk.Label(
            snd,
            text="TEST.WAV is unused. Point shutter or power-on at it (rebuilt as 16-bit, 1.06 s). Put the long clip on slot 5 or that row.",
        ).pack(anchor=tk.W)
        tf = ttk.Frame(snd)
        tf.pack(fill=tk.X, pady=(2, 6))
        ttk.Label(tf, text="Use TEST slot for:").pack(side=tk.LEFT)
        ttk.Radiobutton(tf, text="Nothing", variable=self._test_for, value="none").pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(tf, text="Shutter (1.06 s, 16-bit)", variable=self._test_for, value="shutter").pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(tf, text="Power on (1.06 s, 16-bit)", variable=self._test_for, value="poweron").pack(side=tk.LEFT, padx=4)
        vr = ttk.Frame(snd)
        vr.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(vr, text="Volume").pack(side=tk.LEFT)
        ttk.Scale(
            vr,
            from_=25,
            to=200,
            orient=tk.HORIZONTAL,
            variable=self._volume,
            command=self._on_volume,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        ttk.Label(vr, textvariable=self._vol_label, width=5).pack(side=tk.LEFT)
        for i, slot in enumerate(c100.SLOTS):
            r = ttk.Frame(snd)
            r.pack(fill=tk.X, pady=2)
            ttk.Label(r, width=36, text=f"{slot['n']}  {slot['hint']}").pack(side=tk.LEFT)
            ttk.Entry(r, textvariable=self._slot_vars[i]).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
            ttk.Button(r, text="WAV…", width=6, command=lambda i=i: self.pick_wav(i)).pack(side=tk.LEFT)
            ttk.Checkbutton(r, text="Mute", variable=self._slot_mute[i], command=lambda i=i: self._exclusive(i, "mute")).pack(side=tk.LEFT, padx=4)
            ttk.Checkbutton(r, text="Meow", variable=self._slot_meow[i], command=lambda i=i: self._exclusive(i, "meow")).pack(side=tk.LEFT)
        row = ttk.Frame(snd)
        row.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(row, text="Mute all", command=self.mute_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(row, text="Meow all", command=self.meow_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(row, text="Clear slots", command=self.clear_slots).pack(side=tk.LEFT, padx=2)

        logf = ttk.LabelFrame(root, text="Log", padding=6)
        logf.pack(fill=tk.BOTH, expand=True, **pad)
        self.log = tk.Text(logf, height=10, wrap=tk.WORD, state=tk.DISABLED)
        sy = ttk.Scrollbar(logf, command=self.log.yview)
        self.log.configure(yscrollcommand=sy.set)
        self.log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sy.pack(side=tk.RIGHT, fill=tk.Y)

    def log_line(self, text: str) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, text.rstrip() + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def refresh_status(self) -> None:
        try:
            c100.vault_bytes()
            vault = "vault ok"
        except SystemExit as e:
            vault = f"vault: {e}"
        card = c100.find_card()
        if card is None:
            card_s = "card not mounted"
        else:
            restore = card / "RESTORE_ORIGINAL.bin"
            if restore.is_file() and c100.sha256(restore) == c100.EXPECTED_ORIG:
                rst = "RESTORE ok"
            elif restore.is_file():
                rst = "RESTORE HASH MISMATCH"
            else:
                rst = "RESTORE missing"
            up = "upgrade present" if (card / "gp_cardvr_upgrade.bin").is_file() else "no upgrade file"
            card_s = f"{card.name} · {rst} · {up}"
        self._status.set(f"{vault}  ·  {card_s}")

    def _on_volume(self, _value: str | None = None) -> None:
        self._vol_label.set(f"{int(self._volume.get())}%")

    def pick_wav(self, i: int) -> None:
        path = filedialog.askopenfilename(
            title=f"WAV for slot {i + 1}",
            filetypes=[("WAV", "*.wav"), ("All", "*.*")],
        )
        if path:
            self._slot_vars[i].set(path)
            self._slot_mute[i].set(False)
            self._slot_meow[i].set(False)

    def _exclusive(self, i: int, which: str) -> None:
        if which == "mute" and self._slot_mute[i].get():
            self._slot_meow[i].set(False)
        elif which == "meow" and self._slot_meow[i].get():
            self._slot_mute[i].set(False)

    def mute_all(self) -> None:
        for i in range(len(c100.SLOTS)):
            self._slot_mute[i].set(True)
            self._slot_meow[i].set(False)

    def meow_all(self) -> None:
        for i in range(len(c100.SLOTS)):
            self._slot_meow[i].set(True)
            self._slot_mute[i].set(False)

    def clear_slots(self) -> None:
        for i in range(len(c100.SLOTS)):
            self._slot_vars[i].set("")
            self._slot_mute[i].set(False)
            self._slot_meow[i].set(False)

    def _work(self, fn, *, ok_msg: str = "done") -> None:
        if self._busy:
            messagebox.showinfo("C100", "Wait for the current job to finish.")
            return
        self._busy = True

        def run() -> None:
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                    fn()
                self._q.put((buf.getvalue() + ("" if buf.getvalue().endswith("\n") else "\n") + ok_msg + "\n", True))
            except SystemExit as e:
                msg = buf.getvalue()
                if e.args:
                    msg += str(e.args[0]) + "\n"
                self._q.put((msg or "failed\n", False))
            except Exception as e:
                self._q.put((buf.getvalue() + f"{type(e).__name__}: {e}\n", False))

        threading.Thread(target=run, daemon=True).start()

    def _drain(self) -> None:
        try:
            while True:
                text, ok = self._q.get_nowait()
                if text.strip():
                    self.log_line(text.rstrip())
                if not ok:
                    messagebox.showerror("C100", text.strip() or "failed")
                self._busy = False
                self.refresh_status()
        except queue.Empty:
            pass
        self.after(200, self._drain)

    def dump_vault(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save stock firmware",
            defaultextension=".bin",
            initialfile="gp_cardvr_upgrade.ORIGINAL.bin",
        )
        if not path:
            return
        self._work(lambda: c100.cmd_dump(argparse.Namespace(out=path, from_card=False)))

    def dump_card(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save stock firmware from card",
            defaultextension=".bin",
            initialfile="gp_cardvr_upgrade.ORIGINAL.bin",
        )
        if not path:
            return
        self._work(lambda: c100.cmd_dump(argparse.Namespace(out=path, from_card=True)))

    def stage(self, image: str) -> None:
        if not messagebox.askokcancel("Write to card", f"Write {image} firmware to the card?"):
            return
        self._work(lambda: c100.cmd_stage(argparse.Namespace(image=image, keep=False)))

    def _sound_reps(self) -> dict[int, Path | str]:
        reps: dict[int, Path | str] = {}
        for i, slot in enumerate(c100.SLOTS):
            p = self._slot_vars[i].get().strip()
            if p:
                reps[slot["n"]] = Path(p)
            elif self._slot_mute[i].get():
                reps[slot["n"]] = "mute"
            elif self._slot_meow[i].get():
                reps[slot["n"]] = "meow"
        return reps

    def _label(self) -> str:
        bits = []
        tf = self._test_for.get()
        if tf == "shutter":
            bits.append("TESTshutter")
        elif tf == "poweron":
            bits.append("TESTpoweron")
        vol = int(self._volume.get())
        if vol != 100:
            bits.append(f"vol{vol}")
        reps = self._sound_reps()
        if reps:
            if all(v == "mute" for v in reps.values()) and len(reps) == 5:
                bits.append("MUTE")
            elif all(v == "meow" for v in reps.values()) and len(reps) == 5:
                bits.append("MEOW")
            else:
                bits.append("sounds")
        return "+".join(bits) or "firmware"

    def build_sounds(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save firmware",
            defaultextension=".bin",
            initialfile="gp_cardvr_upgrade.SOUNDS.bin",
        )
        if not path:
            return
        reps = self._sound_reps()
        test_for = self._test_for.get()
        test_for = None if test_for == "none" else test_for
        volume = c100.parse_volume(self._volume.get())

        def go() -> None:
            if not reps and not test_for:
                raise SystemExit("pick a WAV / Mute / Meow / TEST slot")
            data = c100.compose_firmware(reps=reps or None, test_for=test_for, volume=volume)
            Path(path).write_bytes(data)
            print("wrote", path)

        self._work(go)

    def write_card(self) -> None:
        label = self._label()
        if not messagebox.askokcancel("Write to card", f"Write {label} firmware to the card?"):
            return
        reps = self._sound_reps()
        test_for = self._test_for.get()
        test_for = None if test_for == "none" else test_for
        volume = c100.parse_volume(self._volume.get())

        def go() -> None:
            if not reps and not test_for:
                raise SystemExit("pick a WAV / Mute / Meow / TEST slot")
            data = c100.compose_firmware(reps=reps or None, test_for=test_for, volume=volume)
            c100.stage_image(data, label, eject=True)

        self._work(go)


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
