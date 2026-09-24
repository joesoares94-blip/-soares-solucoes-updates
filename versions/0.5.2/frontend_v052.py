from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
import types

NAVY = '#0F2747'
NAVY2 = '#1F4E79'
TEXT = '#172B4D'
MUTED = '#667085'
WHITE = '#FFFFFF'
DANGER = '#B42318'
ACCENT = '#2F80FF'
GRADIENT_START = '#0B1F5E'
GRADIENT_END = '#2BB3FF'
PINK = '#FF3B8D'
PHOTO_B64 = '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[... ELLIPSIZATION ...]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'


def _draw_gradient(self, canvas, color1, color2, width, height):
    def rgb(v):
        v=v.lstrip('#'); return tuple(int(v[i:i+2],16) for i in (0,2,4))
    r1,g1,b1=rgb(color1); r2,g2,b2=rgb(color2)
    for i in range(max(width,1)):
        p=i/max(width-1,1)
        c=f'#{int(r1+(r2-r1)*p):02x}{int(g1+(g2-g1)*p):02x}{int(b1+(b2-b1)*p):02x}'
        canvas.create_line(i,0,i,height,fill=c)


def _access_shell(self, title, subtitle):
    shell=tk.Frame(self,bg=WHITE); shell.pack(fill='both',expand=True)
    left=tk.Frame(shell,bg=WHITE); left.pack(side='left',fill='both',expand=True,padx=(36,16),pady=22)
    tk.Label(left,text='SOARES',bg=WHITE,fg=NAVY,font=('Segoe UI',34,'bold')).pack(anchor='w',pady=(5,0))
    tk.Label(left,text='SOLUÇÕES',bg=WHITE,fg=NAVY2,font=('Segoe UI',18,'bold')).pack(anchor='w',pady=(0,14))
    tk.Label(left,text='Nós da Soares Soluções
temos o objetivo de',bg=WHITE,fg=NAVY,justify='left',font=('Segoe UI',22,'bold')).pack(anchor='w')
    tk.Label(left,text='facilitar o seu dia a dia,
inovando em tecnologia
e soluções.',bg=WHITE,fg=ACCENT,justify='left',font=('Segoe UI',22,'bold')).pack(anchor='w',pady=(2,12))
    body=tk.Frame(left,bg=WHITE); body.pack(fill='both',expand=True)
    features=tk.Frame(body,bg=WHITE); features.pack(side='left',anchor='n',pady=(35,0),padx=(0,10))
    for icon,t,d in [('⚙','Tecnologia','que simplifica'),('▥','Soluções','que geram resultados'),('👥','Parceria','em cada etapa')]:
        row=tk.Frame(features,bg=WHITE); row.pack(anchor='w',pady=10)
        tk.Label(row,text=icon,bg='#ECF3FF',fg=ACCENT,font=('Segoe UI Emoji',18),width=2).pack(side='left',padx=(0,10))
        tx=tk.Frame(row,bg=WHITE); tx.pack(side='left')
        tk.Label(tx,text=t,bg=WHITE,fg=NAVY,font=('Segoe UI',11,'bold')).pack(anchor='w')
        tk.Label(tx,text=d,bg=WHITE,fg=MUTED,font=('Segoe UI',10)).pack(anchor='w')
    try:
        self.login_photo_img=tk.PhotoImage(data=PHOTO_B64)
        tk.Label(body,image=self.login_photo_img,bg=WHITE).pack(side='right',anchor='s',padx=(0,10),pady=(8,0))
    except Exception:
        pass
    tk.Label(left,text='MAIS QUE SISTEMAS,
SOLUÇÕES PARA O SEU CRESCIMENTO.',bg=WHITE,fg=MUTED,justify='left',font=('Segoe UI',10,'bold')).pack(anchor='w',pady=(8,0))
    right=tk.Frame(shell,bg=WHITE,width=430); right.pack(side='right',fill='y',padx=(8,24),pady=22); right.pack_propagate(False)
    canvas=tk.Canvas(right,width=430,height=680,highlightthickness=0,bd=0); canvas.pack(fill='both',expand=True)
    _draw_gradient(self,canvas,GRADIENT_START,GRADIENT_END,430,680)
    box=tk.Frame(canvas,bg=GRADIENT_START,padx=24,pady=22,highlightthickness=2,highlightbackground=WHITE)
    canvas.create_window(215,340,window=box,width=340,height=470)
    tk.Label(box,text='SOARES',bg=GRADIENT_START,fg=WHITE,font=('Segoe UI',27,'bold')).pack(anchor='center',pady=(8,0))
    tk.Label(box,text='SOLUÇÕES',bg=GRADIENT_START,fg='#D6E6FF',font=('Segoe UI',16,'bold')).pack(anchor='center',pady=(0,18))
    tk.Label(box,text=title,bg=GRADIENT_START,fg=WHITE,font=('Segoe UI',18,'bold')).pack(anchor='w')
    tk.Label(box,text=subtitle,bg=GRADIENT_START,fg='#D6E6FF',wraplength=280,justify='left',font=('Segoe UI',10)).pack(anchor='w',pady=(4,16))
    form=tk.Frame(box,bg=GRADIENT_START); form.pack(fill='both',expand=True); return form


def _labeled_entry(self,parent,label,variable,show=None):
    bg=parent.cget('bg'); fg=WHITE if bg==GRADIENT_START else TEXT
    tk.Label(parent,text=label,bg=bg,fg=fg,font=('Segoe UI',9)).pack(anchor='w',pady=(7,3))
    e=ttk.Entry(parent,textvariable=variable,show=show); e.pack(fill='x'); return e


def show_login(self):
    import auth
    panel=self._access_shell('Entrar no sistema','Informe seu usuário e senha para acessar o estoque.')
    username=tk.StringVar(); password=tk.StringVar()
    user_entry=self._labeled_entry(panel,'Usuário',username); pass_entry=self._labeled_entry(panel,'Senha',password,show='•')
    status=tk.Label(panel,text='',bg=GRADIENT_START,fg='#FFD6D6',font=('Segoe UI',9)); status.pack(anchor='w',pady=(7,0))
    def login(_event=None):
        user=auth.authenticate(username.get(),password.get())
        if not user: status.configure(text='Usuário ou senha inválidos.'); return
        self.current_user=user; self.build_main_ui()
    tk.Button(panel,text='Entrar',command=login,bg=PINK,fg='white',activebackground='#E52F7B',activeforeground='white',bd=0,pady=11,font=('Segoe UI',10,'bold'),cursor='hand2').pack(fill='x',pady=(12,0))
    user_entry.bind('<Return>',lambda e:pass_entry.focus_set()); pass_entry.bind('<Return>',login); user_entry.focus_set()


def show_first_owner_setup(self):
    import auth
    panel=self._access_shell('Configuração inicial','Crie a conta principal do sistema. Ela terá o perfil Proprietário e controle sobre os demais usuários.')
    full_name=tk.StringVar(); username=tk.StringVar(); password=tk.StringVar(); confirm=tk.StringVar()
    self._labeled_entry(panel,'Seu nome',full_name); self._labeled_entry(panel,'Usuário',username); self._labeled_entry(panel,'Senha',password,show='•'); self._labeled_entry(panel,'Confirmar senha',confirm,show='•')
    def save_owner():
        if password.get()!=confirm.get(): messagebox.showerror('Senha','As duas senhas não são iguais.'); return
        try:
            auth.create_first_owner(username.get(),full_name.get(),password.get()); messagebox.showinfo('Conta criada','Conta de Proprietário criada. Faça o primeiro login.'); self.show_access_screen()
        except Exception as exc: messagebox.showerror('Não foi possível criar a conta',str(exc))
    tk.Button(panel,text='Criar conta principal',command=save_owner,bg=PINK,fg='white',activebackground='#E52F7B',activeforeground='white',bd=0,pady=11,font=('Segoe UI',10,'bold'),cursor='hand2').pack(fill='x',pady=(16,0))


def apply(app):
    cls=app.__class__
    cls._draw_gradient=_draw_gradient
    cls._access_shell=_access_shell
    cls._labeled_entry=_labeled_entry
    cls.show_login=show_login
    cls.show_first_owner_setup=show_first_owner_setup
    try:
        import sys
        sys.modules['__main__'].VERSION='0.5.2'
    except Exception:
        pass
    app.show_access_screen()
