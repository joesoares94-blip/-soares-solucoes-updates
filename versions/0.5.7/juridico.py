"""Tkinter area for Cases and Papers inside Soares Soluções."""
from __future__ import annotations

import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import webbrowser

from juridico_core import Store, ResearchClient, export_word, import_manual, missing_manuals, read_assignment, run_work

NAVY = "#0F2747"
NAVY2 = "#1F4E79"
ACCENT = "#2F80FF"
BG = "#F4F6F8"
WHITE = "#FFFFFF"
TEXT = "#172B4D"
MUTED = "#667085"


class Workspace:
    def __init__(self, parent: tk.Widget, user: dict):
        self.parent = parent
        self.owner = str(user["id"])
        self.store = Store()
        self.current_id: str | None = None
        self.current_revision = 0
        self.file_name = ""
        self.busy = False
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.ids: list[str] = []
        self._build()
        self.reload()

    def _button(self, parent, text, command, primary=False):
        return tk.Button(parent, text=text, command=command, bg=NAVY2 if primary else WHITE,
                         fg=WHITE if primary else NAVY, activebackground=ACCENT if primary else BG,
                         bd=0, padx=14, pady=8, cursor="hand2", font=("Segoe UI", 10))

    def _build(self):
        bar = tk.Frame(self.parent, bg=BG)
        bar.pack(fill="x", padx=30, pady=(0, 12))
        tk.Label(bar, text="Cases e Papers · FACSUR", bg=BG, fg=MUTED,
                 font=("Segoe UI", 10)).pack(side="left")
        self.status = tk.StringVar(value="Novo trabalho ou selecione um projeto salvo.")
        tk.Label(bar, textvariable=self.status, bg=BG, fg=NAVY2,
                 font=("Segoe UI", 9)).pack(side="right")
        area = tk.PanedWindow(self.parent, orient="horizontal", bg=BG, sashwidth=5)
        area.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        left = tk.Frame(area, bg=WHITE, width=300, padx=14, pady=14)
        area.add(left, minsize=240)
        right = tk.Frame(area, bg=WHITE, padx=18, pady=14)
        area.add(right, minsize=520)

        tk.Label(left, text="Trabalhos", bg=WHITE, fg=TEXT, font=("Segoe UI", 13, "bold")).pack(anchor="w")
        self.projects = tk.Listbox(left, height=10, activestyle="none", selectbackground=NAVY2,
                                   relief="flat", font=("Segoe UI", 10))
        self.projects.pack(fill="both", expand=True, pady=8)
        self.projects.bind("<<ListboxSelect>>", self.open_selected)
        self._button(left, "Novo trabalho", self.new_project, True).pack(fill="x", pady=(5, 0))
        self._button(left, "Importar manuais FACSUR", self.setup_manuals).pack(fill="x", pady=(7, 0))

        form = tk.Frame(right, bg=WHITE)
        form.pack(fill="x")
        tk.Label(form, text="Título", bg=WHITE, fg=TEXT).grid(row=0, column=0, sticky="w")
        self.title = ttk.Entry(form)
        self.title.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 8))
        tk.Label(form, text="Tipo", bg=WHITE, fg=TEXT).grid(row=0, column=2, sticky="w", padx=(12, 0))
        self.kind = tk.StringVar(value="case")
        ttk.Combobox(form, textvariable=self.kind, values=("case", "paper"), state="readonly", width=12).grid(
            row=1, column=2, sticky="ew", padx=(12, 0), pady=(2, 8))
        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)
        tk.Label(form, text="Enunciado do professor", bg=WHITE, fg=TEXT).grid(row=2, column=0, columnspan=2, sticky="w")
        self.assignment = tk.Text(form, height=5, wrap="word", font=("Segoe UI", 10), relief="solid", bd=1)
        self.assignment.grid(row=3, column=0, columnspan=3, sticky="nsew", pady=(2, 8))
        actions = tk.Frame(form, bg=WHITE)
        actions.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        self._button(actions, "Importar proposta", self.import_file).pack(side="left")
        self._button(actions, "Salvar proposta", self.create_project, True).pack(side="left", padx=7)
        self.start_button = self._button(actions, "Iniciar especialistas", self.start)
        self.start_button.pack(side="left")

        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill="both", expand=True, pady=(5, 0))
        self.texts = {}
        for name in ("Documento", "Análise jurídica", "Conferência", "Fontes", "Versões"):
            page = tk.Frame(self.tabs, bg=WHITE)
            self.tabs.add(page, text=name)
            if name == "Versões":
                self.versions = tk.Listbox(page, selectbackground=NAVY2, relief="flat", font=("Segoe UI", 10))
                self.versions.pack(fill="both", expand=True, padx=5, pady=8)
                self._button(page, "Restaurar versão selecionada", self.restore).pack(anchor="e", pady=(0, 8))
            else:
                scroller = ttk.Scrollbar(page)
                scroller.pack(side="right", fill="y")
                content = tk.Text(page, wrap="word", undo=(name == "Documento"),
                                  font=("Segoe UI", 10), relief="flat", padx=8, pady=8,
                                  yscrollcommand=scroller.set)
                content.pack(fill="both", expand=True)
                scroller.configure(command=content.yview)
                self.texts[name] = content
                if name != "Documento":
                    content.configure(state="disabled")
                if name == "Fontes":
                    content.bind("<Double-Button-1>", self.open_source)
        footer = tk.Frame(right, bg=WHITE)
        footer.pack(fill="x", pady=(8, 0))
        self._button(footer, "Salvar revisão", self.save_revision).pack(side="left")
        self._button(footer, "Exportar Word", self.save_word).pack(side="left", padx=7)
        tk.Label(footer, text="Word preliminar; confira o modelo e a paginação.", bg=WHITE,
                 fg=MUTED, font=("Segoe UI", 9)).pack(side="left", padx=8)

    def set_text(self, name: str, text: str):
        widget = self.texts[name]
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        if name != "Documento":
            widget.configure(state="disabled")

    def open_source(self, event):
        line = event.widget.get("@%d,%d linestart" % (event.x, event.y), "@%d,%d lineend" % (event.x, event.y)).strip()
        if line.startswith(("https://", "http://")):
            webbrowser.open(line)

    def reload(self, select_id: str | None = None):
        rows = self.store.list(self.owner)
        self.ids = [row["id"] for row in rows]
        self.projects.delete(0, "end")
        for row in rows:
            self.projects.insert("end", f"{row['title']}  ·  {row['kind'].upper()}  ·  {row['stage']}")
        target = select_id or self.current_id
        if target in self.ids:
            index = self.ids.index(target)
            self.projects.selection_set(index)
            self.projects.see(index)
            self.show(target)

    def open_selected(self, _event=None):
        selection = self.projects.curselection()
        if selection and selection[0] < len(self.ids):
            self.show(self.ids[selection[0]])

    def show(self, work_id: str):
        work = self.store.get(self.owner, work_id)
        self.current_id = work_id
        self.current_revision = work["revision"]
        self.title.delete(0, "end")
        self.title.insert(0, work["title"])
        self.kind.set(work["kind"])
        self.assignment.delete("1.0", "end")
        self.assignment.insert("1.0", work["assignment"])
        self.file_name = work["file_name"] or ""
        self.set_text("Documento", work["draft"])
        self.set_text("Análise jurídica", work["analysis"] + ("\n\nREVISÃO JURÍDICA\n" + work["review"] if work["review"] else ""))
        quality = work["quality"]
        report = (f"{quality.get('word_count',0)} palavras · {quality.get('source_count',0)} fontes registradas\n"
                  "Auditoria formal; confira o conteúdo jurídico e os dados das fontes originais.\n\n")
        report += "\n".join(("✓ " if item["ok"] else "! ") + item["label"] for item in quality.get("items", []))
        if quality.get("untracked_links"):
            report += "\n\nLinks fora do registro:\n" + "\n".join(quality["untracked_links"])
        self.set_text("Conferência", report)
        self.set_text("Fontes", "Fontes registradas pela pesquisa; dê dois cliques no link para conferir o teor:\n\n" +
                      "\n\n".join(f"{s['title']}\n{s['url']}" for s in work["sources"]))
        self.versions.delete(0, "end")
        self.version_numbers = []
        for version in self.store.versions(self.owner, work_id):
            self.version_numbers.append(version["revision"])
            self.versions.insert("end", f"Revisão {version['revision']} · {version['origin']} · {version['created_at']}")
        self.status.set(f"{work['stage'].capitalize()} · revisão {work['revision']}" +
                        (f" · {work['error']}" if work["error"] else ""))

    def new_project(self):
        self.current_id = None
        self.file_name = ""
        self.title.delete(0, "end")
        self.assignment.delete("1.0", "end")
        self.kind.set("case")
        for name in self.texts:
            self.set_text(name, "")
        self.versions.delete(0, "end")
        self.projects.selection_clear(0, "end")
        self.status.set("Novo trabalho · importe ou cole o enunciado.")

    def import_file(self):
        filename = filedialog.askopenfilename(parent=self.parent, title="Proposta do professor",
                                              filetypes=[("Propostas", "*.pdf *.docx *.txt")])
        if not filename:
            return
        try:
            text = read_assignment(Path(filename)).strip()
            if len(text) < 60:
                raise ValueError("O arquivo não contém texto suficiente. Cole o enunciado manualmente.")
            self.assignment.delete("1.0", "end")
            self.assignment.insert("1.0", text)
            self.file_name = Path(filename).name
            self.status.set(f"Proposta importada: {self.file_name}")
        except Exception as exc:
            messagebox.showerror("Importar proposta", str(exc), parent=self.parent)

    def setup_manuals(self):
        for name, label in (("manual_case_paper.txt", "MANUALDECASEEPAPER.pdf"),
                            ("manuals_cases.txt", "Cases .pdf")):
            filename = filedialog.askopenfilename(parent=self.parent,
                title=f"Selecione {label}", filetypes=[("Manual PDF", "*.pdf")])
            if not filename:
                self.status.set("Importação dos manuais interrompida.")
                return
            try:
                import_manual(name, Path(filename))
            except Exception as exc:
                messagebox.showerror("Manual", str(exc), parent=self.parent)
                return
        self.status.set("Os dois manuais FACSUR estão disponíveis na base local.")

    def create_project(self):
        if self.current_id:
            messagebox.showinfo("Trabalho salvo", "Para criar outro, clique em Novo trabalho.", parent=self.parent)
            return
        try:
            work_id = self.store.create(self.owner, self.title.get(), self.kind.get(),
                                        self.assignment.get("1.0", "end"), self.file_name)
            self.reload(work_id)
            self.status.set("Proposta salva. Inicie os especialistas.")
        except Exception as exc:
            messagebox.showerror("Salvar proposta", str(exc), parent=self.parent)

    def start(self):
        if self.busy:
            return
        if not self.current_id:
            messagebox.showinfo("Proposta", "Salve a proposta antes de iniciar.", parent=self.parent)
            return
        if missing_manuals():
            messagebox.showinfo("Manuais FACSUR", "Importe os dois PDFs dos manuais antes de iniciar a pesquisa.", parent=self.parent)
            return
        work = self.store.get(self.owner, self.current_id)
        if work["stage"] == "concluido":
            messagebox.showinfo("Concluído", "O documento já está concluído. Edite e salve uma revisão.", parent=self.parent)
            return
        key = os.environ.get("OPENAI_API_KEY") or simpledialog.askstring(
            "Pesquisa jurídica", "Chave de API para esta sessão:", show="*", parent=self.parent)
        if not key:
            return
        self.busy = True
        self.start_button.configure(state="disabled")
        owner, work_id = self.owner, self.current_id

        def worker():
            try:
                run_work(self.store, owner, work_id, ResearchClient(key),
                         lambda status: self.events.put(("status", status)))
                self.events.put(("done", work_id))
            except Exception as exc:
                self.events.put(("error", str(exc)))
        threading.Thread(target=worker, daemon=True).start()
        self.parent.after(150, self.poll)

    def poll(self):
        if not self.start_button.winfo_exists():
            return
        try:
            while True:
                kind, message = self.events.get_nowait()
                if kind == "status":
                    self.status.set(message)
                else:
                    self.busy = False
                    self.start_button.configure(state="normal")
                    self.reload()
                    if kind == "error":
                        messagebox.showerror("Pesquisa jurídica", message, parent=self.parent)
                    else:
                        self.status.set("Documento concluído. Confira fontes, conteúdo e Word.")
        except queue.Empty:
            pass
        if self.busy and self.parent.winfo_exists():
            self.parent.after(150, self.poll)

    def save_revision(self):
        if not self.current_id or self.busy:
            return
        try:
            self.store.save_draft(self.owner, self.current_id,
                                  self.texts["Documento"].get("1.0", "end"), expected=self.current_revision)
            self.reload()
            self.status.set("Revisão salva no histórico.")
        except Exception as exc:
            messagebox.showerror("Salvar revisão", str(exc), parent=self.parent)

    def restore(self):
        selection = self.versions.curselection()
        if not self.current_id or not selection:
            return
        target = self.version_numbers[selection[0]]
        if not messagebox.askyesno("Restaurar versão", f"Restaurar a revisão {target} como nova revisão?",
                                   parent=self.parent):
            return
        try:
            self.store.restore(self.owner, self.current_id, target, self.current_revision)
            self.reload()
        except Exception as exc:
            messagebox.showerror("Restaurar", str(exc), parent=self.parent)

    def save_word(self):
        if not self.current_id:
            return
        work = self.store.get(self.owner, self.current_id)
        if not work["draft"]:
            messagebox.showinfo("Word", "A pesquisa ainda não produziu um documento.", parent=self.parent)
            return
        if self.texts["Documento"].get("1.0", "end").strip() != work["draft"].strip():
            messagebox.showwarning("Salvar revisão", "Salve a revisão antes de exportar o Word.", parent=self.parent)
            return
        target = filedialog.asksaveasfilename(parent=self.parent, defaultextension=".docx",
                                              initialfile=f"{work['title'][:70]}_{work['kind']}.docx",
                                              filetypes=[("Documento Word", "*.docx")])
        if target:
            try:
                export_word(work, Path(target))
                self.status.set("Word exportado. Confira a formatação no modelo da disciplina.")
            except Exception as exc:
                messagebox.showerror("Exportar Word", str(exc), parent=self.parent)


def mount(parent: tk.Widget, user: dict) -> Workspace:
    return Workspace(parent, user)
