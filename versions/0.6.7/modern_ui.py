"""Shared visual controls. Text editing stays in native Tk entries."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, font as tkfont
import base64
import struct
import zlib

NAVY = '#102D4B'
BLUE = '#087AF5'
BG = '#F3F6FA'
TEXT = '#162740'
MUTED = '#60738E'
BORDER = '#E1E8F0'
WHITE = '#FFFFFF'


def _png_rgba(width, height, rows):
    """Encode tiny antialiased assets with the Python standard library."""
    def chunk(kind, data):
        return (struct.pack('!I', len(data)) + kind + data +
                struct.pack('!I', zlib.crc32(kind + data) & 0xffffffff))
    raw = b''.join(b'\0' + row for row in rows)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', width, height, 8, 6, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


def _coverage(x, y, width, height, radius):
    """4x4 subpixel coverage of a rounded rectangle at a single pixel."""
    if radius <= 0 or (radius <= x < width-radius) or (radius <= y < height-radius):
        return 255
    cx = radius if x < radius else width-radius
    cy = radius if y < radius else height-radius
    count = 0
    for sy in range(4):
        for sx in range(4):
            dx = x + (sx+.5)/4 - cx
            dy = y + (sy+.5)/4 - cy
            count += dx*dx + dy*dy <= radius*radius
    return round(count*255/16)


def _corner_png(radius, fill, left, top):
    rgb = tuple(int(fill[i:i+2], 16) for i in (1, 3, 5))
    rows = []
    for y in range(radius):
        row = bytearray()
        for x in range(radius):
            # The inner edge of a right/bottom corner starts at the circle's
            # center. Reversing this axis made the corners bulge into the UI.
            px = x if left else radius+x
            py = y if top else radius+y
            row.extend((*rgb, _coverage(px, py, 2*radius, 2*radius, radius)))
        rows.append(bytes(row))
    return _png_rgba(radius, radius, rows)


def rounded(canvas, x1, y1, x2, y2, radius=10, fill=WHITE, tag='surface'):
    """Draw solid centers and smooth, transparent PNG corners on a Tk canvas."""
    x1, y1, x2, y2 = map(round, (x1, y1, x2, y2))
    if x2 <= x1 or y2 <= y1 or not fill:
        return
    r = max(0, min(round(radius), (x2-x1)//2, (y2-y1)//2))
    opts = dict(fill=fill, outline='', tags=tag)
    if not r:
        return canvas.create_rectangle(x1, y1, x2, y2, **opts)
    canvas.create_rectangle(x1+r, y1, x2-r, y2, **opts)
    canvas.create_rectangle(x1, y1+r, x2, y2-r, **opts)
    assets = canvas.__dict__.setdefault('_rounded_assets', {})
    for left, top, x, y in ((True, True, x1, y1), (False, True, x2-r, y1),
                            (True, False, x1, y2-r), (False, False, x2-r, y2-r)):
        key = (r, fill, left, top)
        if key not in assets:
            data = base64.b64encode(_corner_png(r, fill, left, top)).decode('ascii')
            assets[key] = tk.PhotoImage(master=canvas, data=data, format='png')
        canvas.create_image(x, y, image=assets[key], anchor='nw', tags=tag)


def gradient_capsule(canvas, width, height, radius, start, end, tag='gradient'):
    """One antialiased gradient image avoids stripe and outline stair steps."""
    width, height = int(width), int(height)
    if width < 2 or height < 2:
        return
    a = tuple(int(start[i:i+2], 16) for i in (1, 3, 5))
    b = tuple(int(end[i:i+2], 16) for i in (1, 3, 5))
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            t = x / max(width-1, 1)
            color = tuple(round(v+(b[i]-v)*t) for i, v in enumerate(a))
            row.extend((*color, _coverage(x, y, width, height, radius)))
        rows.append(bytes(row))
    data = base64.b64encode(_png_rgba(width, height, rows)).decode('ascii')
    canvas._gradient_image = tk.PhotoImage(master=canvas, data=data, format='png')
    canvas.create_image(0, 0, image=canvas._gradient_image, anchor='nw', tags=tag)


def shade_band(canvas, width, height=190, top=True):
    """A smooth navy vignette for legible white copy over a busy photograph."""
    width, height = int(width), int(height)
    rows = []
    for y in range(height):
        distance = y if top else height-1-y
        opacity = 210 if distance <= 90 else round(210*max(0, height-1-distance)/(height-1-90))
        rows.append(bytes((7, 25, 53, opacity))*width)
    data = base64.b64encode(_png_rgba(width, height, rows)).decode('ascii')
    return tk.PhotoImage(master=canvas, data=data, format='png')


def icon(canvas, name, x, y, size=22, color=MUTED, tag='icon'):
    scale = size / 24
    def line(*pts):
        canvas.create_line(*[x+p*scale if i%2==0 else y+p*scale for i,p in enumerate(pts)],
                           fill=color, width=1.6, capstyle='round', joinstyle='round', tags=tag)
    def rect(a,b,c,d):
        canvas.create_rectangle(x+a*scale,y+b*scale,x+c*scale,y+d*scale,outline=color,width=1.5,tags=tag)
    def oval(a,b,c,d):
        canvas.create_oval(x+a*scale,y+b*scale,x+c*scale,y+d*scale,outline=color,width=1.6,tags=tag)
    if name=='home':
        line(2,11,12,3,22,11);line(5,10,5,21,10,21,10,15,14,15,14,21,19,21,19,10)
    elif name=='box':
        line(3,7,12,2,21,7,21,18,12,23,3,18,3,7,12,12,21,7);line(12,12,12,23);line(7,4,17,9)
    elif name=='warehouse':
        line(2,10,12,3,22,10,22,22,2,22,2,10);rect(6,12,18,22);line(7,16,17,16);line(7,19,17,19)
    elif name=='store':
        rect(4,10,20,22);line(2,10,5,3,19,3,22,10,2,10);rect(9,15,15,22)
    elif name=='clipboard':
        rect(5,4,20,22);rect(9,2,16,6);line(9,11,16,11);line(9,16,16,16)
    elif name=='arrows':
        line(3,7,21,7,17,3);line(21,17,3,17,7,21)
    elif name=='clock':
        oval(2,2,22,22);line(12,6,12,12,17,12)
    elif name=='users':
        oval(8,2,16,10);line(4,22,4,17,8,13,16,13,20,17,20,22);line(20,4,23,8,20,11)
    elif name=='settings':
        oval(3,3,21,21);oval(9,9,15,15)
        for a,b,c,d in [(12,0,12,4),(12,20,12,24),(0,12,4,12),(20,12,24,12)]:line(a,b,c,d)
    elif name=='logout':
        line(10,3,3,3,3,21,10,21);line(9,12,22,12,17,7);line(22,12,17,17)
    elif name=='search':
        oval(3,2,17,16);line(15,15,22,22)
    elif name=='plus':
        line(12,4,12,20);line(4,12,20,12)
    elif name=='filter':
        line(2,4,22,4,14,13,14,21,10,18,10,13,2,4)
    elif name in ('download','upload'):
        line(3,17,3,22,21,22,21,17)
        if name=='download':line(12,2,12,16,7,11);line(12,16,17,11)
        else:line(12,17,12,3,7,8);line(12,3,17,8)
    elif name=='alert':
        line(12,2,23,21,1,21,12,2);line(12,8,12,14);oval(11.5,17,12.5,18)
    elif name=='empty':
        oval(2,2,22,22);line(5,5,19,19)
    elif name=='down':
        line(12,2,12,22,5,15);line(12,22,19,15)
    elif name=='right':
        line(2,12,22,12,15,5);line(22,12,15,19)
    else:
        rect(4,3,20,21);line(8,9,16,9);line(8,14,16,14)


class Button(tk.Canvas):
    def __init__(self, master, text='', command=None, bg=BLUE, fg=WHITE,
                 activebackground=None, activeforeground=None, font=('Segoe UI',10),
                 padx=14, pady=9, anchor='center', bd=0, relief=None, cursor='hand2',
                 icon_name=None, radius=9, height=None, width=None, state='normal', **kwargs):
        self.label=text;self.command=command;self.fill=bg;self.fg=fg
        self.hover_fill=activebackground or ('#066BDA' if bg==BLUE else bg)
        self.hover_fg=activeforeground or fg;self.font=font;self.radius=radius
        self.icon_name=icon_name;self.align=anchor;self.padx=padx
        self.enabled=state!='disabled';self.hover=False;self.pressed=False
        f=tkfont.Font(master=master,font=font)
        self._natural_width=width or (f.measure(text)+2*padx+(28 if icon_name else 0))
        h=height or max(34,f.metrics('linespace')+2*pady)
        super().__init__(master,width=self._natural_width,height=h,bg=master.cget('bg'),
                         highlightthickness=0,bd=0,takefocus=1,cursor=cursor)
        self.bind('<Configure>',self._paint)
        self.bind('<Enter>',lambda e:self._hover(True))
        self.bind('<Leave>',lambda e:self._hover(False))
        self.bind('<ButtonPress-1>',self._press)
        self.bind('<ButtonRelease-1>',self._release)
        self.bind('<Return>',lambda e:self.invoke())
        self.bind('<space>',lambda e:self.invoke())
        self.bind('<FocusIn>',self._paint);self.bind('<FocusOut>',self._paint)

    def _hover(self,value):
        self.hover=value;self._paint()

    def _press(self,event):
        if self.enabled:self.pressed=True;self.focus_set()

    def _release(self,event):
        pressed=self.pressed;self.pressed=False
        if pressed and 0<=event.x<self.winfo_width() and 0<=event.y<self.winfo_height():self.invoke()

    def invoke(self):
        if self.enabled and self.command:return self.command()

    def _paint(self,event=None):
        tk.Canvas.delete(self,'all')
        w,h=self.winfo_width(),self.winfo_height()
        if min(w,h)<3:return
        focus=self.focus_get() is self
        if focus:rounded(self,0,0,w,h,self.radius+1,'#79B6FF')
        fill=(self.hover_fill if self.hover else self.fill) if self.enabled else '#E6EBF2'
        rounded(self,2 if focus else 0,2 if focus else 0,w-(2 if focus else 0),h-(2 if focus else 0),self.radius,fill)
        fg=(self.hover_fg if self.hover else self.fg) if self.enabled else '#8392A5'
        f=tkfont.Font(master=self,font=self.font)
        total=f.measure(self.label)+(28 if self.icon_name else 0)
        left=self.padx if self.align=='w' else (w-total)/2
        if self.icon_name:icon(self,self.icon_name,left,(h-19)/2,19,fg);left+=28
        self.create_text(left,h/2,text=self.label,anchor='w',font=self.font,fill=fg)

    def configure(self,cnf=None,**kwargs):
        opts=dict(cnf or {});opts.update(kwargs)
        mapping={'text':'label','command':'command','bg':'fill','background':'fill','fg':'fg','foreground':'fg','font':'font'}
        for k,a in mapping.items():
            if k in opts:setattr(self,a,opts.pop(k))
        if 'state' in opts:self.enabled=opts.pop('state')!='disabled'
        result=super().configure(**opts) if opts else None
        if hasattr(self,'label'):self._paint()
        return result
    config=configure


class Panel(tk.Frame):
    def __init__(self,master,padding=16,fill=WHITE,radius=12,**kwargs):
        super().__init__(master,bg=master.cget('bg'),**kwargs)
        self.fill=fill;self.radius=radius
        self.canvas=tk.Canvas(self,bg=self.cget('bg'),bd=0,highlightthickness=0)
        self.canvas.place(x=0,y=0,relwidth=1,relheight=1)
        self.body=tk.Frame(self,bg=fill)
        self.body.pack(fill='both',expand=True,padx=padding,pady=padding)
        self.canvas.bind('<Configure>',self._paint)
    def _paint(self,event=None):
        self.canvas.delete('all')
        rounded(self.canvas,0,0,self.winfo_width()-1,self.winfo_height()-1,self.radius,self.fill)


class Entry(tk.Frame):
    """Composed control: Canvas drawing never calls Entry.delete/insert."""
    def __init__(self,master,textvariable=None,width=24,show=None,placeholder='',**kwargs):
        super().__init__(master,bg=master.cget('bg'),width=max(80,width*8+24),height=36)
        self.pack_propagate(False);self.grid_propagate(False)
        self.canvas=tk.Canvas(self,bg=self.cget('bg'),highlightthickness=0,bd=0)
        self.canvas.place(x=0,y=0,relwidth=1,relheight=1)
        self.variable=textvariable if textvariable is not None else tk.StringVar(master=self)
        self.native=tk.Entry(self,textvariable=self.variable,show=show,relief='flat',bd=0,
                             highlightthickness=0,bg=WHITE,fg=TEXT,insertbackground=TEXT,
                             font=('Segoe UI',10),**kwargs)
        self.native.place(x=12,y=6,relwidth=1,width=-24,relheight=1,height=-12)
        self.canvas.bind('<Configure>',self._paint)
        self.canvas.bind('<Button-1>',lambda e:self.native.focus_set())
        self.native.bind('<FocusIn>',self._paint,add='+');self.native.bind('<FocusOut>',self._paint,add='+')
        if placeholder:
            self.hint=tk.Label(self,text=placeholder,bg=WHITE,fg=MUTED,font=('Segoe UI',9),anchor='w',bd=0)
            def hint_state(*args):
                if not self.variable.get() and self.focus_get() is not self.native:self.hint.place(x=12,y=7,relwidth=1,width=-24,height=22)
                else:self.hint.place_forget()
            self.hint.bind('<Button-1>',lambda e:self.native.focus_set())
            self.native.bind('<FocusIn>',hint_state,add='+');self.native.bind('<FocusOut>',hint_state,add='+')
            self.variable.trace_add('write',hint_state)
            hint_state()

    def _paint(self,event=None):
        self.canvas.delete('all')
        w,h=self.winfo_width(),self.winfo_height()
        border=BLUE if self.focus_get() is self.native else BORDER
        rounded(self.canvas,0,0,w-1,h-1,8,border)
        rounded(self.canvas,1,1,w-2,h-2,7,WHITE)

    def bind(self,sequence=None,func=None,add=None):
        return self.native.bind(sequence,func,add)
    def focus_set(self):return self.native.focus_set()
    def get(self):return self.native.get()
    def insert(self,*args):return self.native.insert(*args)
    def delete(self,*args):return self.native.delete(*args)
    def selection_range(self,*args):return self.native.selection_range(*args)
    def selection_present(self):return self.native.selection_present()
    def index(self,*args):return self.native.index(*args)
    def icursor(self,*args):return self.native.icursor(*args)


def configure_style(root):
    style=ttk.Style(root);style.theme_use('clam')
    style.configure('Treeview',background=WHITE,fieldbackground=WHITE,foreground=TEXT,
                    rowheight=38,borderwidth=0,font=('Segoe UI',10))
    style.configure('Treeview.Heading',background='#F4F7FB',foreground=MUTED,
                    font=('Segoe UI',10,'bold'),relief='flat',padding=(8,10))
    style.map('Treeview',background=[('selected','#DCEBFF')],foreground=[('selected',TEXT)])
    style.map('Treeview.Heading',background=[('active','#EAF0F8')])
    style.configure('TCombobox',padding=7,arrowsize=16,fieldbackground=WHITE,bordercolor=BORDER,relief='flat')
    style.map('TCombobox',fieldbackground=[('readonly',WHITE)],foreground=[('readonly',TEXT)])
    style.configure('TEntry',padding=7)
    style.configure('TScrollbar',background='#D6DFEA',troughcolor=BG,borderwidth=0,arrowsize=12)


class ScrollArea(tk.Frame):
    def __init__(self,master,bg=BG):
        super().__init__(master,bg=bg)
        self.canvas=tk.Canvas(self,bg=bg,highlightthickness=0,bd=0)
        bar=ttk.Scrollbar(self,orient='vertical',command=self.canvas.yview)
        bar.pack(side='right',fill='y');self.canvas.pack(side='left',fill='both',expand=True)
        self.canvas.configure(yscrollcommand=bar.set)
        self.body=tk.Frame(self.canvas,bg=bg)
        item=self.canvas.create_window(0,0,window=self.body,anchor='nw')
        self.body.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>',lambda e:self.canvas.itemconfigure(item,width=e.width))
        top=self.winfo_toplevel()
        top.bind('<MouseWheel>',lambda e:self.canvas.yview_scroll(-int(e.delta/120),'units') if self.winfo_exists() else None,add='+')
