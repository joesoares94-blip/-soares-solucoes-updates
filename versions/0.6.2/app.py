from __future__ import annotations
import tkinter as tk
from modern_ui import Button, Entry, ScrollArea, configure_style
from modern_shell import ModernMixin
from tkinter import ttk, messagebox, filedialog
from tkinter import font as tkfont
import queue
import threading
import base64
from pathlib import Path


from database import init_db
import auth
import services
from excel_import import import_xlsx
from reports import export_stock_pdf
import updater

APP_TITLE = 'Soares Soluções'
VERSION = '0.6.2'
NAVY = '#102D4B'
NAVY2 = '#1F4E79'
BG = '#F3F6FA'
TEXT = '#162740'
MUTED = '#60738E'
WHITE = '#FFFFFF'
BORDER = '#E4E7EC'
SUCCESS = '#157347'
DANGER = '#B42318'
ACCENT = '#2F80FF'
LOGIN_GRADIENT_START = '#0B1F5E'
LOGIN_GRADIENT_END = '#2BB3FF'
PINK = '#FF3B8D'

ROLE_LABELS = {
    'OWNER': 'Proprietário',
    'ADMIN': 'Administrador',
    'OPERATOR': 'Operador',
    'VIEWER': 'Consulta',
}
ROLE_FROM_LABEL = {v: k for k, v in ROLE_LABELS.items()}


class App(ModernMixin, tk.Tk):
    APP_VERSION = VERSION
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        try:
            from pathlib import Path
            self.iconbitmap(default=str(Path(__file__).with_name('soares_solucoes.ico')))
        except Exception:
            pass
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        self.geometry(f'{min(1450, screen_w)}x{min(860, max(700, screen_h - 80))}')
        self.minsize(1120, 660)
        self.configure(bg=BG)
        self.current_user = None
        self.update_queue = queue.Queue()
        self._update_check_started = False
        self._access_screen_active = False
        init_db()
        self._style()
        self.show_access_screen()
        # A verificação também precisa funcionar quando a tela de acesso falhar.
        self.after(2500, self.check_updates_silent)
        self._update_check_started = True

    def _style(self):
        configure_style(self)

    def reset_root(self):
        for widget in self.winfo_children():
            widget.destroy()

    def show_access_screen(self):
        self.reset_root()
        self._access_screen_active = True
        if auth.has_users():
            self.show_login()
        else:
            self.show_first_owner_setup()

    def report_callback_exception(self, exc, value, tb):
        # Tkinter normalmente só escreve erros de eventos no stderr; no Windows
        # isso fica invisível e pode deixar uma janela aparentemente vazia.
        if self._access_screen_active:
            self._show_access_fallback(str(value))
            return
        messagebox.showerror('Erro no Soares Soluções', str(value), parent=self)

    def _show_access_fallback(self, error=''):
        if not self.winfo_exists():
            return
        self._access_screen_active = False
        self.reset_root()
        shell = tk.Frame(self, bg=WHITE)
        shell.pack(fill='both', expand=True)
        card = tk.Frame(shell, bg=WHITE, highlightthickness=1, highlightbackground=BORDER,
                        padx=34, pady=30)
        card.place(relx=.5, rely=.5, anchor='center', width=430)
        tk.Label(card, text='SOARES SOLUÇÕES', bg=WHITE, fg=NAVY,
                 font=('Segoe UI', 21, 'bold')).pack(anchor='w')
        if auth.has_users():
            tk.Label(card, text='Entrar no sistema', bg=WHITE, fg=TEXT,
                     font=('Segoe UI', 13)).pack(anchor='w', pady=(16, 14))
            username = tk.StringVar()
            password = tk.StringVar()
            tk.Label(card, text='Usuário', bg=WHITE, fg=TEXT).pack(anchor='w', pady=(0, 4))
            user_entry = Entry(card, textvariable=username)
            user_entry.pack(fill='x', pady=(0, 10))
            tk.Label(card, text='Senha', bg=WHITE, fg=TEXT).pack(anchor='w', pady=(0, 4))
            pass_entry = Entry(card, textvariable=password, show='•')
            pass_entry.pack(fill='x')
            status = tk.Label(card, text='', bg=WHITE, fg=DANGER, font=('Segoe UI', 9))
            status.pack(anchor='w', pady=(8, 0))

            def login(_event=None):
                user = auth.authenticate(username.get().strip(), password.get())
                if not user:
                    status.configure(text='Usuário ou senha inválidos.')
                    return
                self.current_user = user
                self.build_main_ui()

            Button(card, text='Entrar', command=login, bg=PINK, fg=WHITE,
                      activebackground=PINK, activeforeground=WHITE, bd=0, pady=10,
                      font=('Segoe UI', 10, 'bold')).pack(fill='x', pady=(14, 0))
            pass_entry.bind('<Return>', login)
            user_entry.focus_set()
        else:
            tk.Label(card, text='Configuração inicial', bg=WHITE, fg=TEXT,
                     font=('Segoe UI', 13)).pack(anchor='w', pady=(16, 14))
            full_name, username = tk.StringVar(), tk.StringVar()
            password, confirm = tk.StringVar(), tk.StringVar()
            fields = [('Seu nome', full_name, ''), ('Usuário', username, ''),
                      ('Senha', password, '•'), ('Confirmar senha', confirm, '•')]
            for label, variable, mask in fields:
                tk.Label(card, text=label, bg=WHITE, fg=TEXT).pack(anchor='w', pady=(0, 4))
                Entry(card, textvariable=variable, show=mask).pack(fill='x', pady=(0, 8))

            def create_owner():
                if password.get() != confirm.get():
                    messagebox.showerror('Senha', 'As duas senhas não são iguais.', parent=self)
                    return
                try:
                    auth.create_first_owner(username.get(), full_name.get(), password.get())
                    self.show_access_screen()
                except Exception as exc:
                    messagebox.showerror('Não foi possível criar a conta', str(exc), parent=self)

            Button(card, text='Criar conta principal', command=create_owner, bg=PINK, fg=WHITE,
                      activebackground=PINK, activeforeground=WHITE, bd=0, pady=10,
                      font=('Segoe UI', 10, 'bold')).pack(fill='x', pady=(8, 0))
        tk.Label(card, text='A tela visual está em modo de recuperação. Seus dados locais foram mantidos.',
                 bg=WHITE, fg=MUTED, wraplength=350, justify='left',
                 font=('Segoe UI', 9)).pack(anchor='w', pady=(18, 0))
        if error:
            # Keep diagnostics local and avoid exposing a traceback to the user.
            try:
                log_path = Path(__file__).with_name('access_screen_error.log')
                log_path.write_text(error[:2000], encoding='utf-8')
            except Exception:
                pass

    def _draw_gradient(self, canvas, color1, color2, width, height):
        def hex_to_rgb(value):
            value = value.lstrip('#')
            return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))

        r1, g1, b1 = hex_to_rgb(color1)
        r2, g2, b2 = hex_to_rgb(color2)
        steps = max(1, min(width, 420))
        for i in range(steps):
            ratio = i / max(steps - 1, 1)
            nr = int(r1 + (r2 - r1) * ratio)
            ng = int(g1 + (g2 - g1) * ratio)
            nb = int(b1 + (b2 - b1) * ratio)
            color = f"#{nr:02x}{ng:02x}{nb:02x}"
            x1 = int(i * width / steps)
            x2 = int((i + 1) * width / steps) + 1
            canvas.create_rectangle(x1, 0, x2, height, fill=color, outline=color)

    def _rounded_shape(self, canvas, x1, y1, x2, y2, radius, fill, outline='', width=1, tags=()):
        radius = max(0, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
        points = []
        corners = [
            (x2 - radius, y1 + radius, -90, 0),
            (x2 - radius, y2 - radius, 0, 90),
            (x1 + radius, y2 - radius, 90, 180),
            (x1 + radius, y1 + radius, 180, 270),
        ]
        for cx, cy, start, end in corners:
            for step in range(9):
                angle = (start + (end - start) * step / 8) * 3.141592653589793 / 180
                points.extend((cx + radius * __import__('math').cos(angle),
                               cy + radius * __import__('math').sin(angle)))
        return canvas.create_polygon(*points, smooth=True, splinesteps=12, fill=fill,
                                     outline=outline, width=width, tags=tags)

    def _access_shell(self, title: str, subtitle: str):
        return self.modern_access_shell(title, subtitle)

    def _pill_entry(self, parent, variable, placeholder, icon='user', password=False):
        row = tk.Canvas(parent, height=54, bg='#073DA8', highlightthickness=0, bd=0)
        row.pack(fill='x', pady=(0, 12))
        entry = tk.Entry(row, textvariable=variable, relief='flat', bd=0, bg='#0B3EAD', fg=WHITE,
                         insertbackground=WHITE, font=('Segoe UI', 11), show='•' if password else '')
        state = {'placeholder': True, 'visible': False}
        entry.insert(0, placeholder)
        entry.configure(fg='#D7E5FF', show='')

        def draw(_event=None):
            row.delete('field')
            width = max(row.winfo_width(), 280)
            self._rounded_shape(row, 1, 1, width - 2, 52, 26, '#0B3EAD', outline='#FFFFFF',
                                width=1, tags='field')
            row.create_line(55, 13, 55, 41, fill='#AFC8F2', width=1, tags='field')
            cy = 27
            if icon == 'user':
                row.create_oval(18, cy - 9, 30, cy + 3, outline=WHITE, width=1, tags='field')
                row.create_arc(14, cy - 1, 34, cy + 17, start=0, extent=180,
                               style='arc', outline=WHITE, width=1, tags='field')
            else:
                row.create_oval(15, cy - 8, 35, cy + 8, outline=WHITE, width=1, tags='field')
                row.create_oval(22, cy - 4, 28, cy + 4, outline=WHITE, width=1, tags='field')
            if password:
                row.create_text(width - 26, cy, text='◉', fill=WHITE,
                                font=('Segoe UI Symbol', 13), tags=('field', 'eye'))
            row.coords(entry_window, 68, cy)
            row.itemconfigure(entry_window, width=max(100, width - (112 if password else 84)))

        def focus_in(_event=None):
            if state['placeholder']:
                entry.delete(0, 'end')
                entry.configure(fg=WHITE, show='•' if password and not state['visible'] else '')
                state['placeholder'] = False

        def focus_out(_event=None):
            if not entry.get():
                state['placeholder'] = True
                entry.configure(show='', fg='#D7E5FF')
                entry.insert(0, placeholder)

        def toggle_eye(_event=None):
            if password and not state['placeholder']:
                state['visible'] = not state['visible']
                entry.configure(show='' if state['visible'] else '•')

        entry_window = row.create_window(68, 27, window=entry, anchor='w', width=180)
        row.bind('<Configure>', draw)
        row.tag_bind('eye', '<Button-1>', toggle_eye)
        entry.bind('<FocusIn>', focus_in)
        entry.bind('<FocusOut>', focus_out)
        entry.bind('<Button-1>', focus_in, add='+')
        return entry, state

    def _pill_button(self, parent, text, command):
        button = tk.Canvas(parent, height=56, bg='#073DA8', highlightthickness=0, bd=0, cursor='hand2')
        button.pack(fill='x', pady=(12, 0))
        def draw(_event=None):
            button.delete('button')
            width = max(button.winfo_width(), 250)
            self._rounded_shape(button, 1, 1, width - 2, 54, 27, PINK, tags='button')
            button.create_text(width / 2, 27, text=text.upper(), fill=WHITE,
                               font=('Segoe UI', 12, 'bold'), tags='button')
        button.bind('<Configure>', draw)
        button.bind('<Button-1>', lambda _event: command())
        return button

    def show_first_owner_setup(self):
        panel = self._access_shell('Configuração inicial',
                                   'Crie a conta principal do sistema. Ela terá o perfil Proprietário e controle sobre os demais usuários.')
        full_name = tk.StringVar()
        username = tk.StringVar()
        password = tk.StringVar()
        confirm = tk.StringVar()
        self._labeled_entry(panel, 'Seu nome', full_name)
        self._labeled_entry(panel, 'Usuário', username)
        self._labeled_entry(panel, 'Senha', password, show='•')
        self._labeled_entry(panel, 'Confirmar senha', confirm, show='•')

        def save_owner():
            if password.get() != confirm.get():
                messagebox.showerror('Senha', 'As duas senhas não são iguais.')
                return
            try:
                auth.create_first_owner(username.get(), full_name.get(), password.get())
                messagebox.showinfo('Conta criada', 'Conta de Proprietário criada. Faça o primeiro login.')
                self.show_access_screen()
            except Exception as exc:
                messagebox.showerror('Não foi possível criar a conta', str(exc))

        Button(panel, text='Criar conta principal', command=save_owner, bg=ACCENT, fg='white',
                  activebackground=NAVY2, activeforeground='white', bd=0, pady=11,
                  font=('Segoe UI', 10, 'bold'), cursor='hand2').pack(fill='x', pady=(16, 0))

    def _labeled_entry(self, parent, label, variable, show=None):
        parent_bg = parent.cget('bg')
        label_fg = WHITE if parent_bg in {LOGIN_GRADIENT_START, '#073DA8'} else TEXT
        tk.Label(parent, text=label, bg=parent_bg, fg=label_fg, font=('Segoe UI', 9)).pack(anchor='w', pady=(7, 3))
        entry = Entry(parent, textvariable=variable, show=show)
        entry.pack(fill='x')
        return entry

    def show_login(self):
        panel = self._access_shell('Bem-vindo de volta',
                                   'Entre com seu usuário e senha para continuar.')
        username, password = tk.StringVar(), tk.StringVar()
        user_entry = self._labeled_entry(panel, 'Usuário', username)
        pass_entry = self._labeled_entry(panel, 'Senha', password, show='•')
        show_password = tk.BooleanVar(value=False)
        tk.Checkbutton(panel, text='Mostrar senha', variable=show_password,
                       command=lambda: pass_entry.native.configure(show='' if show_password.get() else '•'),
                       bg=WHITE, fg=MUTED, activebackground=WHITE,
                       selectcolor=WHITE, font=('Segoe UI', 9), bd=0).pack(anchor='w', pady=(10, 0))
        status = tk.Label(panel, text='', bg=WHITE, fg=DANGER,
                          font=('Segoe UI', 9), anchor='w', wraplength=368)
        status.pack(fill='x', pady=(10, 0))

        def login(_event=None):
            user = auth.authenticate(username.get().strip(), password.get())
            if not user:
                status.configure(text='Usuário ou senha inválidos.')
                pass_entry.focus_set()
                return
            self.current_user = user
            self.build_main_ui()

        username.trace_add('write', lambda *_: status.configure(text=''))
        password.trace_add('write', lambda *_: status.configure(text=''))
        Button(panel, text='Entrar no sistema', command=login, height=44,
               font=('Segoe UI', 11, 'bold')).pack(fill='x', pady=(12, 8))
        Button(panel, text='Esqueci minha senha', bg=WHITE, fg=MUTED,
               command=lambda: messagebox.showinfo('Recuperação de senha',
                   'Peça ao Proprietário ou Administrador do sistema para redefinir sua senha.',
                   parent=self)).pack(fill='x')
        user_entry.bind('<Return>', lambda _e: pass_entry.focus_set())
        pass_entry.bind('<Return>', login)
        user_entry.focus_set()

    def build_main_ui(self):
        self._access_screen_active = False
        self.reset_root()
        self._layout()
        self.show_dashboard()
        if not self._update_check_started:
            self._update_check_started = True
            self.after(2500, self.check_updates_silent)

    def can_edit_stock(self):
        return bool(self.current_user and self.current_user['role'] in {'OWNER', 'ADMIN', 'OPERATOR'})

    def can_manage_users(self):
        return bool(self.current_user and self.current_user['role'] in {'OWNER', 'ADMIN'})

    def can_manage_catalog(self):
        return bool(self.current_user and self.current_user['role'] in {'OWNER', 'ADMIN', 'OPERATOR'})

    def require(self, condition: bool, message='Você não tem permissão para executar esta ação.'):
        if not condition:
            messagebox.showwarning('Acesso restrito', message)
            return False
        return True

    @staticmethod
    def _round_rect(canvas, x1, y1, x2, y2, radius, fill):
        r = min(radius, (x2-x1)/2, (y2-y1)/2)
        canvas.create_rectangle(x1+r, y1, x2-r, y2, fill=fill, outline=fill)
        canvas.create_rectangle(x1, y1+r, x2, y2-r, fill=fill, outline=fill)
        for cx in (x1+r, x2-r):
            for cy in (y1+r, y2-r):
                canvas.create_oval(cx-r, cy-r, cx+r, cy+r, fill=fill, outline=fill)

    def _logout_button(self, parent):
        button = tk.Canvas(parent, height=34, bg=NAVY, highlightthickness=0,
                           bd=0, cursor='hand2', takefocus=1)
        button.pack(fill='x')

        def draw(hover=False):
            button.delete('all')
            width = max(button.winfo_width(), 100)
            self._round_rect(button, 1, 1, width-1, 33, 16, '#315D89' if hover else NAVY2)
            button.create_text(width/2, 17, text='Sair', fill=WHITE, font=('Segoe UI', 10))

        button.bind('<Configure>', lambda event: draw())
        button.bind('<Enter>', lambda event: draw(True))
        button.bind('<Leave>', lambda event: draw())
        button.bind('<Button-1>', lambda event: self.logout())
        button.bind('<Return>', lambda event: self.logout())
        button.bind('<space>', lambda event: self.logout())
        return button

    def _nav_button(self, parent, label, command):
        button = tk.Canvas(parent, width=208, height=42, bg=NAVY, highlightthickness=0,
                           bd=0, cursor='hand2', takefocus=1)
        button.pack(fill='x', padx=16, pady=3)

        def draw(hover=False):
            selected = self._active_nav == label
            fill = NAVY2 if selected else '#244468' if hover else '#1A3658'
            button.delete('all')
            self._round_rect(button, 0, 0, 208, 42, 12, fill)
            button.create_text(16, 21, text=label, anchor='w', fill=WHITE,
                               font=('Segoe UI', 11, 'bold' if selected else 'normal'))

        self._nav_buttons[label] = draw
        draw()
        button.bind('<Enter>', lambda event: draw(True))
        button.bind('<Leave>', lambda event: draw())
        button.bind('<Button-1>', lambda event: (button.focus_set(), command()))
        button.bind('<Return>', lambda event: command())
        button.bind('<space>', lambda event: command())

    def _layout(self):
        self.modern_layout()

    def logout(self):
        self.current_user = None
        self.show_access_screen()

    def clear(self):
        for widget in self.content.winfo_children():
            widget.destroy()

    def header(self, title, subtitle=''):
        return self.modern_header(title, subtitle)

    def card(self, parent, title, value, detail=''):
        frame = tk.Frame(parent, bg=WHITE, highlightthickness=1, highlightbackground=BORDER, padx=18, pady=16)
        tk.Label(frame, text=title, bg=WHITE, fg=MUTED, font=('Segoe UI', 9)).pack(anchor='w')
        tk.Label(frame, text=str(value), bg=WHITE, fg=TEXT, font=('Segoe UI', 21, 'bold')).pack(anchor='w', pady=(4, 0))
        if detail:
            tk.Label(frame, text=detail, bg=WHITE, fg=MUTED, font=('Segoe UI', 8)).pack(anchor='w')
        return frame

    def show_dashboard(self):
        self.modern_dashboard()

    def show_products(self):
        self.modern_products()

    def fill_products(self):
        if hasattr(self, '_stock_table') and self._stock_table.winfo_exists():
            self._stock_rows = [dict(r) for r in services.list_products()]
            self._render_stock()

    def new_product_dialog(self):
        if not self.require(self.can_manage_catalog()):
            return
        win = tk.Toplevel(self)
        win.title(f'{APP_TITLE} — Nova mercadoria')
        win.geometry('680x590')
        win.minsize(620, 560)
        win.configure(bg=BG)
        win.transient(self)
        win.grab_set()

        tk.Label(win, text='Cadastrar nova mercadoria', bg=BG, fg=TEXT,
                 font=('Segoe UI', 18, 'bold')).pack(anchor='w', padx=24, pady=(22, 4))
        tk.Label(win, text='Preencha os dados do produto. Campos com * são obrigatórios.',
                 bg=BG, fg=MUTED, font=('Segoe UI', 9)).pack(anchor='w', padx=24, pady=(0, 14))

        # Rodapé fixo: os botões permanecem visíveis mesmo em telas menores.
        footer = tk.Frame(win, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        footer.pack(side='bottom', fill='x')
        footer_inner = tk.Frame(footer, bg=WHITE)
        footer_inner.pack(fill='x', padx=24, pady=14)

        scroll = ScrollArea(win, bg=BG)
        scroll.pack(fill='both', expand=True, padx=24, pady=(0, 8))
        form = scroll.body
        form.grid_columnconfigure(0, weight=1)
        form.grid_columnconfigure(1, weight=1)

        vars_ = {}

        def add_field(key, label, row, col, colspan=1):
            box = tk.Frame(form, bg=BG)
            box.grid(row=row, column=col, columnspan=colspan, sticky='ew',
                     padx=(0, 10) if col == 0 and colspan == 1 else (10, 0) if col == 1 else 0,
                     pady=(0, 10))
            tk.Label(box, text=label, bg=BG, fg=TEXT, font=('Segoe UI', 9)).pack(anchor='w', pady=(0, 3))
            var = tk.StringVar()
            vars_[key] = var
            entry = Entry(box, textvariable=var)
            entry.pack(fill='x')
            return entry

        code_entry = add_field('code', 'Código *', 0, 0)
        add_field('price', 'Preço', 0, 1)
        add_field('description', 'Descrição *', 1, 0, 2)
        add_field('brand', 'Marca', 2, 0)
        add_field('model', 'Modelo', 2, 1)
        add_field('category', 'Categoria', 3, 0)
        add_field('color', 'Cor', 3, 1)
        add_field('voltage', 'Voltagem', 4, 0)
        add_field('barcode', 'Código de barras', 4, 1)
        add_field('notes', 'Observações', 5, 0, 2)

        qf = tk.Frame(form, bg=BG)
        qf.grid(row=6, column=0, columnspan=2, sticky='ew', pady=(0, 4))
        qf.grid_columnconfigure(0, weight=1)
        qf.grid_columnconfigure(1, weight=1)
        depot = tk.StringVar(value='0')
        display = tk.StringVar(value='0')
        for col, (label, var) in enumerate([('Quantidade no depósito', depot), ('Quantidade em exposição', display)]):
            sf = tk.Frame(qf, bg=BG)
            sf.grid(row=0, column=col, sticky='ew', padx=(0, 10) if col == 0 else (10, 0))
            tk.Label(sf, text=label, bg=BG, fg=TEXT, font=('Segoe UI', 9)).pack(anchor='w', pady=(0, 3))
            Entry(sf, textvariable=var).pack(fill='x')

        def parse_qty(value, label):
            raw = value.get().strip() or '0'
            try:
                qty = int(raw)
            except ValueError:
                raise ValueError(f'{label} deve ser um número inteiro.')
            if qty < 0:
                raise ValueError(f'{label} não pode ser negativa.')
            return qty

        def save():
            if not vars_['code'].get().strip():
                messagebox.showwarning('Campo obrigatório', 'Informe o código da mercadoria.', parent=win)
                return
            if not vars_['description'].get().strip():
                messagebox.showwarning('Campo obrigatório', 'Informe a descrição da mercadoria.', parent=win)
                return
            try:
                depot_qty = parse_qty(depot, 'A quantidade no depósito')
                display_qty = parse_qty(display, 'A quantidade em exposição')
                services.create_product({k: v.get().strip() for k, v in vars_.items()},
                                        depot_qty, display_qty, self.current_user['id'])
                product_name = vars_['description'].get().strip()
                win.destroy()
                self.show_products()
                messagebox.showinfo('Mercadoria cadastrada',
                                    f'“{product_name}” foi cadastrada com sucesso.', parent=self)
            except Exception as exc:
                messagebox.showerror('Não foi possível cadastrar', str(exc), parent=win)

        Button(footer_inner, text='Cancelar', command=win.destroy, bg=WHITE, fg=TEXT,
                  bd=1, relief='solid', padx=18, pady=9, cursor='hand2').pack(side='right', padx=(10, 0))
        Button(footer_inner, text='Salvar mercadoria', command=save, bg=NAVY, fg='white',
                  bd=0, padx=24, pady=10, cursor='hand2',
                  font=('Segoe UI', 10, 'bold')).pack(side='right')

        win.bind('<Control-s>', lambda event: save())
        code_entry.focus_set()

    def import_excel(self):
        if not self.require(self.can_manage_catalog()):
            return
        path = filedialog.askopenfilename(title='Selecione a planilha', filetypes=[('Excel', '*.xlsx')])
        if not path:
            return
        try:
            result = import_xlsx(path)
            msg = (f"Aba: {result.get('sheet', '-')}\nNovos produtos: {result['created']}\nAtualizados: {result['updated']}\n"
                   f"Ignorados: {result['skipped']}")
            if result['errors']:
                msg += f"\nErros: {len(result['errors'])}\n" + '\n'.join(result['errors'][:5])
            messagebox.showinfo('Importação concluída', msg)
            self.show_products()
        except Exception as exc:
            messagebox.showerror('Erro na importação', str(exc))

    def show_inventory(self):
        self.clear()
        self.header('Inventário', 'Informe onde estão as unidades de cada mercadoria.')
        top = tk.Frame(self.content, bg=BG)
        top.pack(fill='x', padx=30, pady=(0, 10))
        search = tk.StringVar()
        Entry(top, textvariable=search).pack(fill='x')
        box = tk.Frame(self.content, bg=WHITE)
        box.pack(fill='both', expand=True, padx=30, pady=(0, 25))
        tree = ttk.Treeview(box, columns=('code', 'desc', 'depot', 'display', 'total'), show='headings')
        for col, title, width in [('code', 'Código', 100), ('desc', 'Produto', 430), ('depot', 'Depósito', 90),
                                  ('display', 'Exposição', 90), ('total', 'Total', 70)]:
            tree.heading(col, text=title)
            tree.column(col, width=width, anchor='w')
        tree.pack(fill='both', expand=True, padx=12, pady=12)

        def fill(*_):
            tree.delete(*tree.get_children())
            for row in services.list_products(search.get()):
                tree.insert('', 'end', iid=str(row['id']),
                            values=(row['code'], row['description'], row['depot_qty'], row['display_qty'], row['total_qty']))

        def edit(_event=None):
            if not self.require(self.can_edit_stock(), 'Seu perfil permite somente consulta do estoque.'):
                return
            selection = tree.selection()
            if not selection:
                return
            pid = int(selection[0])
            row = services.get_product(pid)
            win = tk.Toplevel(self)
            win.title(f'{APP_TITLE} — Atualizar inventário')
            win.geometry('420x300')
            win.configure(bg=BG)
            win.transient(self)
            win.grab_set()
            tk.Label(win, text=row['description'], bg=BG, fg=TEXT, font=('Segoe UI', 13, 'bold'),
                     wraplength=360).pack(padx=20, pady=(20, 12))
            depot = tk.StringVar(value=str(row['depot_qty']))
            display = tk.StringVar(value=str(row['display_qty']))
            for label, var in [('Quantidade no depósito', depot), ('Quantidade em exposição', display)]:
                tk.Label(win, text=label, bg=BG, fg=TEXT).pack(anchor='w', padx=24)
                Entry(win, textvariable=var).pack(fill='x', padx=24, pady=(3, 10))

            def save():
                try:
                    services.set_initial_inventory(pid, int(depot.get()), int(display.get()), self.current_user['id'])
                    win.destroy()
                    fill()
                except Exception as exc:
                    messagebox.showerror('Erro', str(exc), parent=win)

            Button(win, text='Salvar inventário', command=save, bg=NAVY, fg='white', bd=0, pady=9,
                      cursor='hand2').pack(fill='x', padx=24, pady=8)

        search.trace_add('write', fill)
        tree.bind('<Double-1>', edit)
        fill()
        tip = ('Dê dois cliques em uma mercadoria para informar depósito e exposição.' if self.can_edit_stock()
               else 'Seu perfil está em modo de consulta; o inventário não pode ser alterado.')
        tk.Label(self.content, text=tip, bg=BG, fg=MUTED).pack(anchor='w', padx=30, pady=(0, 20))

    def show_movements(self):
        self.clear()
        self.header('Movimentações', 'Registre entrada de mercadoria ou mudança entre depósito e exposição.')
        if self.can_edit_stock():
            form = tk.Frame(self.content, bg=WHITE, highlightthickness=1, highlightbackground=BORDER)
            form.pack(fill='x', padx=30, pady=(0, 20))
            inner = tk.Frame(form, bg=WHITE)
            inner.pack(fill='x', padx=20, pady=18)

            search_var = tk.StringVar()
            product_var = tk.StringVar()
            type_var = tk.StringVar(value='Depósito → Exposição')
            qty_var = tk.StringVar(value='1')
            bylabel = {}

            tk.Label(inner, text='Pesquisar por código ou descrição', bg=WHITE, fg=TEXT).grid(
                row=0, column=0, sticky='w')
            search_entry = Entry(inner, textvariable=search_var, width=18)
            search_entry.grid(row=1, column=0, sticky='ew', padx=(0, 10))

            tk.Label(inner, text='Mercadoria encontrada', bg=WHITE, fg=TEXT).grid(
                row=0, column=1, sticky='w')
            product_combo = ttk.Combobox(inner, textvariable=product_var, values=[], state='readonly')
            product_combo.grid(row=1, column=1, sticky='ew', padx=(0, 10))

            tk.Label(inner, text='Operação', bg=WHITE, fg=TEXT).grid(row=0, column=2, sticky='w')
            ttk.Combobox(inner, textvariable=type_var,
                         values=['Depósito → Exposição', 'Exposição → Depósito',
                                 'Entrada no depósito', 'Entrada na exposição'], state='readonly').grid(
                row=1, column=2, sticky='ew', padx=(0, 10))

            tk.Label(inner, text='Quantidade', bg=WHITE, fg=TEXT).grid(row=0, column=3, sticky='w')
            qty_entry = Entry(inner, textvariable=qty_var, width=8)
            qty_entry.grid(row=1, column=3, sticky='ew', padx=(0, 10))

            stock_info = tk.Label(inner,
                                  text='Digite o código ou parte da descrição para localizar a mercadoria.',
                                  bg=WHITE, fg=MUTED, font=('Segoe UI', 9))
            stock_info.grid(row=2, column=0, columnspan=4, sticky='w', pady=(9, 0))

            inner.grid_columnconfigure(0, weight=2)
            inner.grid_columnconfigure(1, weight=3)
            inner.grid_columnconfigure(2, weight=2)

            def selected_product_id():
                return bylabel.get(product_var.get())

            def refresh_stock_info(*_):
                pid = selected_product_id()
                if not pid:
                    return
                row = services.get_product(pid)
                if row:
                    stock_info.configure(
                        text=f"Estoque atual — Depósito: {row['depot_qty']} | Exposição: {row['display_qty']} | Total: {row['total_qty']}",
                        fg=TEXT)

            def update_product_results(*_):
                term = search_var.get().strip()
                product_var.set('')
                bylabel.clear()
                if not term:
                    product_combo.configure(values=[])
                    stock_info.configure(
                        text='Digite o código ou parte da descrição para localizar a mercadoria.', fg=MUTED)
                    return

                rows = services.search_products(term, limit=80)
                labels = []
                exact_label = None
                for row in rows:
                    label = f"{row['code']} — {row['description']}"
                    labels.append(label)
                    bylabel[label] = row['id']
                    if str(row['code']).strip().casefold() == term.casefold():
                        exact_label = label

                product_combo.configure(values=labels)
                if exact_label:
                    product_var.set(exact_label)
                    refresh_stock_info()
                elif len(labels) == 1:
                    product_var.set(labels[0])
                    refresh_stock_info()
                elif labels:
                    stock_info.configure(text=f'{len(labels)} resultado(s) encontrado(s). Selecione a mercadoria.', fg=MUTED)
                else:
                    stock_info.configure(text='Nenhuma mercadoria encontrada para essa pesquisa.', fg=DANGER)

            def search_enter(_event=None):
                if product_var.get() in bylabel:
                    qty_entry.focus_set()
                    qty_entry.selection_range(0, 'end')
                else:
                    values = product_combo.cget('values')
                    if len(values) == 1:
                        product_var.set(values[0])
                        refresh_stock_info()
                        qty_entry.focus_set()
                        qty_entry.selection_range(0, 'end')

            search_var.trace_add('write', update_product_results)
            product_combo.bind('<<ComboboxSelected>>', refresh_stock_info)
            search_entry.bind('<Return>', search_enter)

            def save():
                try:
                    pid = selected_product_id()
                    if not pid:
                        raise ValueError('Pesquise e selecione uma mercadoria.')
                    qty = int(qty_var.get())
                    op = type_var.get()
                    uid = self.current_user['id']
                    if op == 'Depósito → Exposição':
                        services.move_internal(pid, qty, 'DEPOT', 'DISPLAY', uid)
                    elif op == 'Exposição → Depósito':
                        services.move_internal(pid, qty, 'DISPLAY', 'DEPOT', uid)
                    elif op == 'Entrada no depósito':
                        services.add_stock(pid, qty, 'DEPOT', user_id=uid)
                    else:
                        services.add_stock(pid, qty, 'DISPLAY', user_id=uid)
                    messagebox.showinfo('Movimentação registrada', 'Estoque atualizado com sucesso.')
                    self.show_movements()
                except Exception as exc:
                    messagebox.showerror('Erro', str(exc))

            register_btn = Button(inner, text='Registrar', command=save, bg=NAVY, fg='white', bd=0,
                                     padx=20, pady=8, cursor='hand2')
            register_btn.grid(row=1, column=4)
            qty_entry.bind('<Return>', lambda _event: save())
            search_entry.focus_set()
        else:
            tk.Label(self.content, text='Perfil de consulta: você pode visualizar, mas não registrar movimentações.',
                     bg=BG, fg=MUTED).pack(anchor='w', padx=30, pady=(0, 16))
        self._history_table(limit=50)

    def _history_table(self, limit=300):
        box = tk.Frame(self.content, bg=WHITE)
        box.pack(fill='both', expand=True, padx=30, pady=(0, 25))
        box.grid_rowconfigure(0, weight=1)
        box.grid_columnconfigure(0, weight=1)
        tree = ttk.Treeview(box, columns=('date', 'user', 'code', 'desc', 'type', 'qty', 'from', 'to', 'reason'), show='headings')
        cols = [('date', 'Data', 165), ('user', 'Usuário', 130), ('code', 'Código', 80), ('desc', 'Produto', 255),
                ('type', 'Movimento', 190), ('qty', 'Qtd.', 50), ('from', 'Origem', 90), ('to', 'Destino', 90),
                ('reason', 'Detalhes do registro', 430)]
        for col, title, width in cols:
            tree.heading(col, text=title)
            tree.column(col, width=width, minwidth=width, anchor='w')
        kinds = {'ENTRY': 'Entrada', 'INTERNAL_TRANSFER': 'Transferência interna', 'INVENTORY_SET': 'Ajuste de inventário'}
        places = {'DEPOT': 'Depósito', 'DISPLAY': 'Exposição', 'EXTERNAL': 'Externo'}
        for row in services.movements(limit):
            tree.insert('', 'end', values=(row['created_at'], row['user_name'], row['code'], row['description'],
                                           kinds.get(row['movement_type'], row['movement_type']), row['qty'],
                                           places.get(row['origin'], row['origin'] or ''),
                                           places.get(row['destination'], row['destination'] or ''), row['reason'] or ''))
        vertical = ttk.Scrollbar(box, orient='vertical', command=tree.yview)
        horizontal = ttk.Scrollbar(box, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky='nsew')
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')

    def show_history(self):
        self.clear()
        self.header('Histórico', 'Últimos 300 registros, com usuário responsável e detalhes. Os anteriores permanecem salvos.')
        self._history_table()

    def show_users(self):
        if not self.require(self.can_manage_users()):
            return
        self.clear()
        head = self.header('Usuários', 'Controle quem pode entrar no sistema e qual é o nível de acesso.')
        actions = tk.Frame(head, bg=BG)
        actions.pack(side='right', anchor='e')
        Button(actions, text='+ Novo usuário', command=self.new_user_dialog, bg=NAVY, fg='white', bd=0,
                  padx=14, pady=8, cursor='hand2').pack(side='left', padx=4)
        box = tk.Frame(self.content, bg=WHITE)
        box.pack(fill='both', expand=True, padx=30, pady=(0, 25))
        tree = ttk.Treeview(box, columns=('name', 'username', 'role', 'status', 'last'), show='headings')
        for col, title, width in [('name', 'Nome', 240), ('username', 'Usuário', 150), ('role', 'Perfil', 130),
                                  ('status', 'Status', 90), ('last', 'Último acesso', 160)]:
            tree.heading(col, text=title)
            tree.column(col, width=width, anchor='w')
        for row in auth.list_users():
            tree.insert('', 'end', iid=str(row['id']),
                        values=(row['full_name'], row['username'], ROLE_LABELS[row['role']],
                                'Ativo' if row['active'] else 'Bloqueado', row['last_login'] or '—'))
        tree.pack(fill='both', expand=True, padx=12, pady=(12, 4))

        footer = tk.Frame(box, bg=WHITE)
        footer.pack(fill='x', padx=12, pady=(0, 12))

        def toggle(active: bool):
            selection = tree.selection()
            if not selection:
                messagebox.showwarning('Usuários', 'Selecione um usuário.')
                return
            try:
                auth.set_user_active(int(selection[0]), active, self.current_user['id'])
                self.show_users()
            except Exception as exc:
                messagebox.showerror('Não foi possível alterar o usuário', str(exc))

        Button(footer, text='Ativar selecionado', command=lambda: toggle(True), bg=SUCCESS, fg='white', bd=0,
                  padx=12, pady=7, cursor='hand2').pack(side='left', padx=(0, 6))
        Button(footer, text='Bloquear selecionado', command=lambda: toggle(False), bg=DANGER, fg='white', bd=0,
                  padx=12, pady=7, cursor='hand2').pack(side='left')
        if self.current_user['role'] == 'OWNER':
            Button(footer, text='Alterar perfil', command=lambda: self.change_user_role_dialog(tree),
                      bg=NAVY, fg='white', bd=0, padx=12, pady=7, cursor='hand2').pack(side='right')

    def change_user_role_dialog(self, tree):
        if not self.require(bool(self.current_user and self.current_user['role'] == 'OWNER')):
            return
        selection = tree.selection()
        if not selection:
            messagebox.showwarning('Usuários', 'Selecione um usuário.')
            return
        user_id = int(selection[0])
        user = next((row for row in auth.list_users() if row['id'] == user_id), None)
        if not user:
            messagebox.showerror('Usuários', 'Usuário não encontrado.')
            self.show_users()
            return
        if user['role'] == 'OWNER':
            messagebox.showwarning('Usuários', 'O perfil Proprietário não pode ser alterado.')
            return

        win = tk.Toplevel(self)
        win.title(f'{APP_TITLE} — Alterar perfil')
        win.geometry('420x245')
        win.resizable(False, False)
        win.configure(bg=BG)
        win.transient(self)
        win.grab_set()
        form = tk.Frame(win, bg=BG)
        form.pack(fill='both', expand=True, padx=24, pady=20)
        tk.Label(form, text='Alterar perfil', bg=BG, fg=TEXT, font=('Segoe UI', 16, 'bold')).pack(anchor='w')
        tk.Label(form, text=f"Usuário: {user['full_name']} ({user['username']})", bg=BG, fg=TEXT).pack(
            anchor='w', pady=(10, 8))
        tk.Label(form, text='Novo perfil', bg=BG, fg=TEXT).pack(anchor='w', pady=(0, 3))
        role_label = tk.StringVar(value=ROLE_LABELS[user['role']])
        ttk.Combobox(form, textvariable=role_label, values=['Administrador', 'Operador', 'Consulta'],
                     state='readonly').pack(fill='x')

        def save():
            new_role = ROLE_FROM_LABEL[role_label.get()]
            if new_role == user['role']:
                win.destroy()
                return
            if not messagebox.askyesno('Confirmar alteração',
                                       f"Alterar o perfil de {user['full_name']} para {role_label.get()}?",
                                       parent=win):
                return
            try:
                auth.set_user_role(user_id, new_role, self.current_user['id'])
                win.destroy()
                self.show_users()
            except Exception as exc:
                messagebox.showerror('Não foi possível alterar o perfil', str(exc), parent=win)

        Button(form, text='Salvar perfil', command=save, bg=NAVY, fg='white', bd=0, pady=10,
                  cursor='hand2').pack(fill='x', pady=(18, 0))

    def new_user_dialog(self):
        if not self.require(self.can_manage_users()):
            return
        win = tk.Toplevel(self)
        win.title(f'{APP_TITLE} — Novo usuário')
        win.geometry('460x470')
        win.configure(bg=BG)
        win.transient(self)
        win.grab_set()
        tk.Label(win, text='Novo usuário', bg=BG, fg=TEXT, font=('Segoe UI', 18, 'bold')).pack(
            anchor='w', padx=24, pady=(22, 10))
        form = tk.Frame(win, bg=BG)
        form.pack(fill='both', expand=True, padx=24)
        full_name = tk.StringVar()
        username = tk.StringVar()
        password = tk.StringVar()
        confirm = tk.StringVar()
        role_label = tk.StringVar(value='Operador')
        for label, var, show in [('Nome completo', full_name, None), ('Usuário', username, None),
                                 ('Senha', password, '•'), ('Confirmar senha', confirm, '•')]:
            tk.Label(form, text=label, bg=BG, fg=TEXT).pack(anchor='w', pady=(7, 3))
            Entry(form, textvariable=var, show=show).pack(fill='x')
        tk.Label(form, text='Perfil', bg=BG, fg=TEXT).pack(anchor='w', pady=(7, 3))
        roles = ['Administrador', 'Operador', 'Consulta'] if self.current_user['role'] == 'OWNER' else ['Operador', 'Consulta']
        ttk.Combobox(form, textvariable=role_label, values=roles, state='readonly').pack(fill='x')

        def save():
            if password.get() != confirm.get():
                messagebox.showerror('Senha', 'As duas senhas não são iguais.', parent=win)
                return
            try:
                auth.create_user_authorized(self.current_user['id'], username.get(), full_name.get(), password.get(),
                                            ROLE_FROM_LABEL[role_label.get()])
                win.destroy()
                self.show_users()
            except Exception as exc:
                messagebox.showerror('Não foi possível criar o usuário', str(exc), parent=win)

        Button(form, text='Criar usuário', command=save, bg=NAVY, fg='white', bd=0, pady=10,
                  cursor='hand2').pack(fill='x', pady=18)


    def _start_update_check(self, interactive=False):
        def worker():
            try:
                result = updater.fetch_manifest(VERSION)
                self.update_queue.put(('ok', interactive, result))
            except Exception as exc:
                self.update_queue.put(('error', interactive, str(exc)))
        threading.Thread(target=worker, daemon=True).start()
        self.after(150, self._poll_update_queue)

    def _poll_update_queue(self):
        try:
            kind, interactive, payload = self.update_queue.get_nowait()
        except queue.Empty:
            self.after(150, self._poll_update_queue)
            return
        if kind == 'error':
            if interactive:
                messagebox.showwarning('Atualizações', 'Não foi possível consultar o servidor de atualizações.\n\n' + payload)
            return
        manifest = payload
        if manifest.get('available'):
            self._offer_update(manifest, bool(manifest.get('required')))
        elif interactive:
            messagebox.showinfo('Atualizações', f'Você já está usando a versão mais recente do Soares Soluções ({VERSION}).')

    def check_updates_silent(self):
        self._start_update_check(interactive=False)

    def check_updates_interactive(self):
        self._start_update_check(interactive=True)

    def _offer_update(self, manifest, required=False):
        notes = str(manifest.get('notes') or '').strip()
        message = (f'Nova versão disponível: {manifest.get("version")}\n'
                   f'Versão instalada: {VERSION}')
        if notes:
            message += '\n\n' + notes[:700]
        message += '\n\nO estoque, usuários e histórico serão preservados.'
        if required:
            message += '\n\nEsta atualização foi marcada como obrigatória.'
        if messagebox.askyesno('Atualização do Soares Soluções', message + '\n\nAtualizar agora?'):
            self._run_update(manifest)

    def _run_update(self, manifest):
        progress = tk.Toplevel(self)
        progress.title('Soares Soluções — Atualização')
        progress.geometry('470x190')
        progress.resizable(False, False)
        progress.configure(bg=BG)
        progress.transient(self)
        progress.grab_set()
        tk.Label(progress, text='Baixando atualização...', bg=BG, fg=TEXT,
                 font=('Segoe UI', 16, 'bold')).pack(anchor='w', padx=24, pady=(24, 8))
        tk.Label(progress, text='O programa será fechado e aberto novamente automaticamente.',
                 bg=BG, fg=MUTED, wraplength=410, justify='left').pack(anchor='w', padx=24)
        bar = ttk.Progressbar(progress, mode='indeterminate')
        bar.pack(fill='x', padx=24, pady=22)
        bar.start(10)

        def worker():
            try:
                work = updater.download_and_prepare(manifest)
                self.update_queue.put(('apply', False, (manifest, work)))
            except Exception as exc:
                self.update_queue.put(('apply_error', False, (progress, str(exc))))
        threading.Thread(target=worker, daemon=True).start()

        def poll_apply():
            try:
                kind, _, payload = self.update_queue.get_nowait()
            except queue.Empty:
                self.after(150, poll_apply)
                return
            if kind == 'apply_error':
                win, err = payload
                try:
                    win.destroy()
                except Exception:
                    pass
                messagebox.showerror('Atualização', 'Não foi possível baixar/aplicar a atualização.\n\n' + err)
                return
            if kind == 'apply':
                mf, work = payload
                try:
                    updater.launch_apply_script(work, str(mf['version']))
                    self.destroy()
                except Exception as exc:
                    try:
                        progress.destroy()
                    except Exception:
                        pass
                    messagebox.showerror('Atualização', str(exc))
                return
            self.after(150, poll_apply)
        self.after(150, poll_apply)

    def show_updates(self):
        self.clear()
        self.header('Atualizações', 'Mantenha todos os computadores com a versão mais recente do Soares Soluções.')
        box = tk.Frame(self.content, bg=WHITE, highlightthickness=1, highlightbackground=BORDER, padx=22, pady=20)
        box.pack(fill='x', padx=30, pady=(0, 18))
        tk.Label(box, text='Versão instalada', bg=WHITE, fg=MUTED, font=('Segoe UI', 9)).pack(anchor='w')
        tk.Label(box, text=VERSION, bg=WHITE, fg=TEXT, font=('Segoe UI', 20, 'bold')).pack(anchor='w', pady=(2, 14))
        tk.Label(box, text='O sistema verifica novas versões automaticamente ao iniciar. Você também pode fazer uma verificação manual.',
                 bg=WHITE, fg=TEXT, justify='left', wraplength=780).pack(anchor='w', pady=(0, 14))
        Button(box, text='Verificar atualizações agora', command=self.check_updates_interactive, bg=NAVY, fg='white',
                  bd=0, padx=16, pady=9, font=('Segoe UI', 10, 'bold'), cursor='hand2').pack(anchor='w')
        tk.Label(box, text='Segurança: o pacote é validado por SHA-256 antes de ser instalado. O banco de dados fica fora da pasta do aplicativo e não é substituído.',
                 bg=WHITE, fg=MUTED, justify='left', wraplength=800, font=('Segoe UI', 9)).pack(anchor='w', pady=(16, 0))

    def export_pdf(self):
        path = filedialog.asksaveasfilename(title='Salvar relatório', defaultextension='.pdf',
                                            filetypes=[('PDF', '*.pdf')], initialfile='relatorio_estoque.pdf')
        if not path:
            return
        try:
            export_stock_pdf(path)
            messagebox.showinfo('Relatório gerado', f'PDF salvo em:\n{path}')
        except Exception as exc:
            messagebox.showerror('Erro', str(exc))


if __name__ == '__main__':
    App().mainloop()
