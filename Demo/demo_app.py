"""
EventLog GUI Demo
=================

⚠️ PROTOTYPE ONLY - NOT PRODUCTION CODE ⚠️

This demo is for rapid UI/UX prototyping and testing layout ideas.
DO NOT copy code directly to the actual application!

Purpose:
- Test layout ideas quickly
- Validate UI/UX concepts
- Reference for visual design

Demonstrates:
- Login prompt with key file selection and password
- Main GUI with three tabs (Communications, Events, Personnel)
- Static demo data
- Tab switching
- TNR (time number) with "Nu" button
- Pre-filled fields

This is a standalone demo - no actual functionality, just UI mockup.

For actual app development, use proper architecture:
GUI (Views + Presenters) → Core (Business Logic) → DB (Adapters + Repositories)

See Demo/README.md for guidance on using this as a reference.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime


class LoginWindow:
    """Login window with key file selection and password input."""

    def __init__(self, on_login_success):
        self.on_login_success = on_login_success
        self.root = tk.Tk()
        self.root.title("EventLog - Inloggning")

        # Set minimum size to prevent clipping
        self.root.minsize(500, 350)
        
        self._create_widgets()
        
        # Center window after creating widgets (so size is calculated)
        self.root.update_idletasks()
        width = max(500, self.root.winfo_reqwidth())
        height = max(350, self.root.winfo_reqheight())
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _create_widgets(self):
        """Create login form widgets."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text="EventLog - Pluton Event Logger",
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 20))

        # Info text
        info_label = ttk.Label(main_frame, text="Välj nyckelfil och ange lösenord för att låsa upp databasen")
        info_label.pack(pady=(0, 20))

        # Key file section
        keyfile_frame = ttk.LabelFrame(main_frame, text="Nyckelfil", padding="10")
        keyfile_frame.pack(fill=tk.X, pady=(0, 10))

        self.keyfile_var = tk.StringVar(value="(Ingen fil vald)")
        keyfile_label = ttk.Label(keyfile_frame, textvariable=self.keyfile_var)
        keyfile_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        browse_button = ttk.Button(keyfile_frame, text="Bläddra...", command=self._browse_keyfile)
        browse_button.pack(side=tk.RIGHT)

        # Password section
        password_frame = ttk.LabelFrame(main_frame, text="Lösenord", padding="10")
        password_frame.pack(fill=tk.X, pady=(0, 20))

        self.password_var = tk.StringVar()
        password_entry = ttk.Entry(password_frame, textvariable=self.password_var, show="*", width=40)
        password_entry.pack(fill=tk.X)
        password_entry.bind("<Return>", lambda e: self._login())

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        login_button = ttk.Button(button_frame, text="Lås upp", command=self._login)
        login_button.pack(side=tk.RIGHT, padx=(5, 0))

        cancel_button = ttk.Button(button_frame, text="Avbryt", command=self.root.quit)
        cancel_button.pack(side=tk.RIGHT)

        # Focus password field
        password_entry.focus()

    def _browse_keyfile(self):
        """Open file browser for key file selection."""
        filename = filedialog.askopenfilename(
            title="Välj nyckelfil",
            filetypes=[
                ("Alla filer", "*.*"),
                ("Bildfiler", "*.jpg *.jpeg *.png *.gif"),
                ("Dokumentfiler", "*.pdf *.doc *.docx"),
            ]
        )
        if filename:
            self.keyfile_var.set(filename)

    def _login(self):
        """Handle login button click - accepts anything."""
        # In real app, would validate. Demo accepts anything.
        if self.password_var.get():
            self.root.destroy()
            self.on_login_success()
        else:
            messagebox.showwarning("Lösenord krävs", "Vänligen ange ett lösenord.")

    def run(self):
        """Start the login window."""
        self.root.mainloop()


class MainWindow:
    """Main application window with three tabs."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("EventLog - Pluton Event Logger")
        self.root.geometry("1200x700")

        # Center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (1200 // 2)
        y = (self.root.winfo_screenheight() // 2) - (700 // 2)
        self.root.geometry(f"1200x700+{x}+{y}")

        self._create_widgets()

    def _create_widgets(self):
        """Create main window widgets."""
        # Toolbar
        toolbar = ttk.Frame(self.root, relief=tk.RAISED, borderwidth=1)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        nollstall_button = tk.Button(toolbar, text="🗑️ Nollställ",
                                     bg="#ff4444", fg="white",
                                     font=("Arial", 10, "bold"),
                                     padx=10, pady=5)
        nollstall_button.pack(side=tk.LEFT, padx=5, pady=5)

        # Status bar
        status_bar = ttk.Frame(self.root, relief=tk.SUNKEN, borderwidth=1)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        status_label = ttk.Label(status_bar, text="Last log: Application started")
        status_label.pack(side=tk.LEFT, padx=5)

        operator_label = ttk.Label(status_bar, text="Operator: GC")
        operator_label.pack(side=tk.RIGHT, padx=5)

        # Notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create tabs
        self._create_communication_tab()
        self._create_events_tab()
        self._create_personnel_tab()

    @staticmethod
    def _get_current_tnr():
        """Get current time as TNR (DDHHMM format)."""
        now = datetime.now()
        return now.strftime("%d%H%M")

    def _create_communication_tab(self):
        """Create Communications tab with static demo data."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Kommunikation")

        # Split into form (top) and table (bottom)
        form_frame = ttk.LabelFrame(tab, text="Ny kommunikation", padding="10")
        form_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # Configure column weights for proper expansion
        form_frame.columnconfigure(1, weight=1)
        form_frame.columnconfigure(3, weight=1)

        # Form layout with proper alignment
        row = 0
        ttk.Label(form_frame, text="TNR:").grid(row=row, column=0, sticky=tk.W, padx=(5, 2), pady=2)

        # TNR entry with Nu button
        tnr_frame = ttk.Frame(form_frame)
        tnr_frame.grid(row=row, column=1, sticky=tk.W+tk.E, padx=(2, 5), pady=2)
        tnr_entry = ttk.Entry(tnr_frame)
        tnr_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        def fill_tnr():
            tnr_entry.delete(0, tk.END)
            tnr_entry.insert(0, self._get_current_tnr())

        ttk.Button(tnr_frame, text="Nu", width=5, command=fill_tnr).pack(side=tk.LEFT, padx=(5, 0))

        ttk.Label(form_frame, text="System:").grid(row=row, column=2, sticky=tk.W, padx=(15, 2), pady=2)
        # NOTE: These are EXAMPLE values for demo purposes only!
        # Real app needs: User-configurable system list from settings/config
        system_combo = ttk.Combobox(form_frame, values=["RA180", "RA146", "(Ingen)"])
        system_combo.grid(row=row, column=3, sticky=tk.W+tk.E, padx=(2, 5), pady=2)
        system_combo.set("RA180")

        row += 1
        ttk.Label(form_frame, text="Metod:").grid(row=row, column=0, sticky=tk.W, padx=(5, 2), pady=2)
        # NOTE: These are EXAMPLE values for demo purposes only!
        # Real app needs: User-configurable method list from settings/config
        method_combo = ttk.Combobox(form_frame, values=["Radio", "Telefon", "Data"])
        method_combo.grid(row=row, column=1, sticky=tk.W+tk.E, padx=(2, 5), pady=2)
        method_combo.set("Radio")

        ttk.Label(form_frame, text="Kanal:").grid(row=row, column=2, sticky=tk.W, padx=(15, 2), pady=2)
        # NOTE: These are EXAMPLE values for demo purposes only!
        # Real app needs: User-configurable channel list from settings/config
        channel_combo = ttk.Combobox(form_frame, values=["Company Net (Ch 5)", "Platoon 1 Net (Ch 7)"])
        channel_combo.grid(row=row, column=3, sticky=tk.W+tk.E, padx=(2, 5), pady=2)
        channel_combo.set("Company Net (Ch 5)")

        row += 1
        ttk.Label(form_frame, text="Från:").grid(row=row, column=0, sticky=tk.W, padx=(5, 2), pady=2)

        # Från field with callsign button
        fran_frame = ttk.Frame(form_frame)
        fran_frame.grid(row=row, column=1, sticky=tk.W+tk.E, padx=(2, 5), pady=2)
        fran_entry = ttk.Entry(fran_frame)
        fran_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        def fill_fran():
            fran_entry.delete(0, tk.END)
            fran_entry.insert(0, "AQ")

        ttk.Button(fran_frame, text="AQ", width=5, command=fill_fran).pack(side=tk.LEFT, padx=(5, 0))

        ttk.Label(form_frame, text="Till:").grid(row=row, column=2, sticky=tk.W, padx=(15, 2), pady=2)

        # Till field with callsign button
        till_frame = ttk.Frame(form_frame)
        till_frame.grid(row=row, column=3, sticky=tk.W+tk.E, padx=(2, 5), pady=2)
        till_entry = ttk.Entry(till_frame)
        till_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        def fill_till():
            till_entry.delete(0, tk.END)
            till_entry.insert(0, "AQ")

        ttk.Button(till_frame, text="AQ", width=5, command=fill_till).pack(side=tk.LEFT, padx=(5, 0))

        row += 1
        ttk.Label(form_frame, text="Meddelande:").grid(row=row, column=0, sticky=tk.NW, padx=(5, 2), pady=2)
        message_text = tk.Text(form_frame, height=3, width=1)  # width=1, let grid expand it
        message_text.grid(row=row, column=1, columnspan=3, sticky=tk.W+tk.E, padx=(2, 5), pady=2)

        row += 1
        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=row, column=0, columnspan=4, pady=10, sticky=tk.W)
        ttk.Button(button_frame, text="Spara").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Rensa").pack(side=tk.LEFT, padx=5)

        # Table
        table_frame = ttk.Frame(tab)
        table_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create treeview
        columns = ("time", "from", "to", "method", "message", "operator")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)

        tree.heading("time", text="TNR")
        tree.heading("from", text="Från")
        tree.heading("to", text="Till")
        tree.heading("method", text="Metod")
        tree.heading("message", text="Meddelande")
        tree.heading("operator", text="Operatör")

        tree.column("time", width=120)
        tree.column("from", width=100)
        tree.column("to", width=100)
        tree.column("method", width=150)
        tree.column("message", width=400)
        tree.column("operator", width=80)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Add demo data
        demo_data = [
            ("221430", "Company", "Pluton 2", "Radio - Company Net", "Pluton 2 rapporterar färdig med patrull", "GC"),
            ("221415", "Pluton 2", "Company", "Radio - Company Net", "Pluton 2 avgår till kontrollpunkt Alpha", "GC"),
            ("221400", "HQ", "Company", "Radio - Command Net", "Sitrep begärs kl 15:00", "GC"),
            ("221345", "Company", "Pluton 1", "Radio - Platoon 1 Net", "Förflytta till samlingspunkt Bravo", "AK"),
            ("221330", "Pluton 3", "Company", "Radio - Company Net", "I ställning vid checkpoint Charlie", "GC"),
        ]

        for row_data in demo_data:
            tree.insert("", tk.END, values=row_data)

    def _create_events_tab(self):
        """Create Events tab with static demo data."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Händelser")

        # Form
        form_frame = ttk.LabelFrame(tab, text="Ny händelse", padding="10")
        form_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # Configure column weights for proper expansion
        form_frame.columnconfigure(1, weight=1)
        form_frame.columnconfigure(3, weight=1)

        row = 0
        ttk.Label(form_frame, text="TNR:").grid(row=row, column=0, sticky=tk.W, padx=(5, 2), pady=2)

        # TNR entry with Nu button
        tnr_frame_events = ttk.Frame(form_frame)
        tnr_frame_events.grid(row=row, column=1, sticky=tk.W+tk.E, padx=(2, 5), pady=2)
        tnr_entry_events = ttk.Entry(tnr_frame_events)
        tnr_entry_events.pack(side=tk.LEFT, fill=tk.X, expand=True)

        def fill_tnr_events():
            tnr_entry_events.delete(0, tk.END)
            tnr_entry_events.insert(0, self._get_current_tnr())

        ttk.Button(tnr_frame_events, text="Nu", width=5, command=fill_tnr_events).pack(side=tk.LEFT, padx=(5, 0))

        ttk.Label(form_frame, text="Vem:").grid(row=row, column=2, sticky=tk.W, padx=(15, 2), pady=2)
        ttk.Entry(form_frame).grid(row=row, column=3, sticky=tk.W+tk.E, padx=(2, 5), pady=2)

        row += 1
        ttk.Label(form_frame, text="Prioritet:").grid(row=row, column=0, sticky=tk.W, padx=(5, 2), pady=2)
        priority_combo = ttk.Combobox(form_frame, values=["Låg", "Normal", "Hög", "Kritisk"])
        priority_combo.grid(row=row, column=1, sticky=tk.W+tk.E, padx=(2, 5), pady=2)
        priority_combo.set("Normal")

        ttk.Label(form_frame, text="Kategori:").grid(row=row, column=2, sticky=tk.W, padx=(15, 2), pady=2)
        category_combo = ttk.Combobox(form_frame, values=["Kontakt", "Förflyttning", "Observation", "Rapport"])
        category_combo.grid(row=row, column=3, sticky=tk.W+tk.E, padx=(2, 5), pady=2)
        category_combo.set("Observation")

        row += 1
        ttk.Label(form_frame, text="Beskrivning:").grid(row=row, column=0, sticky=tk.NW, padx=(5, 2), pady=2)
        desc_text = tk.Text(form_frame, height=3, width=1)  # width=1, let grid expand it
        desc_text.grid(row=row, column=1, columnspan=3, sticky=tk.W+tk.E, padx=(2, 5), pady=2)

        row += 1
        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=row, column=0, columnspan=4, pady=10, sticky=tk.W)
        ttk.Button(button_frame, text="Spara").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Lägg till rapport...").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Rensa").pack(side=tk.LEFT, padx=5)

        # Table
        table_frame = ttk.Frame(tab)
        table_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("time", "whom", "priority", "category", "description", "operator")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)

        tree.heading("time", text="TNR")
        tree.heading("whom", text="Vem")
        tree.heading("priority", text="Prioritet")
        tree.heading("category", text="Kategori")
        tree.heading("description", text="Händelse")
        tree.heading("operator", text="Operatör")

        tree.column("time", width=120)
        tree.column("whom", width=100)
        tree.column("priority", width=80)
        tree.column("category", width=100)
        tree.column("description", width=450)
        tree.column("operator", width=80)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Demo data
        demo_data = [
            ("221435", "Pluton 2", "Normal", "Observation", "Fientlig patrull | 14:30, Grid 12345678, 20 pers, Soldater", "GC"),
            ("221420", "Grupp 3", "Hög", "Kontakt", "Beskjutning från öster, inga skadade", "GC"),
            ("221405", "Pluton 1", "Normal", "Förflyttning", "Pluton 1 förflyttar till sektor Bravo", "AK"),
            ("221350", "Company", "Normal", "Rapport", "Sitrep skickad till HQ", "GC"),
            ("221340", "Pluton 3", "Låg", "Observation", "Civila fordon på väg 23", "GC"),
        ]

        for row_data in demo_data:
            tree.insert("", tk.END, values=row_data)

    def _create_personnel_tab(self):
        """Create Personnel tab with static demo data."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Personal")

        # Form
        form_frame = ttk.LabelFrame(tab, text="Ny personalpost", padding="10")
        form_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # Configure column weights for proper expansion
        form_frame.columnconfigure(1, weight=1)
        form_frame.columnconfigure(3, weight=1)

        row = 0
        ttk.Label(form_frame, text="Vem:").grid(row=row, column=0, sticky=tk.W, padx=(5, 2), pady=2)
        ttk.Entry(form_frame).grid(row=row, column=1, sticky=tk.W+tk.E, padx=(2, 5), pady=2)

        ttk.Label(form_frame, text="Status:").grid(row=row, column=2, sticky=tk.W, padx=(15, 2), pady=2)
        ttk.Entry(form_frame).grid(row=row, column=3, sticky=tk.W+tk.E, padx=(2, 5), pady=2)

        row += 1
        ttk.Label(form_frame, text="Plats:").grid(row=row, column=0, sticky=tk.W, padx=(5, 2), pady=2)
        ttk.Entry(form_frame).grid(row=row, column=1, sticky=tk.W+tk.E, padx=(2, 5), pady=2)

        ttk.Label(form_frame, text="Senaste kontakt:").grid(row=row, column=2, sticky=tk.W, padx=(15, 2), pady=2)
        ttk.Entry(form_frame).grid(row=row, column=3, sticky=tk.W+tk.E, padx=(2, 5), pady=2)

        row += 1
        ttk.Label(form_frame, text="Uppdrag/Anteckningar:").grid(row=row, column=0, sticky=tk.NW, padx=(5, 2), pady=2)
        mission_text = tk.Text(form_frame, height=2, width=1)  # width=1, let grid expand it
        mission_text.grid(row=row, column=1, columnspan=3, sticky=tk.W+tk.E, padx=(2, 5), pady=2)

        row += 1
        alarm_var = tk.BooleanVar()
        alarm_check = ttk.Checkbutton(form_frame, text="Sätt påminnelse", variable=alarm_var)
        alarm_check.grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=(5, 2), pady=5)

        row += 1
        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=row, column=0, columnspan=4, pady=10, sticky=tk.W)
        ttk.Button(button_frame, text="Spara").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Uppdatera status").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Rensa").pack(side=tk.LEFT, padx=5)

        # Filter
        filter_frame = ttk.Frame(tab)
        filter_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        active_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(filter_frame, text="Visa endast aktiva", variable=active_var).pack(side=tk.LEFT, padx=5)

        # Table
        table_frame = ttk.Frame(tab)
        table_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("who", "status", "location", "last_contact", "mission", "operator")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)

        tree.heading("who", text="Vem")
        tree.heading("status", text="Status")
        tree.heading("location", text="Plats")
        tree.heading("last_contact", text="Senaste kontakt")
        tree.heading("mission", text="Uppdrag")
        tree.heading("operator", text="Operatör")

        tree.column("who", width=120)
        tree.column("status", width=150)
        tree.column("location", width=120)
        tree.column("last_contact", width=120)
        tree.column("mission", width=350)
        tree.column("operator", width=80)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Demo data
        demo_data = [
            ("Pluton 2", "Ute på patrull", "Sektor Alpha", "221430", "Patrull till checkpoint Alpha och tillbaka", "GC"),
            ("Grupp 3", "I skydd", "Punkt Bravo", "221420", "Bevakning av väg 23", "GC"),
            ("Sgt. Andersson", "Förflyttning", "På väg till lager", "221345", "Hämta förnödenheter", "AK"),
            ("Pluton 1", "I ställning", "Checkpoint Charlie", "221330", "Checkpoint bevakning", "GC"),
        ]

        for row_data in demo_data:
            tree.insert("", tk.END, values=row_data)

    def run(self):
        """Start the main window."""
        self.root.mainloop()


def main():
    """Run the complete demo: login → main window."""

    def on_login_success():
        """Called when login succeeds - show main window."""
        main_window = MainWindow()
        main_window.run()

    # Show login window first
    login_window = LoginWindow(on_login_success)
    login_window.run()


if __name__ == "__main__":
    main()

