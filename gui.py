import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from preprocessing import tokenize, compute_soundex, edit_distance
from indexing import DocumentIndex
from search_core import SearchEngineCore

class AppGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("WSM Search Engine - All Slide Modules Implemented")
        self.root.geometry("1020x720")

        self.index = DocumentIndex()
        self.core = SearchEngineCore(self.index)
        self.current_q_tokens = []

        self._build_widgets()
        self._auto_load_default_folder()

    def _build_widgets(self):
        # Top Path Bar
        top_bar = tk.Frame(self.root, padx=10, pady=8)
        top_bar.pack(fill=tk.X)

        self.btn_folder = tk.Button(top_bar, text="📁 Choose Documents Directory", command=self.load_folder_dialog, bg="#eaeaea", padx=8)
        self.btn_folder.pack(side=tk.LEFT)

        self.lbl_status = tk.Label(top_bar, text="Status: Ready", fg="gray")
        self.lbl_status.pack(side=tk.LEFT, padx=10)

        # Search Controls
        search_bar = tk.Frame(self.root, padx=10, pady=5)
        search_bar.pack(fill=tk.X)

        tk.Label(search_bar, text="Query:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(0, 5))

        self.entry_query = tk.Entry(search_bar, font=("Arial", 11))
        self.entry_query.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.entry_query.bind("<Return>", lambda e: self.on_search())

        self.combo_model = ttk.Combobox(
            search_bar,
            values=[
                "Vector Space (Cosine)", 
                "Boolean Model", 
                "Exact Phrase Match", 
                "Proximity Match (/k)", 
                "Zone Scoring (Title/Body)", 
                "Wildcard Search", 
                "Soundex (Phonetic)"
            ],
            state="readonly",
            width=24
        )
        self.combo_model.current(0)
        self.combo_model.pack(side=tk.LEFT, padx=5)

        self.btn_search = tk.Button(search_bar, text="🔍 Search", command=self.on_search, bg="#0066cc", fg="white", font=("Arial", 9, "bold"), padx=12)
        self.btn_search.pack(side=tk.LEFT, padx=5)

        # Slide Specific Tool Strip (Lecture 3, 5, 8, 9)
        tool_bar = tk.Frame(self.root, padx=10, pady=4, bg="#f5f5f5")
        tool_bar.pack(fill=tk.X)

        self.btn_rocchio = tk.Button(tool_bar, text="⚡ Rocchio RF", command=self.on_rocchio, bg="#28a745", fg="white", font=("Arial", 8, "bold"))
        self.btn_rocchio.pack(side=tk.LEFT, padx=4)

        self.btn_prf = tk.Button(tool_bar, text="🚀 Pseudo RF", command=self.on_pseudo_rf, bg="#17a2b8", fg="white", font=("Arial", 8, "bold"))
        self.btn_prf.pack(side=tk.LEFT, padx=4)

        self.btn_spell = tk.Button(tool_bar, text="💡 Did you mean? (Spell Check)", command=self.on_spellcheck, font=("Arial", 8))
        self.btn_spell.pack(side=tk.LEFT, padx=4)

        self.btn_compress = tk.Button(tool_bar, text="📦 Test Gap Compression (VB/Gamma)", command=self.on_test_compression, font=("Arial", 8))
        self.btn_compress.pack(side=tk.LEFT, padx=4)

        # Central Paned Display
        paned = tk.PanedWindow(self.root, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        # Result Table with KWIC Snippets (Lecture 8, Slide 323)
        res_frame = tk.LabelFrame(paned, text="Search Results", padx=5, pady=5)
        paned.add(res_frame, height=250)

        cols = ("Rank", "Filename", "Score", "KWIC Snippet")
        self.tree = ttk.Treeview(res_frame, columns=cols, show='headings', selectmode="browse")
        self.tree.heading("Rank", text="Rank")
        self.tree.heading("Filename", text="Document")
        self.tree.heading("Score", text="Relevance Score")
        self.tree.heading("KWIC Snippet", text="Dynamic Snippet (KWIC)")

        self.tree.column("Rank", width=50, anchor="center")
        self.tree.column("Filename", width=200)
        self.tree.column("Score", width=110, anchor="e")
        self.tree.column("KWIC Snippet", width=620)

        t_scroll = ttk.Scrollbar(res_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=t_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        t_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self.on_doc_select)

        # Document Content Viewer
        preview_frame = tk.LabelFrame(paned, text="Response Box (Document Content)", padx=5, pady=5)
        paned.add(preview_frame)

        self.txt_preview = tk.Text(preview_frame, wrap=tk.WORD, font=("Consolas", 10))
        p_scroll = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self.txt_preview.yview)
        self.txt_preview.configure(yscrollcommand=p_scroll.set)
        self.txt_preview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        p_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _auto_load_default_folder(self):
        default_folder = os.path.join(os.path.dirname(__file__), "documents_data")
        if os.path.exists(default_folder):
            count = self.index.build_from_folder(default_folder)
            if count > 0:
                self.lbl_status.config(text=f"Loaded {count} documents from 'documents_data/'", fg="green")

    def load_folder_dialog(self):
        folder = filedialog.askdirectory(title="Select Folder with Documents")
        if folder:
            count = self.index.build_from_folder(folder)
            if count == 0:
                messagebox.showwarning("Warning", "No .txt files found in selected directory.")
                self.lbl_status.config(text="No .txt documents found", fg="red")
            else:
                self.lbl_status.config(text=f"Loaded {count} documents successfully.", fg="green")
                self.tree.delete(*self.tree.get_children())
                self.txt_preview.delete("1.0", tk.END)

    def on_search(self):
        if self.index.total_docs == 0:
            messagebox.showinfo("Notice", "Please select a documents folder first.")
            return

        q = self.entry_query.get().strip()
        if not q:
            return

        mode = self.combo_model.get()
        self.current_q_tokens = tokenize(q, remove_stops=True)

        if mode == "Boolean Model":
            results = self.core.search_boolean(q)
        elif mode == "Exact Phrase Match":
            results = self.core.search_phrase(q)
        elif mode == "Proximity Match (/k)":
            parts = q.split()
            if len(parts) >= 2:
                results = self.core.search_proximity(parts[0], parts[1], k=3)
            else:
                results = []
        elif mode == "Zone Scoring (Title/Body)":
            term = self.current_q_tokens[0] if self.current_q_tokens else q
            results = self.core.search_zone(term)
        elif mode == "Wildcard Search":
            terms = self.core.resolve_wildcard(q)
            docs = set()
            for t in terms:
                docs.update(self.index.positional_index[t].keys())
            results = [(self.index.id_to_doc[d], 1.0) for d in docs]
        elif mode == "Soundex (Phonetic)":
            code = compute_soundex(q.split()[0])
            terms = self.index.soundex_index.get(code, set())
            docs = set()
            for t in terms:
                docs.update(self.index.positional_index[t].keys())
            results = [(self.index.id_to_doc[d], 1.0) for d in docs]
        else:
            results = self.core.search_vsm(self.current_q_tokens)

        self._display_results(results)

    def _display_results(self, results):
        self.tree.delete(*self.tree.get_children())
        self.txt_preview.delete("1.0", tk.END)

        if not results:
            self.txt_preview.insert(tk.END, "No documents matched the search query.")
            return

        is_scored = self.combo_model.get() in ["Vector Space (Cosine)", "Zone Scoring (Title/Body)"]
        for idx, (doc, score) in enumerate(results, start=1):
            kwic = self.core.generate_kwic(doc, self.current_q_tokens)
            score_str = f"{score:.4f}" if is_scored else "MATCH"
            self.tree.insert("", tk.END, values=(idx, doc, score_str, kwic))

    def on_doc_select(self, event):
        items = self.tree.selection()
        if not items:
            return
        doc_name = self.tree.item(items[0])['values'][1]
        content = self.index.raw_docs.get(doc_name, "")
        self.txt_preview.delete("1.0", tk.END)
        self.txt_preview.insert(tk.END, f"=== File: {doc_name} ===\n\n{content}")

    def on_rocchio(self):
        items = self.tree.selection()
        if not items:
            messagebox.showinfo("Rocchio Info", "Select a document in the table to mark as 'Relevant' feedback.")
            return

        rel_doc = self.tree.item(items[0])['values'][1]
        all_retrieved = [self.tree.item(c)['values'][1] for c in self.tree.get_children()]
        non_rel = [d for d in all_retrieved if d != rel_doc]

        results = self.core.rocchio_feedback(self.current_q_tokens, [rel_doc], non_rel)
        self._display_results(results)
        messagebox.showinfo("Rocchio", f"Refined results using '{rel_doc}' as Relevant Feedback.")

    def on_pseudo_rf(self):
        if not self.current_q_tokens:
            return
        results = self.core.pseudo_relevance_feedback(self.current_q_tokens, top_k_docs=2)
        self._display_results(results)
        messagebox.showinfo("Pseudo RF", "Re-ranked results using top 2 documents automatically.")

    def on_spellcheck(self):
        q = self.entry_query.get().strip()
        tokens = tokenize(q, remove_stops=False)
        if not tokens:
            return

        corrections = []
        for t in tokens:
            if t not in self.index.vocabulary and self.index.vocabulary:
                closest = min(self.index.vocabulary, key=lambda w: edit_distance(t, w))
                corrections.append(closest)
            else:
                corrections.append(t)

        suggested = " ".join(corrections)
        if suggested != q:
            if messagebox.askyesno("Spell Correction", f"Did you mean: '{suggested}'?"):
                self.entry_query.delete(0, tk.END)
                self.entry_query.insert(0, suggested)
                self.on_search()
        else:
            messagebox.showinfo("Spell Correction", "No spelling correction suggestions needed.")

    def on_test_compression(self):
        doc_ids = sorted(list(self.index.id_to_doc.keys()))
        if not doc_ids:
            messagebox.showinfo("Compression Test", "Load documents first.")
            return

        # Calculate gaps (Lecture 5, Slide 184)
        gaps = [doc_ids[0]] + [doc_ids[i] - doc_ids[i-1] for i in range(1, len(doc_ids))]
        vb_bytes = DocumentIndex.vb_encode(gaps)
        decoded = DocumentIndex.vb_decode(vb_bytes)
        gamma_sample = DocumentIndex.gamma_encode_number(gaps[0] if gaps[0] > 0 else 1)

        msg = (
            f"Original Doc IDs: {doc_ids[:5]}...\n"
            f"Computed Gaps: {gaps[:5]}...\n"
            f"Variable Byte Encoded Bytes: {list(vb_bytes[:5])}...\n"
            f"VB Decoded Gaps: {decoded[:5]}...\n"
            f"Elias Gamma Sample (First Gap): {gamma_sample}"
        )
        messagebox.showinfo("Lecture 5 Compression", msg)