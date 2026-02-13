"""SDP GUI prototype.

UI-only desktop application for:
- Selecting an .slx file
- Entering natural-language prompts
- Previewing converted readable data
- Viewing model responses

Backend model and .slx extraction are intentionally left as placeholders.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class SDPApp(tk.Tk):
    """UI shell for future SDP workflow integration."""

    def __init__(self) -> None:
        super().__init__()
        self.title("SDP Assistant UI")
        self.geometry("1100x760")
        self.minsize(980, 680)
        self.configure(bg="#f3f4f6")

        self.selected_file = tk.StringVar(value="No .slx file selected")
        self.status_text = tk.StringVar(value="Ready (UI-only mode)")

        self._configure_style()
        self._build_layout()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("Card.TFrame", background="#ffffff", relief="flat")
        style.configure("PanelTitle.TLabel", font=("Segoe UI", 14, "bold"), background="#ffffff", foreground="#111827")
        style.configure("Muted.TLabel", font=("Segoe UI", 10), background="#ffffff", foreground="#6b7280")
        style.configure("Body.TLabel", font=("Segoe UI", 11), background="#ffffff", foreground="#1f2937")

        style.configure(
            "Primary.TButton",
            font=("Segoe UI", 11, "bold"),
            background="#3b82f6",
            foreground="#ffffff",
            borderwidth=0,
            focusthickness=3,
            focuscolor="#93c5fd",
            padding=(14, 8),
        )
        style.map("Primary.TButton", background=[("active", "#2563eb"), ("disabled", "#93c5fd")])

        style.configure(
            "Secondary.TButton",
            font=("Segoe UI", 10, "bold"),
            background="#e5e7eb",
            foreground="#111827",
            borderwidth=0,
            padding=(12, 8),
        )
        style.map("Secondary.TButton", background=[("active", "#d1d5db")])

    def _build_layout(self) -> None:
        container = ttk.Frame(self, padding=18, style="Card.TFrame")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        topbar = ttk.Frame(container, style="Card.TFrame")
        topbar.pack(fill="x", pady=(0, 14))

        ttk.Label(topbar, text="SDP Workflow Assistant", style="PanelTitle.TLabel").pack(side="left")
        ttk.Label(
            topbar,
            text="UI Prototype · Backend hooks to be implemented",
            style="Muted.TLabel",
        ).pack(side="right")

        # Main 2-column workspace
        workspace = ttk.Frame(container, style="Card.TFrame")
        workspace.pack(fill="both", expand=True)
        workspace.columnconfigure(0, weight=2)
        workspace.columnconfigure(1, weight=3)
        workspace.rowconfigure(0, weight=1)

        left = ttk.Frame(workspace, style="Card.TFrame", padding=14)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right = ttk.Frame(workspace, style="Card.TFrame", padding=14)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        self._build_left_panel(left)
        self._build_right_panel(right)
        self._build_footer(container)

    def _build_left_panel(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)

        ttk.Label(parent, text="1) Input Source", style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            parent,
            text="Choose an .slx model file and provide your NLP request.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 10))

        file_card = ttk.Frame(parent, style="Card.TFrame")
        file_card.grid(row=2, column=0, sticky="ew")
        file_card.columnconfigure(0, weight=1)

        ttk.Label(file_card, text="Selected file", style="Body.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(file_card, textvariable=self.selected_file, style="Muted.TLabel", wraplength=320).grid(
            row=1, column=0, sticky="w", pady=(2, 8)
        )

        ttk.Button(file_card, text="Browse .slx", style="Secondary.TButton", command=self._choose_file).grid(
            row=2, column=0, sticky="w"
        )

        ttk.Label(parent, text="Question / Prompt", style="Body.TLabel").grid(row=3, column=0, sticky="w", pady=(16, 6))
        self.prompt_text = tk.Text(
            parent,
            height=10,
            wrap="word",
            bd=1,
            relief="solid",
            font=("Segoe UI", 11),
            padx=10,
            pady=10,
        )
        self.prompt_text.grid(row=4, column=0, sticky="nsew")
        self.prompt_text.insert(
            "1.0",
            "Example: Summarize the control flow and list safety-critical subsystems.",
        )

        actions = ttk.Frame(parent, style="Card.TFrame")
        actions.grid(row=5, column=0, sticky="ew", pady=(14, 0))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)

        ttk.Button(actions, text="Convert .slx → Readable Data", style="Primary.TButton", command=self._convert_placeholder).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ttk.Button(actions, text="Ask AI", style="Primary.TButton", command=self._ask_placeholder).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )

    def _build_right_panel(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1)
        parent.rowconfigure(6, weight=1)

        ttk.Label(parent, text="2) Pipeline Output", style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            parent,
            text="Visual placeholders for future extraction and model integration.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 10))

        ttk.Label(parent, text="Readable data preview", style="Body.TLabel").grid(row=2, column=0, sticky="w", pady=(0, 6))
        self.readable_preview = tk.Text(
            parent,
            wrap="word",
            bd=1,
            relief="solid",
            font=("Consolas", 10),
            padx=10,
            pady=10,
        )
        self.readable_preview.grid(row=3, column=0, sticky="nsew")
        self.readable_preview.insert(
            "1.0",
            "[Placeholder] Converted architecture text from .slx will appear here...\n\n"
            "- Subsystem: ...\n"
            "- Blocks: ...\n"
            "- Signals: ...",
        )

        ttk.Label(parent, text="AI response", style="Body.TLabel").grid(row=4, column=0, sticky="w", pady=(12, 6))
        self.model_response = tk.Text(
            parent,
            wrap="word",
            bd=1,
            relief="solid",
            font=("Segoe UI", 11),
            padx=10,
            pady=10,
        )
        self.model_response.grid(row=6, column=0, sticky="nsew")
        self.model_response.insert(
            "1.0",
            "[Placeholder] Natural-language answer from the AI model will appear here.",
        )

    def _build_footer(self, parent: ttk.Frame) -> None:
        footer = ttk.Frame(parent, style="Card.TFrame")
        footer.pack(fill="x", pady=(10, 0))

        ttk.Label(footer, textvariable=self.status_text, style="Muted.TLabel").pack(side="left")
        ttk.Label(
            footer,
            text="Tip: This version is intentionally UI-only.",
            style="Muted.TLabel",
        ).pack(side="right")

    def _choose_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Simulink .slx file",
            filetypes=[("Simulink model", "*.slx"), ("All files", "*.*")],
        )
        if path:
            self.selected_file.set(path)
            self.status_text.set("File selected. Ready for conversion (placeholder).")

    def _convert_placeholder(self) -> None:
        self.status_text.set("Convert requested. Hook your SLX extraction script here.")
        messagebox.showinfo(
            "UI-only placeholder",
            "Conversion is not implemented yet.\n\n"
            "Connect this button to your .slx extraction script when ready.",
        )

    def _ask_placeholder(self) -> None:
        self.status_text.set("Model query requested. Hook your AI model here.")
        messagebox.showinfo(
            "UI-only placeholder",
            "AI querying is not implemented yet.\n\n"
            "Connect this button to your model client when ready.",
        )


def main() -> None:
    app = SDPApp()
    app.mainloop()


if __name__ == "__main__":
    main()
