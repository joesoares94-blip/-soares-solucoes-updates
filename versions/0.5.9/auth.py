from __future__ import annotations
import hashlib
import hmac
import secrets
from database import connect

ITERATIONS = 310_000
ROLES = {'OWNER', 'ADMIN', 'OPERATOR', 'VIEWER'}


def _hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    if not isinstance(password, str) or len(password) < 6:
        raise ValueError('A senha deve ter pelo menos 6 caracteres.')
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, ITERATIONS)
    return digest.hex(), salt.hex()


def has_users() -> bool:
    with connect() as conn:
        return conn.execute('SELECT 1 FROM users LIMIT 1').fetchone() is not None


def create_user(username: str, full_name: str, password: str, role: str = 'OPERATOR') -> int:
    username = (username or '').strip()
    full_name = (full_name or '').strip()
    role = (role or '').upper().strip()
    if len(username) < 3:
        raise ValueError('O usuário deve ter pelo menos 3 caracteres.')
    if not full_name:
        raise ValueError('Informe o nome do usuário.')
    if role not in ROLES:
        raise ValueError('Perfil de acesso inválido.')
    pwd_hash, salt = _hash_password(password)
    with connect() as conn:
        try:
            cur = conn.execute('''INSERT INTO users(username, full_name, password_hash, password_salt, role)
                                  VALUES (?, ?, ?, ?, ?)''', (username, full_name, pwd_hash, salt, role))
        except Exception as exc:
            if 'UNIQUE' in str(exc).upper():
                raise ValueError('Esse nome de usuário já existe.') from exc
            raise
        return cur.lastrowid


def create_first_owner(username: str, full_name: str, password: str) -> int:
    if has_users():
        raise ValueError('O usuário proprietário já foi configurado.')
    return create_user(username, full_name, password, 'OWNER')


def authenticate(username: str, password: str):
    username = (username or '').strip()
    with connect() as conn:
        row = conn.execute('''SELECT id, username, full_name, password_hash, password_salt, role, active
                              FROM users WHERE username=? COLLATE NOCASE''', (username,)).fetchone()
        if not row or not row['active']:
            return None
        try:
            candidate, _ = _hash_password(password, row['password_salt'])
        except ValueError:
            return None
        if not hmac.compare_digest(candidate, row['password_hash']):
            return None
        conn.execute('UPDATE users SET last_login=CURRENT_TIMESTAMP WHERE id=?', (row['id'],))
        return dict(row)


def list_users():
    with connect() as conn:
        return conn.execute('''SELECT id, username, full_name, role, active, created_at, last_login
                               FROM users ORDER BY CASE role WHEN 'OWNER' THEN 0 WHEN 'ADMIN' THEN 1 ELSE 2 END, full_name''').fetchall()


def set_user_active(user_id: int, active: bool, actor_user_id: int):
    with connect() as conn:
        target = conn.execute('SELECT id, role FROM users WHERE id=?', (user_id,)).fetchone()
        actor = conn.execute('SELECT id, role FROM users WHERE id=?', (actor_user_id,)).fetchone()
        if not target or not actor:
            raise ValueError('Usuário não encontrado.')
        if target['role'] == 'OWNER':
            raise ValueError('O usuário proprietário não pode ser desativado.')
        if actor['role'] not in {'OWNER', 'ADMIN'}:
            raise PermissionError('Você não tem permissão para alterar usuários.')
        conn.execute('UPDATE users SET active=? WHERE id=?', (1 if active else 0, user_id))


def set_user_role(user_id: int, role: str, actor_user_id: int):
    role = (role or '').upper().strip()
    if role not in {'ADMIN', 'OPERATOR', 'VIEWER'}:
        raise ValueError('Selecione um perfil válido: Administrador, Operador ou Consulta.')
    with connect() as conn:
        actor = conn.execute('SELECT role FROM users WHERE id=? AND active=1', (actor_user_id,)).fetchone()
        if not actor or actor['role'] != 'OWNER':
            raise PermissionError('Apenas o Proprietário pode alterar perfis de usuários.')
        target = conn.execute('SELECT role FROM users WHERE id=?', (user_id,)).fetchone()
        if not target:
            raise ValueError('Usuário não encontrado.')
        if target['role'] == 'OWNER':
            raise ValueError('O perfil Proprietário não pode ser alterado.')
        conn.execute('UPDATE users SET role=? WHERE id=?', (role, user_id))


def change_password(user_id: int, new_password: str):
    pwd_hash, salt = _hash_password(new_password)
    with connect() as conn:
        conn.execute('UPDATE users SET password_hash=?, password_salt=? WHERE id=?', (pwd_hash, salt, user_id))


def create_user_authorized(actor_user_id: int, username: str, full_name: str, password: str, role: str = 'OPERATOR') -> int:
    role = (role or '').upper().strip()
    with connect() as conn:
        actor = conn.execute('SELECT role FROM users WHERE id=? AND active=1', (actor_user_id,)).fetchone()
        if not actor or actor['role'] not in {'OWNER', 'ADMIN'}:
            raise PermissionError('Você não tem permissão para criar usuários.')
        if role == 'OWNER':
            raise PermissionError('O perfil Proprietário é exclusivo da configuração inicial.')
    return create_user(username, full_name, password, role)
