from __future__ import annotations
from typing import Iterable
from database import connect


def normalize(value):
    if value is None:
        return ''
    return str(value).strip()


def create_product(data: dict, depot: int = 0, display: int = 0, user_id: int | None = None) -> int:
    depot, display = int(depot), int(display)
    if depot < 0 or display < 0:
        raise ValueError('Quantidades não podem ser negativas.')
    code = normalize(data.get('code'))
    description = normalize(data.get('description'))
    if not code or not description:
        raise ValueError('Código e descrição são obrigatórios.')
    fields = ['code','description','brand','model','category','color','voltage','barcode','notes']
    values = [normalize(data.get(f)) for f in fields]
    price_raw = data.get('price')
    price = None if price_raw in (None, '') else float(str(price_raw).replace(',', '.'))
    with connect() as conn:
        cur = conn.execute(
            '''INSERT INTO products(code, description, brand, model, category, color, voltage, barcode, notes, price)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', values + [price])
        pid = cur.lastrowid
        conn.execute('INSERT INTO stock(product_id, depot_qty, display_qty) VALUES (?, ?, ?)', (pid,depot,display))
        if depot + display:
            conn.execute('''INSERT INTO movements(product_id, movement_type, qty, reason, user_id)
                            VALUES (?, 'INVENTORY_SET', ?, ?, ?)''',
                         (pid, depot+display, f'Estoque inicial: depósito={depot}, exposição={display}', user_id))
        return pid


def upsert_product(data: dict) -> tuple[int, bool]:
    code = normalize(data.get('code'))
    description = normalize(data.get('description'))
    if not code or not description:
        raise ValueError('Código e descrição são obrigatórios.')
    price_raw = data.get('price')
    price = None if price_raw in (None, '') else float(str(price_raw).replace(',', '.'))
    with connect() as conn:
        row = conn.execute('SELECT id FROM products WHERE code=?', (code,)).fetchone()
        if row:
            pid = row['id']
            conn.execute('''UPDATE products SET description=?, brand=?, model=?, category=?, color=?, voltage=?, barcode=?, notes=?, price=?
                            WHERE id=?''', (
                description, normalize(data.get('brand')), normalize(data.get('model')),
                normalize(data.get('category')), normalize(data.get('color')), normalize(data.get('voltage')),
                normalize(data.get('barcode')), normalize(data.get('notes')), price, pid))
            return pid, False
        cur = conn.execute('''INSERT INTO products(code, description, brand, model, category, color, voltage, barcode, notes, price)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
            code, description, normalize(data.get('brand')), normalize(data.get('model')),
            normalize(data.get('category')), normalize(data.get('color')), normalize(data.get('voltage')),
            normalize(data.get('barcode')), normalize(data.get('notes')), price))
        pid = cur.lastrowid
        conn.execute('INSERT INTO stock(product_id) VALUES (?)', (pid,))
        return pid, True


def list_products(search: str = ''):
    term = f"%{search.strip()}%"
    with connect() as conn:
        return conn.execute('''
            SELECT p.*, s.depot_qty, s.display_qty, (s.depot_qty+s.display_qty) total_qty
            FROM products p JOIN stock s ON s.product_id=p.id
            WHERE p.active=1 AND (p.code LIKE ? OR p.description LIKE ? OR p.brand LIKE ? OR p.model LIKE ? OR p.category LIKE ?)
            ORDER BY p.description
        ''', (term,term,term,term,term)).fetchall()



def search_products(search: str, limit: int = 80):
    """Pesquisa rápida para telas operacionais, priorizando código exato e prefixo do código."""
    query = search.strip()
    if not query:
        return []
    contains = f"%{query}%"
    prefix = f"{query}%"
    limit = max(1, min(int(limit), 200))
    sql = (
        "SELECT p.*, s.depot_qty, s.display_qty, (s.depot_qty+s.display_qty) total_qty "
        "FROM products p JOIN stock s ON s.product_id=p.id "
        "WHERE p.active=1 AND (p.code LIKE ? OR p.description LIKE ? OR p.brand LIKE ? OR p.model LIKE ?) "
        "ORDER BY CASE WHEN LOWER(p.code)=LOWER(?) THEN 0 WHEN p.code LIKE ? THEN 1 ELSE 2 END, p.description "
        "LIMIT ?"
    )
    with connect() as conn:
        return conn.execute(sql, (contains, contains, contains, contains, query, prefix, limit)).fetchall()

def get_product(product_id: int):
    with connect() as conn:
        return conn.execute('''SELECT p.*, s.depot_qty, s.display_qty, (s.depot_qty+s.display_qty) total_qty
                               FROM products p JOIN stock s ON s.product_id=p.id WHERE p.id=?''', (product_id,)).fetchone()


def set_initial_inventory(product_id: int, depot: int, display: int, user_id: int | None = None):
    depot, display = int(depot), int(display)
    if depot < 0 or display < 0:
        raise ValueError('Quantidades não podem ser negativas.')
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        old = conn.execute('SELECT depot_qty, display_qty FROM stock WHERE product_id=?', (product_id,)).fetchone()
        if not old:
            raise ValueError('Produto não encontrado.')
        conn.execute('UPDATE stock SET depot_qty=?, display_qty=?, updated_at=CURRENT_TIMESTAMP WHERE product_id=?',
                     (depot, display, product_id))
        delta = (depot+display) - (old['depot_qty']+old['display_qty'])
        if depot != old['depot_qty'] or display != old['display_qty']:
            changed_qty = abs(delta) or abs(depot-old['depot_qty'])
            conn.execute('''INSERT INTO movements(product_id, movement_type, qty, origin, destination, reason, user_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?)''',
                         (product_id, 'INVENTORY_SET', changed_qty, None, None,
                          f"Ajuste de inventário: depósito {old['depot_qty']} → {depot}; exposição {old['display_qty']} → {display}", user_id))


def move_internal(product_id: int, qty: int, origin: str, destination: str, user_id: int | None = None):
    qty = int(qty)
    if qty <= 0:
        raise ValueError('Quantidade deve ser maior que zero.')
    valid = {'DEPOT', 'DISPLAY'}
    if origin not in valid or destination not in valid or origin == destination:
        raise ValueError('Origem e destino inválidos.')
    with connect() as conn:
        # Lock before reading balances so simultaneous writers cannot use the same stock.
        conn.execute('BEGIN IMMEDIATE')
        s = conn.execute('SELECT depot_qty, display_qty FROM stock WHERE product_id=?', (product_id,)).fetchone()
        if not s:
            raise ValueError('Produto não encontrado.')
        depot, display = s['depot_qty'], s['display_qty']
        if origin == 'DEPOT':
            if depot < qty: raise ValueError('Quantidade insuficiente no depósito.')
            depot -= qty; display += qty
        else:
            if display < qty: raise ValueError('Quantidade insuficiente na exposição.')
            display -= qty; depot += qty
        conn.execute('UPDATE stock SET depot_qty=?, display_qty=?, updated_at=CURRENT_TIMESTAMP WHERE product_id=?',
                     (depot, display, product_id))
        conn.execute('''INSERT INTO movements(product_id, movement_type, qty, origin, destination, user_id)
                        VALUES (?, 'INTERNAL_TRANSFER', ?, ?, ?, ?)''', (product_id, qty, origin, destination, user_id))


def add_stock(product_id: int, qty: int, destination: str = 'DEPOT', reason: str='Entrada de mercadoria', user_id: int | None = None):
    qty = int(qty)
    if qty <= 0: raise ValueError('Quantidade deve ser maior que zero.')
    if destination not in {'DEPOT','DISPLAY'}: raise ValueError('Destino inválido.')
    with connect() as conn:
        col = 'depot_qty' if destination == 'DEPOT' else 'display_qty'
        changed = conn.execute(f'UPDATE stock SET {col}={col}+?, updated_at=CURRENT_TIMESTAMP WHERE product_id=?', (qty, product_id))
        if changed.rowcount != 1:
            raise ValueError('Produto não encontrado.')
        conn.execute('''INSERT INTO movements(product_id, movement_type, qty, origin, destination, reason, user_id)
                        VALUES (?, 'ENTRY', ?, 'EXTERNAL', ?, ?, ?)''', (product_id, qty, destination, reason, user_id))


def dashboard_metrics():
    with connect() as conn:
        return conn.execute('''SELECT COUNT(*) products,
                   COALESCE(SUM(depot_qty+display_qty),0) total_units,
                   COALESCE(SUM(depot_qty),0) depot_units,
                   COALESCE(SUM(display_qty),0) display_units,
                   SUM(CASE WHEN depot_qty>0 AND display_qty=0 THEN 1 ELSE 0 END) no_display,
                   SUM(CASE WHEN depot_qty=0 AND display_qty>0 THEN 1 ELSE 0 END) display_only,
                   SUM(CASE WHEN depot_qty+display_qty=0 THEN 1 ELSE 0 END) out_of_stock
               FROM products p JOIN stock s ON s.product_id=p.id WHERE p.active=1''').fetchone()


def special_list(kind: str):
    where = {
        'no_display': 's.depot_qty>0 AND s.display_qty=0',
        'display_only': 's.depot_qty=0 AND s.display_qty>0',
        'out_of_stock': 's.depot_qty+s.display_qty=0'
    }[kind]
    with connect() as conn:
        return conn.execute(f'''SELECT p.code,p.description,p.brand,s.depot_qty,s.display_qty
                                FROM products p JOIN stock s ON s.product_id=p.id
                                WHERE p.active=1 AND {where} ORDER BY p.description''').fetchall()


def movements(limit=300):
    with connect() as conn:
        return conn.execute('''SELECT m.created_at,p.code,p.description,m.movement_type,m.qty,m.origin,m.destination,m.reason,
                                      COALESCE(u.full_name, 'Sistema') user_name
                               FROM movements m JOIN products p ON p.id=m.product_id
                               LEFT JOIN users u ON u.id=m.user_id
                               ORDER BY m.id DESC LIMIT ?''', (limit,)).fetchall()
