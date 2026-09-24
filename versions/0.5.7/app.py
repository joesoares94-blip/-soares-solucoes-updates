from __future__ import annotations
import tkinter as tk
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
VERSION = '0.5.7'
NAVY = '#0F2747'
NAVY2 = '#1F4E79'
BG = '#F4F6F8'
TEXT = '#172B4D'
MUTED = '#667085'
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


class App(tk.Tk):
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
        self.minsize(1020, 650)
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
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('Treeview', background='white', fieldbackground='white', foreground=TEXT,
                        rowheight=30, borderwidth=0)
        style.configure('Treeview.Heading', background=NAVY, foreground='white',
                        font=('Segoe UI', 10, 'bold'), relief='flat')
        style.map('Treeview', background=[('selected', NAVY2)], foreground=[('selected', 'white')])
        style.configure('TEntry', padding=7)
        style.configure('TCombobox', padding=6)

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
            user_entry = ttk.Entry(card, textvariable=username)
            user_entry.pack(fill='x', pady=(0, 10))
            tk.Label(card, text='Senha', bg=WHITE, fg=TEXT).pack(anchor='w', pady=(0, 4))
            pass_entry = ttk.Entry(card, textvariable=password, show='•')
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

            tk.Button(card, text='Entrar', command=login, bg=PINK, fg=WHITE,
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
                ttk.Entry(card, textvariable=variable, show=mask).pack(fill='x', pady=(0, 8))

            def create_owner():
                if password.get() != confirm.get():
                    messagebox.showerror('Senha', 'As duas senhas não são iguais.', parent=self)
                    return
                try:
                    auth.create_first_owner(username.get(), full_name.get(), password.get())
                    self.show_access_screen()
                except Exception as exc:
                    messagebox.showerror('Não foi possível criar a conta', str(exc), parent=self)

            tk.Button(card, text='Criar conta principal', command=create_owner, bg=PINK, fg=WHITE,
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
        canvas = tk.Canvas(self, bg=WHITE, highlightthickness=0, bd=0)
        canvas.pack(fill='both', expand=True)
        self.access_canvas = canvas
        card_bg = '#073DA8'
        form = tk.Frame(canvas, bg=card_bg)
        form.pack_propagate(False)
        self.access_form = form
        self.login_photo_img = None
        photo_dir = Path(__file__).resolve().parent
        try:
            photo_path = photo_dir / 'login_photo.png'
            gif_path = photo_dir / 'login_photo.gif'
            b64_path = photo_dir / 'login_photo.b64'
            if photo_path.exists():
                self.login_photo_img = tk.PhotoImage(file=str(photo_path))
            elif gif_path.exists():
                self.login_photo_img = tk.PhotoImage(file=str(gif_path))
            elif b64_path.exists():
                self.login_photo_img = tk.PhotoImage(data=b64_path.read_text(encoding='ascii').strip())
            elif (photo_dir / 'v052_login_photo.b64').exists():
                self.login_photo_img = tk.PhotoImage(
                    data=(photo_dir / 'v052_login_photo.b64').read_text(encoding='ascii').strip())
            else:
                parts = sorted(photo_dir.glob('login_photo.b64.part*'))
                if parts:
                    encoded = ''.join(part.read_text(encoding='ascii').strip() for part in parts)
                    self.login_photo_img = tk.PhotoImage(data=encoded)
            self.login_photo_base = self.login_photo_img
        except Exception:
            self.login_photo_img = None

        is_login = title == 'Entrar no sistema'
        form_window = canvas.create_window(0, 0, window=form, anchor='nw', tags=('access_form',))

        def draw_layout(event=None):
            w = max(canvas.winfo_width(), 1020)
            h = max(canvas.winfo_height(), 650)
            s = min(w / 1450, h / 860)
            split = int(w * 0.583)
            canvas.delete('design')
            # Painel azul à direita com o gradiente e as curvas grandes da referência.
            steps = max(1, min(420, w - split))
            stops = ((0.0, (8, 47, 148)), (0.58, (0, 111, 224)), (1.0, (0, 210, 203)))
            for i in range(steps):
                t = i / max(steps - 1, 1)
                for j in range(len(stops) - 1):
                    if stops[j][0] <= t <= stops[j + 1][0]:
                        a, ca = stops[j]
                        b, cb = stops[j + 1]
                        u = (t - a) / (b - a)
                        rgb = tuple(round(ca[k] + (cb[k] - ca[k]) * u) for k in range(3))
                        break
                color = '#%02x%02x%02x' % rgb
                x1 = split + int(i * (w - split) / steps)
                x2 = split + int((i + 1) * (w - split) / steps) + 1
                canvas.create_rectangle(x1, 0, x2, h, fill=color, outline=color, tags=('design', 'gradient'))
            # Arredondamento externo no início e no fim do painel.
            radius = int(78 * s)
            canvas.create_oval(split - radius, -radius, split + radius, radius,
                               fill=WHITE, outline=WHITE, tags='design')
            canvas.create_oval(split - radius, h - radius, split + radius, h + radius,
                               fill=WHITE, outline=WHITE, tags='design')

            # Marca Soares Soluções no painel esquerdo.
            lx, ly = int(64 * s), int(65 * s)
            canvas.create_text(lx + 51 * s, ly + 43 * s, text='S', fill='#1764E8',
                               font=('Segoe UI', max(55, int(85 * s)), 'bold italic'), tags='design')
            canvas.create_line(lx + 126 * s, ly + 6 * s, lx + 126 * s, ly + 91 * s,
                               fill='#DCE5F3', width=max(2, int(3 * s)), tags='design')
            canvas.create_text(lx + 148 * s, ly + 32 * s, text='SOARES', anchor='w',
                               fill='#102B63', font=('Segoe UI', max(24, int(40 * s)), 'bold'), tags='design')
            canvas.create_text(lx + 150 * s, ly + 68 * s, text='S O L U Ç Õ E S', anchor='w',
                               fill='#102B63', font=('Segoe UI', max(11, int(18 * s))), tags='design')

            # Texto institucional e benefícios, mantendo os elementos e a hierarquia da referência.
            tx, ty = int(63 * s), int(218 * s)
            f1 = ('Segoe UI', max(18, int(31 * s)), 'bold')
            f2 = ('Segoe UI', max(18, int(31 * s)), 'bold')
            canvas.create_text(tx, ty, text='Nós da Soares Soluções\ntemos o objetivo de', anchor='nw',
                               fill='#102B63', font=f1, spacing=int(3 * s), tags='design')
            canvas.create_text(tx, ty + 88 * s, text='facilitar o seu dia a dia,\ninovando em tecnologia\ne soluções.',
                               anchor='nw', fill='#1764E8', font=f2, spacing=int(3 * s), tags='design')
            feature_y = int(465 * s)
            features = [('gear', 'Tecnologia', 'que simplifica'),
                        ('chart', 'Soluções', 'que geram resultados'),
                        ('people', 'Parceria', 'em cada etapa')]
            for i, (icon, heading, detail) in enumerate(features):
                cy = feature_y + i * int(79 * s)
                canvas.create_oval(lx - 4 * s, cy, lx + 58 * s, cy + 62 * s,
                                   fill='#EAF1FF', outline='', tags='design')
                if icon == 'gear':
                    canvas.create_text(lx + 27 * s, cy + 31 * s, text='⚙', fill='#1764E8',
                                       font=('Segoe UI Symbol', max(18, int(24 * s))), tags='design')
                elif icon == 'chart':
                    for bar_i, bar_h in enumerate((12, 19, 27)):
                        bx = lx + (15 + bar_i * 9) * s
                        canvas.create_rectangle(bx, cy + (47 - bar_h) * s, bx + 5 * s,
                                               cy + 47 * s, fill='#1764E8', outline='', tags='design')
                else:
                    for dx, dy, size in ((17, 21, 8), (28, 18, 9), (39, 21, 8)):
                        canvas.create_oval(lx + (dx - size / 2) * s, cy + (dy - size / 2) * s,
                                           lx + (dx + size / 2) * s, cy + (dy + size / 2) * s,
                                           fill='#1764E8', outline='', tags='design')
                    canvas.create_arc(lx + 10 * s, cy + 24 * s, lx + 44 * s, cy + 49 * s,
                                      start=0, extent=180, style='pieslice', fill='#1764E8',
                                      outline='', tags='design')
                canvas.create_text(lx + 82 * s, cy + 19 * s, text=heading, anchor='w',
                                   fill='#102B63', font=('Segoe UI', max(10, int(14 * s)), 'bold'), tags='design')
                canvas.create_text(lx + 82 * s, cy + 43 * s, text=detail, anchor='w',
                                   fill='#667085', font=('Segoe UI', max(9, int(13 * s))), tags='design')
            bar_y = int(h * 0.88)
            self._rounded_shape(canvas, lx, bar_y, lx + 48 * s, bar_y + 5 * s, 3 * s,
                                '#1680FF', tags='design')
            canvas.create_text(lx, bar_y + 28 * s,
                               text='M A I S   Q U E   S I S T E M A S,\nS O L U Ç Õ E S   P A R A   O   S E U   C R E S C I M E N T O.',
                               anchor='nw', fill='#667085', font=('Segoe UI', max(8, int(10 * s))),
                               spacing=int(5 * s), tags='design')

            # Retrato recortado em transparência, centralizado e sobreposto à divisão das áreas.
            if self.login_photo_img:
                zoom = 3 if s >= 0.82 else 2
                self.login_photo_img = self.login_photo_base.zoom(zoom, zoom)
                canvas.create_image(int(w * 0.205), -int(60 * s), image=self.login_photo_img,
                                    anchor='nw', tags='design')

            # Cartão de acesso, logotipo e formulário.
            panel_w = int(min(424, max(350, (w - split) - 48 * s)))
            panel_h = int((0.635 if is_login else 0.78) * h)
            panel_x = split + (w - split - panel_w) // 2
            panel_y = (h - panel_h) // 2
            self._rounded_shape(canvas, panel_x, panel_y, panel_x + panel_w, panel_y + panel_h,
                                int(23 * s), '#073DA8', outline='#FFFFFF', width=max(1, int(2 * s)), tags='design')
            # Logo compacto centralizado no cartão azul.
            brand_y = panel_y + int(50 * s)
            canvas.create_text(panel_x + panel_w * 0.31, brand_y + 22 * s, text='S', fill='#58C5FF',
                               font=('Segoe UI', max(35, int(50 * s)), 'bold italic'), tags='design')
            canvas.create_line(panel_x + panel_w * 0.45, brand_y + 5 * s,
                               panel_x + panel_w * 0.45, brand_y + 49 * s,
                               fill='#87A9E8', width=max(1, int(2 * s)), tags='design')
            canvas.create_text(panel_x + panel_w * 0.49, brand_y + 18 * s, text='SOARES', anchor='w',
                               fill=WHITE, font=('Segoe UI', max(17, int(25 * s)), 'bold'), tags='design')
            canvas.create_text(panel_x + panel_w * 0.49, brand_y + 41 * s, text='S O L U Ç Õ E S', anchor='w',
                               fill='#E1EDFF', font=('Segoe UI', max(8, int(11 * s))), tags='design')
            if not is_login:
                canvas.create_text(panel_x + int(42 * s), panel_y + int(126 * s), text=title,
                                   anchor='nw', fill=WHITE, font=('Segoe UI', max(16, int(20 * s)), 'bold'), tags='design')
                canvas.create_text(panel_x + int(42 * s), panel_y + int(158 * s), text=subtitle,
                                   anchor='nw', fill='#D6E6FF', width=panel_w - int(84 * s),
                                   font=('Segoe UI', max(9, int(11 * s))), tags='design')
            form_y = panel_y + int((205 if is_login else 238) * s)
            form_h = max(220, panel_y + panel_h - form_y - int(34 * s))
            form_w = panel_w - int(84 * s)
            canvas.coords(form_window, panel_x + (panel_w - form_w) / 2, form_y)
            canvas.itemconfigure(form_window, width=form_w, height=form_h)
            form.configure(width=form_w, height=form_h)

        def layout(event=None):
            try:
                draw_layout(event)
            except Exception as exc:
                self._show_access_fallback(str(exc))

        canvas.bind('<Configure>', layout)
        self.after_idle(layout)
        return form

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

        tk.Button(panel, text='Criar conta principal', command=save_owner, bg=PINK, fg='white',
                  activebackground=NAVY2, activeforeground='white', bd=0, pady=11,
                  font=('Segoe UI', 10, 'bold'), cursor='hand2').pack(fill='x', pady=(16, 0))

    def _labeled_entry(self, parent, label, variable, show=None):
        parent_bg = parent.cget('bg')
        label_fg = WHITE if parent_bg in {LOGIN_GRADIENT_START, '#073DA8'} else TEXT
        tk.Label(parent, text=label, bg=parent_bg, fg=label_fg, font=('Segoe UI', 9)).pack(anchor='w', pady=(7, 3))
        entry = ttk.Entry(parent, textvariable=variable, show=show)
        entry.pack(fill='x')
        return entry

    def show_login(self):
        # The supplied reference is the decorative layer.  Inputs are real Tk
        # widgets, so keyboard editing, paste and password handling remain native.
        image_dir = Path(__file__).resolve().parent
        backgrounds = []
        try:
            for percent in (100, 80, 70):
                photo = tk.PhotoImage(file=str(image_dir / f'login_bg_{percent}.png'))
                backgrounds.append((photo.width(), photo.height(), photo))
        except Exception as exc:
            self._show_access_fallback(f'Imagem da tela de login: {exc}')
            return

        self._login_backgrounds = backgrounds
        canvas = tk.Canvas(self, bg=WHITE, bd=0, highlightthickness=0)
        canvas.pack(fill='both', expand=True)
        username = tk.StringVar()
        password = tk.StringVar()
        state = {'origin_x': 0, 'origin_y': 0, 'scale': 1.0,
                 'show_password': False, 'status': ''}

        # These small controls receive keyboard input without covering the
        # gradient, outlines and icons in the supplied layout.
        user_entry = tk.Entry(canvas, textvariable=username, bd=0, takefocus=True)
        pass_entry = tk.Entry(canvas, textvariable=password, bd=0, show='•', takefocus=True)
        user_entry.place(x=0, y=0, width=1, height=1)
        pass_entry.place(x=1, y=0, width=1, height=1)

        def redraw():
            if not canvas.winfo_exists():
                return
            canvas.delete('login_overlay')
            scale = state['scale']
            ox, oy = state['origin_x'], state['origin_y']
            input_font = tkfont.Font(family='Segoe UI', size=max(9, round(12 * scale)))
            for entry, variable, label, y in (
                (user_entry, username, 'Usuário', 372),
                (pass_entry, password, 'Senha', 438),
            ):
                value = variable.get()
                if entry is pass_entry and not state['show_password']:
                    value = '•' * len(value)
                visible = value
                while visible and input_font.measure(visible) > 220 * scale:
                    visible = visible[1:]
                x = ox + 1070 * scale
                cy = oy + y * scale
                canvas.create_text(x, cy, text=visible or label, anchor='w',
                                   fill=WHITE if value else '#CAD8EE', font=input_font,
                                   tags='login_overlay')
                if self.focus_get() is entry:
                    clipped = len(value) - len(visible)
                    insert_at = max(0, min(len(visible), entry.index('insert') - clipped))
                    caret_x = x + input_font.measure(visible[:insert_at]) + 2 * scale
                    canvas.create_line(caret_x, cy - 11 * scale, caret_x, cy + 11 * scale,
                                       fill=WHITE, width=max(1, round(scale)), tags='login_overlay')
            if state['status']:
                canvas.create_text(ox + 995 * scale, oy + 478 * scale,
                                   text=state['status'], anchor='w', fill='#FFE2E8',
                                   font=('Segoe UI', max(9, round(10 * scale))),
                                   tags='login_overlay')

        def render(_event=None):
            width, height = canvas.winfo_width(), canvas.winfo_height()
            if width < 500 or height < 400:
                return
            selected = next(((iw, ih, photo) for iw, ih, photo in backgrounds
                             if iw <= width and ih <= height), backgrounds[-1])
            iw, ih, photo = selected
            state['origin_x'] = (width - iw) // 2
            state['origin_y'] = (height - ih) // 2
            state['scale'] = iw / 1448
            canvas.delete('login_background')
            canvas.create_image(state['origin_x'], state['origin_y'], image=photo,
                                anchor='nw', tags='login_background')
            canvas.tag_lower('login_background')
            redraw()

        def changed(*_args):
            state['status'] = ''
            redraw()

        username.trace_add('write', changed)
        password.trace_add('write', changed)
        user_entry.bind('<FocusIn>', lambda _e: redraw())
        pass_entry.bind('<FocusIn>', lambda _e: redraw())
        user_entry.bind('<FocusOut>', lambda _e: self.after_idle(redraw))
        pass_entry.bind('<FocusOut>', lambda _e: self.after_idle(redraw))
        user_entry.bind('<KeyRelease>', lambda _e: redraw())
        pass_entry.bind('<KeyRelease>', lambda _e: redraw())

        def login(_event=None):
            user = auth.authenticate(username.get().strip(), password.get())
            if not user:
                state['status'] = 'Usuário ou senha inválidos.'
                redraw()
                return
            self.current_user = user
            self.build_main_ui()

        def clicked(event):
            scale = state['scale']
            x = (event.x - state['origin_x']) / scale
            y = (event.y - state['origin_y']) / scale
            if 993 <= x <= 1323 and 347 <= y <= 397:
                user_entry.focus_set()
            elif 993 <= x <= 1323 and 413 <= y <= 464:
                if x <= 1052:
                    state['show_password'] = not state['show_password']
                pass_entry.focus_set()
            elif 993 <= x <= 1323 and 495 <= y <= 550:
                login()
            elif 1055 <= x <= 1265 and 592 <= y <= 633:
                messagebox.showinfo('Recuperação de senha',
                    'Peça ao Proprietário ou Administrador do sistema para redefinir sua senha.',
                    parent=self)
            redraw()

        def hover(event):
            x = (event.x - state['origin_x']) / state['scale']
            y = (event.y - state['origin_y']) / state['scale']
            pointer = ((993 <= x <= 1323 and 495 <= y <= 550) or
                       (1055 <= x <= 1265 and 592 <= y <= 633) or
                       (993 <= x <= 1052 and 413 <= y <= 464))
            canvas.configure(cursor='hand2' if pointer else 'arrow')

        canvas.bind('<Configure>', render)
        canvas.bind('<Button-1>', clicked)
        canvas.bind('<Motion>', hover)
        user_entry.bind('<Return>', lambda _e: pass_entry.focus_set())
        pass_entry.bind('<Return>', login)
        self.after_idle(render)
        self.after(100, user_entry.focus_set)

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

    def _layout(self):
        self.sidebar = tk.Frame(self, bg=NAVY, width=240)
        self.sidebar.pack(side='left', fill='y')
        self.sidebar.pack_propagate(False)

        tk.Label(self.sidebar, text='SOARES', bg=NAVY, fg='white', font=('Segoe UI', 18, 'bold')).pack(
            anchor='w', padx=22, pady=(24, 0))
        tk.Label(self.sidebar, text='SOLUÇÕES', bg=NAVY, fg='#A9C2DF', font=('Segoe UI', 11, 'bold')).pack(
            anchor='w', padx=22, pady=(0, 2))
        tk.Label(self.sidebar, text='Estoque e estudos jurídicos', bg=NAVY, fg='#B8C7DB', font=('Segoe UI', 9)).pack(
            anchor='w', padx=22, pady=(0, 22))

        nav = [
            ('Dashboard', self.show_dashboard),
            ('Produtos', self.show_products),
            ('Inventário', self.show_inventory),
            ('Movimentações', self.show_movements),
            ('Histórico', self.show_history),
        ]
        if self.can_manage_users():
            nav.append(('Usuários', self.show_users))
        if self.current_user['role'] == 'OWNER':
            nav.append(('Estúdio Jurídico', self.show_juridico))
        nav.append(('Atualizações', self.show_updates))
        for text, cmd in nav:
            tk.Button(self.sidebar, text=text, command=cmd, bg=NAVY, fg='white', activebackground=NAVY2,
                      activeforeground='white', bd=0, anchor='w', font=('Segoe UI', 11),
                      padx=22, pady=11, cursor='hand2').pack(fill='x')

        bottom = tk.Frame(self.sidebar, bg=NAVY)
        bottom.pack(side='bottom', fill='x', padx=18, pady=16)
        tk.Label(bottom, text=self.current_user['full_name'], bg=NAVY, fg='white',
                 font=('Segoe UI', 9, 'bold'), wraplength=185).pack(anchor='w')
        tk.Label(bottom, text=ROLE_LABELS[self.current_user['role']], bg=NAVY, fg='#A9C2DF',
                 font=('Segoe UI', 8)).pack(anchor='w', pady=(1, 8))
        tk.Button(bottom, text='Sair', command=self.logout, bg=NAVY2, fg='white', bd=0,
                  padx=10, pady=6, cursor='hand2').pack(fill='x')
        tk.Label(bottom, text=f'Versão {VERSION}', bg=NAVY, fg='#8DA2BE', font=('Segoe UI', 8)).pack(
            anchor='center', pady=(10, 0))

        self.content = tk.Frame(self, bg=BG)
        self.content.pack(side='left', fill='both', expand=True)

    def logout(self):
        self.current_user = None
        self.show_access_screen()

    def clear(self):
        for widget in self.content.winfo_children():
            widget.destroy()

    def header(self, title, subtitle=''):
        frame = tk.Frame(self.content, bg=BG)
        frame.pack(fill='x', padx=30, pady=(26, 18))
        tk.Label(frame, text=title, bg=BG, fg=TEXT, font=('Segoe UI', 22, 'bold')).pack(anchor='w')
        if subtitle:
            tk.Label(frame, text=subtitle, bg=BG, fg=MUTED, font=('Segoe UI', 10)).pack(anchor='w', pady=(3, 0))
        return frame

    def card(self, parent, title, value, detail=''):
        frame = tk.Frame(parent, bg=WHITE, highlightthickness=1, highlightbackground=BORDER, padx=18, pady=16)
        tk.Label(frame, text=title, bg=WHITE, fg=MUTED, font=('Segoe UI', 9)).pack(anchor='w')
        tk.Label(frame, text=str(value), bg=WHITE, fg=TEXT, font=('Segoe UI', 21, 'bold')).pack(anchor='w', pady=(4, 0))
        if detail:
            tk.Label(frame, text=detail, bg=WHITE, fg=MUTED, font=('Segoe UI', 8)).pack(anchor='w')
        return frame

    def show_juridico(self):
        if not self.require(self.current_user and self.current_user['role'] == 'OWNER'):
            return
        self.clear()
        self.header('Estúdio Jurídico', 'Cases e Papers dentro do Soares Soluções.')
        from juridico import mount
        self.juridico_workspace = mount(self.content, self.current_user)

    def show_dashboard(self):
        self.clear()
        self.header('Dashboard', 'Visão rápida da disponibilidade das mercadorias.')
        metrics = services.dashboard_metrics()
        cards = tk.Frame(self.content, bg=BG)
        cards.pack(fill='x', padx=30)
        values = [
            ('Produtos', metrics['products']),
            ('Unidades totais', metrics['total_units']),
            ('No depósito', metrics['depot_units']),
            ('Em exposição', metrics['display_units']),
            ('Sem exposição', metrics['no_display']),
            ('Estoque zerado', metrics['out_of_stock']),
        ]
        for i, (title, value) in enumerate(values):
            self.card(cards, title, value).grid(row=i // 3, column=i % 3, sticky='nsew', padx=6, pady=6)
        for i in range(3):
            cards.grid_columnconfigure(i, weight=1)

        panel = tk.Frame(self.content, bg=WHITE, highlightthickness=1, highlightbackground=BORDER)
        panel.pack(fill='both', expand=True, padx=30, pady=18)
        tk.Label(panel, text='Mercadorias no depósito sem unidade em exposição', bg=WHITE, fg=TEXT,
                 font=('Segoe UI', 12, 'bold')).pack(anchor='w', padx=18, pady=(16, 10))
        tree = ttk.Treeview(panel, columns=('code', 'name', 'brand', 'depot'), show='headings', height=10)
        for col, title, width in [('code', 'Código', 100), ('name', 'Produto', 430),
                                  ('brand', 'Marca', 150), ('depot', 'Depósito', 100)]:
            tree.heading(col, text=title)
            tree.column(col, width=width, anchor='w')
        for row in services.special_list('no_display')[:20]:
            tree.insert('', 'end', values=(row['code'], row['description'], row['brand'], row['depot_qty']))
        tree.pack(fill='both', expand=True, padx=18, pady=(0, 18))

    def show_products(self):
        self.clear()
        head = self.header('Produtos', 'Catálogo importado do Excel e novos cadastros.')
        actions = tk.Frame(head, bg=BG)
        actions.pack(side='right', anchor='e')
        if self.can_manage_catalog():
            tk.Button(actions, text='Importar Excel', command=self.import_excel, bg=NAVY2, fg='white', bd=0,
                      padx=14, pady=8, cursor='hand2').pack(side='left', padx=4)
            tk.Button(actions, text='+ Nova mercadoria', command=self.new_product_dialog, bg=NAVY, fg='white', bd=0,
                      padx=14, pady=8, cursor='hand2').pack(side='left', padx=4)

        searchf = tk.Frame(self.content, bg=BG)
        searchf.pack(fill='x', padx=30, pady=(0, 12))
        self.search_var = tk.StringVar()
        entry = ttk.Entry(searchf, textvariable=self.search_var)
        entry.pack(side='left', fill='x', expand=True)
        entry.bind('<KeyRelease>', lambda e: self.fill_products())
        tk.Button(searchf, text='Exportar PDF', command=self.export_pdf, bg='white', fg=NAVY, bd=1,
                  relief='solid', padx=14, pady=7, cursor='hand2').pack(side='left', padx=(10, 0))

        box = tk.Frame(self.content, bg=WHITE)
        box.pack(fill='both', expand=True, padx=30, pady=(0, 25))
        self.product_tree = ttk.Treeview(box, columns=('code', 'desc', 'price', 'depot', 'display', 'total'),
                                         show='headings')
        cols = [('code', 'Código', 90), ('desc', 'Produto', 430), ('price', 'Preço', 90),
                ('depot', 'Depósito', 80), ('display', 'Exposição', 80), ('total', 'Total', 70)]
        for col, title, width in cols:
            self.product_tree.heading(col, text=title)
            self.product_tree.column(col, width=width, anchor='w')
        self.product_tree.pack(fill='both', expand=True)
        self.fill_products()

    def fill_products(self):
        if not hasattr(self, 'product_tree'):
            return
        self.product_tree.delete(*self.product_tree.get_children())
        term = self.search_var.get() if hasattr(self, 'search_var') else ''
        for row in services.list_products(term):
            self.product_tree.insert('', 'end', iid=str(row['id']),
                                     values=(row['code'], row['description'],
                                             '' if row['price'] is None else f"R$ {row['price']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                                             row['depot_qty'], row['display_qty'], row['total_qty']))

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

        form = tk.Frame(win, bg=BG)
        form.pack(fill='both', expand=True, padx=24, pady=(0, 8))
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
            entry = ttk.Entry(box, textvariable=var)
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
            ttk.Entry(sf, textvariable=var).pack(fill='x')

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
                pid = services.create_product({k: v.get().strip() for k, v in vars_.items()})
                services.set_initial_inventory(pid, depot_qty, display_qty, self.current_user['id'])
                product_name = vars_['description'].get().strip()
                win.destroy()
                self.show_products()
                messagebox.showinfo('Mercadoria cadastrada',
                                    f'“{product_name}” foi cadastrada com sucesso.', parent=self)
            except Exception as exc:
                messagebox.showerror('Não foi possível cadastrar', str(exc), parent=win)

        tk.Button(footer_inner, text='Cancelar', command=win.destroy, bg=WHITE, fg=TEXT,
                  bd=1, relief='solid', padx=18, pady=9, cursor='hand2').pack(side='right', padx=(10, 0))
        tk.Button(footer_inner, text='Salvar mercadoria', command=save, bg=NAVY, fg='white',
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
        ttk.Entry(top, textvariable=search).pack(fill='x')
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
                ttk.Entry(win, textvariable=var).pack(fill='x', padx=24, pady=(3, 10))

            def save():
                try:
                    services.set_initial_inventory(pid, int(depot.get()), int(display.get()), self.current_user['id'])
                    win.destroy()
                    fill()
                except Exception as exc:
                    messagebox.showerror('Erro', str(exc), parent=win)

            tk.Button(win, text='Salvar inventário', command=save, bg=NAVY, fg='white', bd=0, pady=9,
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
            search_entry = ttk.Entry(inner, textvariable=search_var)
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
            qty_entry = ttk.Entry(inner, textvariable=qty_var, width=10)
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

            register_btn = tk.Button(inner, text='Registrar', command=save, bg=NAVY, fg='white', bd=0,
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
        tree = ttk.Treeview(box, columns=('date', 'user', 'code', 'desc', 'type', 'qty', 'from', 'to'), show='headings')
        cols = [('date', 'Data', 135), ('user', 'Usuário', 130), ('code', 'Código', 80), ('desc', 'Produto', 255),
                ('type', 'Movimento', 125), ('qty', 'Qtd.', 50), ('from', 'Origem', 80), ('to', 'Destino', 80)]
        for col, title, width in cols:
            tree.heading(col, text=title)
            tree.column(col, width=width, anchor='w')
        for row in services.movements(limit):
            tree.insert('', 'end', values=(row['created_at'], row['user_name'], row['code'], row['description'],
                                           row['movement_type'], row['qty'], row['origin'] or '', row['destination'] or ''))
        tree.pack(fill='both', expand=True)

    def show_history(self):
        self.clear()
        self.header('Histórico', 'Todas as alterações registradas pelo sistema, incluindo o usuário responsável.')
        self._history_table()

    def show_users(self):
        if not self.require(self.can_manage_users()):
            return
        self.clear()
        head = self.header('Usuários', 'Controle quem pode entrar no sistema e qual é o nível de acesso.')
        actions = tk.Frame(head, bg=BG)
        actions.pack(side='right', anchor='e')
        tk.Button(actions, text='+ Novo usuário', command=self.new_user_dialog, bg=NAVY, fg='white', bd=0,
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

        tk.Button(footer, text='Ativar selecionado', command=lambda: toggle(True), bg=SUCCESS, fg='white', bd=0,
                  padx=12, pady=7, cursor='hand2').pack(side='left', padx=(0, 6))
        tk.Button(footer, text='Bloquear selecionado', command=lambda: toggle(False), bg=DANGER, fg='white', bd=0,
                  padx=12, pady=7, cursor='hand2').pack(side='left')

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
            ttk.Entry(form, textvariable=var, show=show).pack(fill='x')
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

        tk.Button(form, text='Criar usuário', command=save, bg=NAVY, fg='white', bd=0, pady=10,
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
        tk.Button(box, text='Verificar atualizações agora', command=self.check_updates_interactive, bg=NAVY, fg='white',
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
