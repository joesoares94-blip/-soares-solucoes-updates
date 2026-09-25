"""Main application screens matching the approved Soares Soluções concept."""
from __future__ import annotations
from pathlib import Path
import tkinter as tk
from tkinter import ttk, font as tkfont
import services
from modern_ui import Button, Entry, Panel, icon, rounded, NAVY, BLUE, BG, TEXT, MUTED, BORDER, WHITE

ROLE_LABELS={'OWNER':'Proprietário','ADMIN':'Administrador','OPERATOR':'Operador','VIEWER':'Consulta'}
LOW_STOCK=5


def label(parent,text,fg=TEXT,font=('Segoe UI',10),**kwargs):
    return tk.Label(parent,text=text,bg=parent.cget('bg'),fg=fg,font=font,**kwargs)


def num(value):return f'{int(value or 0):,}'.replace(',','.')


class ModernMixin:
    def brand_lockup(self, parent, large=False):
        """Keep the approved SS symbol; render the name at readable UI sizes."""
        back=parent.cget('bg')
        row=tk.Frame(parent,bg=back)
        try:
            original=tk.PhotoImage(file=str(Path(__file__).with_name('brand_logo_login.png')))
            crop=tk.PhotoImage()
            w,h=original.width(),original.height()
            self.tk.call(crop,'copy',original,'-from',int(w*.04),int(h*.10),int(w*.34),int(h*.90))
            target=100 if large else 52
            symbol=crop.subsample(max(1,(crop.width()+target-1)//target))
            mark=tk.Label(row,image=symbol,bg=back,bd=0)
            mark.image=symbol
            mark.pack(side='left',padx=(0,14 if large else 8))
        except (tk.TclError,OSError):
            label(row,'SS',WHITE,('Segoe UI',32 if large else 22,'bold')).pack(side='left',padx=(0,10))
        name=tk.Frame(row,bg=back);name.pack(side='left')
        label(name,'SOARES',WHITE,('Segoe UI',-44 if large else -24,'bold')).pack(anchor='w')
        label(name,'SOLUÇÕES',WHITE,('Segoe UI',-27 if large else -16,'bold')).pack(anchor='w')
        return row

    def modern_access_shell(self,title,subtitle):
        shell=tk.Frame(self,bg=NAVY);shell.pack(fill='both',expand=True)
        shell.grid_rowconfigure(0,weight=1)
        shell.grid_columnconfigure(0,weight=1,uniform='access')
        shell.grid_columnconfigure(1,weight=1,uniform='access')
        identity=tk.Canvas(shell,bg=NAVY,bd=0,highlightthickness=0)
        identity.grid(row=0,column=0,sticky='nsew')
        try:
            art=tk.PhotoImage(file=str(Path(__file__).with_name('warehouse_login.png')))
            art=art.subsample(max(1,(art.width()+680-1)//680))
            identity.art=art
        except (tk.TclError,OSError):
            identity.art=None
        def draw_identity(event):
            identity.delete('all')
            w,h=event.width,event.height
            if identity.art:
                identity.create_image(w/2,h/2-12,image=identity.art)
            identity.create_text(38,34,anchor='nw',text='SOARES SOLUÇÕES',fill=WHITE,
                                 font=('Segoe UI',15,'bold'))
            identity.create_text(38,h-86,anchor='nw',text='Tecnologia que simplifica o seu dia a dia.',
                                 fill=WHITE,font=('Segoe UI',15,'bold'))
            identity.create_text(38,h-53,anchor='nw',text='Controle seu estoque com clareza e confiança.',
                                 fill='#C7D9F0',font=('Segoe UI',10))
        identity.bind('<Configure>',draw_identity)
        right=tk.Canvas(shell,bg=NAVY,bd=0,highlightthickness=0)
        right.grid(row=0,column=1,sticky='nsew')
        setup='Configuração' in title
        card_height=585 if setup else 465
        card_width=370
        def draw_right(event):
            right.delete('decoration')
            w,h=event.width,event.height
            steps=max(1,min(w,240))
            for i in range(steps):
                t=i/max(steps-1,1)
                color=f'#{int(9+4*t):02x}{int(29+91*t):02x}{int(87+153*t):02x}'
                x=i*w/steps
                # The reference has broad rounded corners on the left side of the blue panel.
                edge=72-(max(0,72**2-(72-x)**2)**.5) if x<72 else 0
                right.create_rectangle(x,edge,(i+1)*w/steps+1,h-edge,
                                       fill=color,outline=color,tags='decoration')
            height=min(card_height,h-42)
            x1=(w-card_width)/2;y1=(h-height)/2
            self._rounded_shape(right,x1,y1,x1+card_width,y1+height,24,'#0B2464',
                                outline='#EAF4FF',width=2,tags='decoration')
            right.tag_lower('decoration')
            # The frame is already centered with relx/rely=.5. Adding x/y here
            # shifts it another half-panel to the right and hides the login.
            body.place_configure(width=card_width-64,height=height-38)
        right.bind('<Configure>',draw_right)
        body=tk.Frame(right,bg='#0B2464')
        body.place(relx=.5,rely=.5,anchor='center',width=card_width-64,height=card_height-38)
        try:
            full_logo=tk.PhotoImage(file=str(Path(__file__).with_name('brand_logo_login.png')))
            full_logo=full_logo.subsample(max(1,(full_logo.width()+270-1)//270))
            logo=tk.Label(body,image=full_logo,bg='#0B2464',bd=0)
            logo.image=full_logo
            logo.pack(pady=(8,26 if setup else 34))
        except (tk.TclError,OSError):
            self.brand_lockup(body).pack(pady=(16,32))
        if setup:
            label(body,title,WHITE,('Segoe UI',17,'bold'),wraplength=300).pack(anchor='w')
            label(body,subtitle,'#D6E8FF',('Segoe UI',9),wraplength=300,
                  justify='left').pack(anchor='w',pady=(5,10))
        self.access_form=tk.Frame(body,bg='#0B2464');self.access_form.pack(fill='x')
        return self.access_form

    def modern_layout(self):
        self.sidebar=tk.Frame(self,bg=NAVY,width=230)
        self.sidebar.pack(side='left',fill='y');self.sidebar.pack_propagate(False)
        brand=tk.Frame(self.sidebar,bg=NAVY,height=110)
        brand.pack(fill='x',padx=16,pady=(18,12));brand.pack_propagate(False)
        self.brand_lockup(brand).pack(anchor='w')
        label(brand,'Controle de estoque','#B3C5D9',('Segoe UI',9)).pack(anchor='w',padx=4,pady=(10,0))
        bottom=tk.Frame(self.sidebar,bg=NAVY)
        bottom.pack(side='bottom',fill='x',padx=16,pady=16)
        person=tk.Frame(bottom,bg=NAVY);person.pack(fill='x',pady=(0,14))
        full=self.current_user['full_name']
        initials=''.join(p[0] for p in full.split()[:2]).upper()
        avatar=tk.Canvas(person,width=38,height=38,bg=NAVY,highlightthickness=0)
        avatar.pack(side='left',padx=(0,10));avatar.create_oval(1,1,37,37,fill='#365875',outline='')
        avatar.create_text(19,19,text=initials,fill=WHITE,font=('Segoe UI',10,'bold'))
        person_text=tk.Frame(person,bg=NAVY);person_text.pack(side='left',fill='x',expand=True)
        label(person_text,full,WHITE,('Segoe UI',10,'bold'),anchor='w',wraplength=145).pack(anchor='w')
        label(person_text,ROLE_LABELS.get(self.current_user['role'],''),'#B3C5D9',('Segoe UI',9)).pack(anchor='w')
        Button(bottom,text='Sair',command=self.logout,bg='#284763',fg=WHITE,
               activebackground='#355977',icon_name='logout',anchor='w',height=40).pack(fill='x')
        label(bottom,f'Versão {self.APP_VERSION}','#839BB5',('Segoe UI',8)).pack(pady=(9,0))
        items=[('Dashboard','home',self.show_dashboard),('Produtos','box',self.show_products),
               ('Inventário','clipboard',self.show_inventory),('Movimentações','arrows',self.show_movements),
               ('Histórico','clock',self.show_history)]
        if self.can_manage_users():items.append(('Usuários','users',self.show_users))
        items.append(('Atualizações','settings',self.show_updates))
        self._nav_controls={}
        for name,glyph,command in items:
            b=Button(self.sidebar,text=name,command=command,bg=NAVY,fg='#C2D1E2',
                     activebackground='#1F4264',icon_name=glyph,anchor='w',padx=14,
                     font=('Segoe UI',11),height=46)
            b.pack(fill='x',padx=16,pady=3);self._nav_controls[name]=b
        self._nav_buttons={}
        self.content=tk.Frame(self,bg=BG);self.content.pack(side='left',fill='both',expand=True)

    def modern_header(self,title,subtitle=''):
        for name,b in self._nav_controls.items():
            b.fill=BLUE if name==title else NAVY
            b.fg=WHITE if name==title else '#C2D1E2'
            b.hover_fill='#0870DD' if name==title else '#1F4264';b.hover_fg=b.fg;b._paint()
        outer=tk.Frame(self.content,bg=BG);outer.pack(fill='x',padx=24,pady=(17,18))
        breadcrumb=tk.Frame(outer,bg=BG);breadcrumb.pack(fill='x',pady=(0,12))
        home=tk.Canvas(breadcrumb,width=18,height=18,bg=BG,bd=0,highlightthickness=0)
        home.pack(side='left',padx=(0,8));icon(home,'home',0,0,17,BLUE)
        label(breadcrumb,'Visão geral  ›' if title=='Dashboard' else f'Gestão  ›  {title}',MUTED,('Segoe UI',9)).pack(side='left')
        row=tk.Frame(outer,bg=BG);row.pack(fill='x')
        titles=tk.Frame(row,bg=BG);titles.pack(side='left',fill='x',expand=True)
        label(titles,title,TEXT,('Segoe UI',26,'bold')).pack(anchor='w')
        if subtitle:label(titles,subtitle,MUTED,('Segoe UI',10)).pack(anchor='w',pady=(3,0))
        return row

    def _metrics_strip(self,parent,rows):
        strip=tk.Frame(parent,bg=BG);strip.pack(fill='x',padx=24,pady=(0,18))
        totals=[('Produtos cadastrados',len(rows),'box','#EAF3FF',BLUE),
                ('No depósito',sum(r['depot_qty'] for r in rows),'warehouse','#E5F8EF','#13936B'),
                ('Em exposição',sum(r['display_qty'] for r in rows),'store','#F0EAFE','#8551E6'),
                ('Estoque baixo',sum(0<r['total_qty']<=LOW_STOCK for r in rows),'alert','#FFF1DE','#D98A00')]
        for i,(name,value,glyph,back,fore) in enumerate(totals):
            strip.grid_columnconfigure(i,weight=1,uniform='cards')
            p=Panel(strip,padding=14,height=90);p.grid(row=0,column=i,sticky='nsew',padx=(0,12 if i<3 else 0))
            glyphbox=tk.Canvas(p.body,width=42,height=45,bg=WHITE,highlightthickness=0)
            glyphbox.pack(side='left',padx=(0,12));rounded(glyphbox,0,0,41,44,10,back);icon(glyphbox,glyph,9,10,24,fore)
            text=tk.Frame(p.body,bg=WHITE);text.pack(side='left')
            label(text,name,MUTED,('Segoe UI',9),wraplength=118,justify='left').pack(anchor='w')
            label(text,num(value),TEXT,('Segoe UI',22,'bold')).pack(anchor='w',pady=(3,0))

    def modern_dashboard(self):
        self.clear()
        h=self.header('Dashboard','Acompanhe o estoque e as movimentações da sua empresa.')
        if self.can_manage_catalog():Button(h,text='Nova mercadoria',icon_name='plus',command=self.new_product_dialog).pack(side='right',padx=(16,0))
        rows=[dict(r) for r in services.list_products()]
        self._metrics_strip(self.content,rows)
        body=tk.Frame(self.content,bg=BG);body.pack(fill='both',expand=True,padx=24,pady=(0,22))
        body.grid_columnconfigure(0,weight=1);body.grid_columnconfigure(1,minsize=248);body.grid_rowconfigure(0,weight=1)
        stock=Panel(body,padding=16);stock.grid(row=0,column=0,sticky='nsew',padx=(0,16))
        self._stock_screen(stock.body,rows,title='Visão do estoque',dashboard=True)
        side=tk.Frame(body,bg=BG,width=248);side.grid(row=0,column=1,sticky='nsew');side.grid_propagate(False)
        side.grid_columnconfigure(0,weight=1);side.grid_rowconfigure(1,weight=1)
        layout_state={'wide':True}
        def fit_dashboard(event):
            wide=event.width>=1000
            if wide==layout_state['wide']:return
            layout_state['wide']=wide
            if wide:
                side.grid();body.grid_columnconfigure(1,minsize=248);stock.grid_configure(padx=(0,16))
            else:
                side.grid_remove();body.grid_columnconfigure(1,minsize=0);stock.grid_configure(padx=0)
        body.bind('<Configure>',fit_dashboard)
        alerts=Panel(side,padding=16);alerts.grid(row=0,column=0,sticky='ew',pady=(0,14))
        label(alerts.body,'Atenção ao estoque',TEXT,('Segoe UI',12,'bold')).pack(anchor='w',pady=(0,12))
        low=sum(0<r['total_qty']<=LOW_STOCK for r in rows);empty=sum(r['total_qty']==0 for r in rows)
        for count,caption,status,color in [(low,'Estoque baixo (1 a 5)','Baixo','#BD7600'),(empty,'Produtos sem estoque','Zerado','#C33142')]:
            Button(alerts.body,text=f'{num(count)}  {caption}',font=('Segoe UI',9),bg=WHITE,fg=color,
                   command=lambda st=status:self._apply_stock_filter(st),anchor='w',padx=0,height=42,
                   activebackground='#F4F7FB').pack(fill='x')
        recent=Panel(side,padding=16);recent.grid(row=1,column=0,sticky='nsew')
        label(recent.body,'Últimas movimentações',TEXT,('Segoe UI',12,'bold')).pack(anchor='w',pady=(0,12))
        moves=services.movements(limit=3)
        if not moves:label(recent.body,'Nenhuma movimentação registrada.',MUTED,('Segoe UI',9),wraplength=208,justify='left').pack(anchor='w')
        for index,m in enumerate(moves):
            if index:tk.Frame(recent.body,bg=BORDER,height=1).pack(fill='x',pady=11)
            name={'ENTRY':'Entrada de mercadoria','INTERNAL_TRANSFER':'Transferência interna','INVENTORY_SET':'Inventário atualizado'}.get(m['movement_type'],'Movimentação')
            row=tk.Frame(recent.body,bg=WHITE);row.pack(fill='x')
            c=tk.Canvas(row,width=25,height=25,bg=WHITE,highlightthickness=0);c.pack(side='left',anchor='n',padx=(0,8));icon(c,'down' if m['movement_type']=='ENTRY' else 'arrows',0,0,22,BLUE)
            t=tk.Frame(row,bg=WHITE);t.pack(side='left',fill='x',expand=True)
            label(t,name,TEXT,('Segoe UI',9,'bold')).pack(anchor='w')
            label(t,f"{m['qty']} un. • {m['description']}",MUTED,('Segoe UI',9),wraplength=170,justify='left').pack(anchor='w',pady=(4,0))
            label(t,str(m['created_at'])[:16],MUTED,('Segoe UI',8)).pack(anchor='w',pady=(3,0))

    def modern_products(self):
        self.clear();h=self.header('Produtos','Consulte, filtre e organize as mercadorias do seu estoque.')
        if self.can_manage_catalog():Button(h,text='Nova mercadoria',icon_name='plus',command=self.new_product_dialog).pack(side='right',padx=(12,0))
        rows=[dict(r) for r in services.list_products()]
        self._metrics_strip(self.content,rows)
        panel=Panel(self.content,padding=18);panel.pack(fill='both',expand=True,padx=24,pady=(0,22))
        self._stock_screen(panel.body,rows,title='Catálogo de produtos',dashboard=False)

    def _apply_stock_filter(self,value):
        self._stock_filter.set(value);self._stock_page=0;self._render_stock()

    def _stock_screen(self,parent,rows,title,dashboard):
        self._stock_rows=rows;self._stock_page=0;self._stock_sort=('description',False)
        self._stock_dashboard=dashboard;self._stock_page_size=5 if dashboard else 8
        self._stock_filter=tk.StringVar(value='Todos');self._stock_search=tk.StringVar()
        label(parent,title,TEXT,('Segoe UI',15,'bold')).pack(anchor='w',pady=(0,16))
        toolbar=tk.Frame(parent,bg=WHITE);toolbar.pack(fill='x',pady=(0,14))
        entry=Entry(toolbar,textvariable=self._stock_search,width=20,placeholder='Pesquisar por código ou descrição');entry.pack(side='left',fill='x',expand=True,padx=(0,8))
        entry.native.configure(fg=TEXT)
        self._stock_search_entry=entry
        entry.bind('<KeyRelease>',lambda e:self._search_stock())
        entry.bind('<Return>',lambda e:self._search_stock())
        def filters():
            menu=tk.Menu(self,tearoff=0,font=('Segoe UI',10))
            for name in ('Todos','Baixo','Zerado','Sem exposição'):
                caption={'Baixo':'Estoque baixo: 1 a 5 unidades','Zerado':'Sem estoque'}.get(name,name)
                menu.add_command(label=caption,command=lambda v=name:self._apply_stock_filter(v))
            menu.tk_popup(filter_button.winfo_rootx(),filter_button.winfo_rooty()+filter_button.winfo_height())
        filter_button=Button(toolbar,text='Filtros',icon_name='filter',bg='#F1F5FA',fg=TEXT,command=filters,padx=10,height=36)
        filter_button.pack(side='left',padx=(0,7))
        if self.can_manage_catalog():Button(toolbar,text='Importar Excel',icon_name='upload',bg='#F1F5FA',fg=TEXT,command=self.import_excel,padx=10,height=36).pack(side='left',padx=(0,7))
        Button(toolbar,text='Exportar PDF',icon_name='download',bg='#F1F5FA',fg=TEXT,command=self.export_pdf,padx=10,height=36).pack(side='left')
        self._stock_filter_caption=label(parent,'Busca por código, descrição, marca ou categoria',MUTED,('Segoe UI',8))
        self._stock_filter_caption.pack(anchor='w',pady=(0,9))
        self._stock_table=tk.Frame(parent,bg=WHITE)
        footer=tk.Frame(parent,bg=WHITE);footer.pack(side='bottom',fill='x',pady=(12,0))
        self._stock_count=label(footer,'',MUTED,('Segoe UI',9));self._stock_count.pack(side='left')
        self._stock_next=Button(footer,text='›',bg='#F1F5FA',fg=TEXT,command=lambda:self._page_stock(1),width=32,height=32,padx=8)
        self._stock_next.pack(side='right')
        self._stock_page_label=label(footer,'',BLUE,('Segoe UI',10,'bold'));self._stock_page_label.pack(side='right',padx=12)
        self._stock_prev=Button(footer,text='‹',bg='#F1F5FA',fg=TEXT,command=lambda:self._page_stock(-1),width=32,height=32,padx=8)
        self._stock_prev.pack(side='right')
        self._stock_table.pack(fill='both',expand=True)
        row_height=max(42,tkfont.Font(master=self,font=('Segoe UI',9)).metrics('linespace')+20)
        def fit_rows(event):
            limit=5 if self._stock_dashboard else 8
            count=max(1,min(limit,(event.height-35)//row_height))
            if count!=self._stock_page_size:
                self._stock_page_size=count;self._stock_page=0;self._render_stock()
        self._stock_table.bind('<Configure>',fit_rows)
        self._render_stock()

    def _search_stock(self):self._stock_page=0;self._render_stock()
    def _page_stock(self,delta):self._stock_page+=delta;self._render_stock()
    def _sort_stock(self,key):
        old,reverse=self._stock_sort;self._stock_sort=(key,not reverse if old==key else False);self._render_stock()

    def _render_stock(self):
        if not self._stock_table.winfo_exists():return
        term=self._stock_search.get().strip().casefold();flt=self._stock_filter.get()
        rows=[r for r in self._stock_rows if not term or any(term in str(r.get(k) or '').casefold() for k in ('code','description','brand','model','category'))]
        if flt=='Baixo':rows=[r for r in rows if 0<r['total_qty']<=LOW_STOCK]
        elif flt=='Zerado':rows=[r for r in rows if r['total_qty']==0]
        elif flt=='Sem exposição':rows=[r for r in rows if r['depot_qty']>0 and r['display_qty']==0]
        key,reverse=self._stock_sort
        rows.sort(key=lambda r:(str(r.get(key) or '').casefold() if key in ('code','description') else r.get(key) or 0),reverse=reverse)
        pages=max(1,(len(rows)+self._stock_page_size-1)//self._stock_page_size)
        self._stock_page=max(0,min(self._stock_page,pages-1))
        start=self._stock_page*self._stock_page_size;page=rows[start:start+self._stock_page_size]
        for w in self._stock_table.winfo_children():w.destroy()
        columns=[('Código','code',66),('Produto','description',160),('Depósito','depot_qty',70),('Exposição','display_qty',78),('Total','total_qty',48),('Situação',None,104)]
        if not self._stock_dashboard:columns.insert(2,('Preço','price',94))
        for i,(name,key,w) in enumerate(columns):
            self._stock_table.grid_columnconfigure(i,weight=1 if i==1 else 0,minsize=w)
            head=Button(self._stock_table,text=name,command=(lambda k=key:self._sort_stock(k)) if key else None,
                        bg='#F3F6FA',fg=MUTED,font=('Segoe UI',9,'bold'),anchor='w',padx=8,height=35,radius=0,width=w)
            head.grid(row=0,column=i,sticky='ew')
        for row_index,r in enumerate(page,1):
            color=WHITE if row_index%2 else '#FAFCFE'
            vals=[r['code'],r['description'],r['depot_qty'],r['display_qty'],r['total_qty']]
            if not self._stock_dashboard:
                price=r.get('price')
                vals.insert(2,'—' if price is None else ('R$ '+f'{price:,.2f}'.replace(',','X').replace('.',',').replace('X','.')))
            for i,v in enumerate(vals):
                cell=tk.Label(self._stock_table,text=str(v),anchor='w' if i<2 else 'e',bg=color,fg=TEXT,
                              font=('Segoe UI',9),padx=8,pady=10)
                if i==1:cell.configure(width=1)
                cell.grid(row=row_index,column=i,sticky='ew')
            qty=r['total_qty']
            caption,back,fore=('Sem estoque','#FDECEF','#BF3546') if qty==0 else ('Estoque baixo','#FFF3E0','#B47600') if qty<=LOW_STOCK else ('Disponível','#E7F8F0','#128A61')
            box=tk.Frame(self._stock_table,bg=color);box.grid(row=row_index,column=len(columns)-1,sticky='nsew')
            chip=Button(box,text=caption,bg=back,fg=fore,font=('Segoe UI',8),height=28,padx=8,radius=7)
            chip.pack(anchor='center',pady=7)
        if not page:label(self._stock_table,'Nenhum produto encontrado.',MUTED).grid(row=1,column=0,columnspan=len(columns),pady=45)
        self._stock_count.configure(text=f'{start+1 if page else 0}–{start+len(page)} de {num(len(rows))} produtos')
        self._stock_page_label.configure(text=f'{self._stock_page+1} / {pages}')
        self._stock_prev.configure(state='normal' if self._stock_page else 'disabled')
        self._stock_next.configure(state='normal' if self._stock_page<pages-1 else 'disabled')
        self._stock_filter_caption.configure(text='Busca por código, descrição, marca ou categoria' if flt=='Todos' else f'Filtro ativo: {flt}' + (' (1 a 5 unidades)' if flt=='Baixo' else ''))
