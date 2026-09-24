import os
import tempfile
import unittest

_data_dir = tempfile.TemporaryDirectory()
os.environ['SOARES_SOLUCOES_DATA_DIR'] = _data_dir.name

import auth
from database import connect, init_db


class RoleChangeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.owner_id = auth.create_first_owner('owner', 'Proprietário', 'senha123')
        cls.admin_id = auth.create_user_authorized(cls.owner_id, 'admin', 'Administrador', 'senha123', 'ADMIN')
        cls.operator_id = auth.create_user_authorized(cls.owner_id, 'operator', 'Operador', 'senha123', 'OPERATOR')
        cls.viewer_id = auth.create_user_authorized(cls.owner_id, 'viewer', 'Consulta', 'senha123', 'VIEWER')

    def test_owner_changes_standard_roles_and_login_reflects_change(self):
        for role in ('ADMIN', 'VIEWER', 'OPERATOR'):
            auth.set_user_role(self.operator_id, role, self.owner_id)
            self.assertEqual(auth.authenticate('operator', 'senha123')['role'], role)

    def test_other_users_cannot_change_roles(self):
        for actor in (self.admin_id, self.operator_id, self.viewer_id, 99999):
            with self.assertRaises(PermissionError):
                auth.set_user_role(self.viewer_id, 'ADMIN', actor)

    def test_inactive_owner_cannot_change_roles(self):
        with connect() as conn:
            conn.execute('UPDATE users SET active=0 WHERE id=?', (self.owner_id,))
        try:
            with self.assertRaises(PermissionError):
                auth.set_user_role(self.viewer_id, 'ADMIN', self.owner_id)
        finally:
            with connect() as conn:
                conn.execute('UPDATE users SET active=1 WHERE id=?', (self.owner_id,))

    def test_owner_role_remains_exclusive(self):
        with self.assertRaises(ValueError):
            auth.set_user_role(self.owner_id, 'ADMIN', self.owner_id)
        with self.assertRaises(ValueError):
            auth.set_user_role(self.viewer_id, 'OWNER', self.owner_id)
        self.assertEqual(auth.authenticate('owner', 'senha123')['role'], 'OWNER')

    def test_invalid_or_missing_target_keeps_existing_role(self):
        for role in ('', 'SUPERUSER'):
            with self.assertRaises(ValueError):
                auth.set_user_role(self.viewer_id, role, self.owner_id)
        with self.assertRaises(ValueError):
            auth.set_user_role(99999, 'ADMIN', self.owner_id)
        self.assertEqual(auth.authenticate('viewer', 'senha123')['role'], 'VIEWER')


if __name__ == '__main__':
    unittest.main()
