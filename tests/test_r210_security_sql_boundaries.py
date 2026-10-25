"""Adversarial identifier and value checks for reviewed dynamic SQLite queries."""
import pytest
from app import auth,account_lifecycle as life
from test_r210_account_lifecycle import env as env  # noqa: F401


@pytest.mark.parametrize('key',['sandbox_days=1 WHERE id=1; DROP TABLE users; --','project_days"','user_id'])
def test_retention_identifier_allowlist_rejects_request_sql(env,key):
    with pytest.raises(ValueError):life.settings({key:10})
    with auth.db() as c:assert c.execute('SELECT count(*) FROM users').fetchone()[0]==2


def test_schema_quotes_and_fk_columns_do_not_become_sql(env):
    admin,uid=env
    name='audit"; DROP TABLE users;--'
    with auth.db() as c:
        c.execute('CREATE TABLE "audit""; DROP TABLE users;--"(id INTEGER PRIMARY KEY,user_id INTEGER,note TEXT)')
        c.execute('CREATE TABLE audit_child(id INTEGER PRIMARY KEY,"owner""ref" INTEGER REFERENCES "audit""; DROP TABLE users;--"(id))')
        c.execute('INSERT INTO "audit""; DROP TABLE users;--" VALUES(1,?,?)',(uid,"'; DELETE FROM users;--"))
        c.execute('INSERT INTO "audit""; DROP TABLE users;--" VALUES(2,?,?)',(admin,'preserve other owner'))
        c.execute('INSERT INTO audit_child VALUES(1,1),(2,2)')
        selected,meta=life._rows_for_user(c,uid)
        assert set(selected[name])=={1} and set(selected['audit_child'])=={1}
        assert meta[name][0]=='"audit""; DROP TABLE users;--"'
        assert c.execute('SELECT count(*) FROM users').fetchone()[0]==2
        assert c.execute('SELECT note FROM "audit""; DROP TABLE users;--" WHERE id=2').fetchone()[0]=='preserve other owner'
