"""Real account tables across internal cutover phases; not enabled API acceptance."""
import sqlite3

import pytest
from app import auth,resource_accounts as accounts,ai_billing
from app.regime_operation_fence import FenceBlocked
from app import regime_balance_continuity as continuity
from app.regime_transition_journal import reserve
from app.regime_cutover_mirror import reconcile_mirror
from test_r210_subscriptions import account as account  # noqa: F401


@pytest.fixture
def prepared(account,tmp_path):
    with auth.db() as con:
        ai_billing._init(con);accounts.init(con)
        con.execute("INSERT INTO resource_credits VALUES('continuity-credit',?,1000000,?,'explicit test credit',1)",(account,account))
        con.execute("INSERT INTO resource_periods VALUES(?,1,1000,'{}','TEST')",(account,))
        con.execute('INSERT INTO resource_storage_debits VALUES(?,100,123)',(account,))
        con.execute('''CREATE TABLE nc_period_statements(period_start INTEGER,period_end INTEGER,statement_json TEXT,sha256 TEXT,PRIMARY KEY(period_start,period_end))''')
        con.execute("INSERT INTO nc_period_statements VALUES(1,2,'{\"immutable\":true}','synthetic-history')")
        con.commit()
        con.execute('BEGIN IMMEDIATE')
        reserve(con,transition_id='balance-cutover',target='NON_COMMERCIAL',expected_revision=0,evidence={'ready':True,'unresolved':[]})
    return account,tmp_path/'service-regime.json'


def test_internal_commit_mirror_finalize_conserve_actual_wallet_periods_and_nc_history(prepared):
    uid,path=prepared
    with auth.db() as con:
        con.execute('BEGIN IMMEDIATE');before=continuity.snapshot(con);balance=accounts._balance(con,uid)
        committed=continuity.commit_preserving_balances(con,transition_id='balance-cutover',expected_revision=0,readiness_check=lambda _:True)
        assert committed['barrier_held'] and accounts._balance(con,uid)==balance==999877
        assert continuity.snapshot(con)==before
    with auth.db() as con:
        con.execute('BEGIN IMMEDIATE');reconcile_mirror(con,path,'balance-cutover')
        result=continuity.finalize_preserving_balances(con,mirror_path=path,transition_id='balance-cutover',readiness_check=lambda _:True)
        assert result['barrier_held'] is False and continuity.snapshot(con)==before
        assert con.execute('SELECT regime,revision,transitioning FROM regime_fence_state').fetchone()[:]==('NON_COMMERCIAL',1,0)
        assert accounts._balance(con,uid)==balance
    # The callbacks deliberately stand in for missing whole-service readiness.
    # This internal primitive proof is NOT D6/API authorization or RC evidence.


@pytest.mark.parametrize('change',['wallet','period','history','schema','new-statement-table'])
def test_post_commit_drift_cannot_release_fence(prepared,change):
    _,path=prepared
    with auth.db() as con:
        con.execute('BEGIN IMMEDIATE');continuity.commit_preserving_balances(con,transition_id='balance-cutover',expected_revision=0,readiness_check=lambda _:True)
    with auth.db() as con:
        if change=='wallet':con.execute('UPDATE resource_credits SET delta_micro=0')
        elif change=='period':con.execute('UPDATE resource_periods SET end=end+1')
        elif change=='history':con.execute("UPDATE nc_period_statements SET statement_json='{}'")
        elif change=='schema':con.execute('ALTER TABLE resource_periods ADD COLUMN unexpected INTEGER')
        else:con.execute('DROP TABLE nc_period_statements')
    with auth.db() as con:
        con.execute('BEGIN IMMEDIATE');reconcile_mirror(con,path,'balance-cutover')
        with pytest.raises(FenceBlocked,match='balances or periods changed'):
            continuity.finalize_preserving_balances(con,mirror_path=path,transition_id='balance-cutover',readiness_check=lambda _:True)
        assert con.execute('SELECT transitioning FROM regime_fence_state').fetchone()[0]==1


def test_mutating_readiness_callback_rolls_back_with_caller_transaction(prepared):
    uid,_=prepared
    with auth.db() as con:
        before=accounts._balance(con,uid)
        con.execute('BEGIN IMMEDIATE')
        def corrupt(connection):
            connection.execute('UPDATE resource_credits SET delta_micro=0');return True
        with pytest.raises(FenceBlocked,match='Financial mutation'):
            continuity.commit_preserving_balances(con,transition_id='balance-cutover',expected_revision=0,readiness_check=corrupt)
        con.rollback()
        assert accounts._balance(con,uid)==before
        assert con.execute('SELECT regime,revision,transitioning FROM regime_fence_state').fetchone()[:]==('COMMERCIAL',0,1)


def test_baseline_immutable_and_missing_original_never_adopted(prepared):
    _,_=prepared
    with auth.db() as con:
        con.execute('BEGIN IMMEDIATE')
        with pytest.raises(FenceBlocked,match='unavailable'):continuity.verify(con,'balance-cutover')
        continuity.commit_preserving_balances(con,transition_id='balance-cutover',expected_revision=0,readiness_check=lambda _:True)
        with pytest.raises(sqlite3.IntegrityError):con.execute("UPDATE regime_balance_continuity SET snapshot_json='{}'")
        with pytest.raises(sqlite3.IntegrityError):con.execute('DELETE FROM regime_balance_continuity')


def test_finalize_callback_mutation_cannot_commit_fence_release(prepared):
    uid,path=prepared
    with auth.db() as con:
        con.execute('BEGIN IMMEDIATE');continuity.commit_preserving_balances(con,transition_id='balance-cutover',expected_revision=0,readiness_check=lambda _:True)
    with auth.db() as con:
        original=accounts._balance(con,uid);con.execute('BEGIN IMMEDIATE');reconcile_mirror(con,path,'balance-cutover')
        def mutate(connection):connection.execute('UPDATE resource_storage_debits SET cost_micro=0');return True
        with pytest.raises(FenceBlocked):continuity.finalize_preserving_balances(con,mirror_path=path,transition_id='balance-cutover',readiness_check=mutate)
        con.rollback()
        assert accounts._balance(con,uid)==original
        assert con.execute('SELECT transitioning FROM regime_fence_state').fetchone()[0]==1


def test_unknown_schema_is_not_a_zero_balance():
    con=sqlite3.connect(':memory:');con.execute('BEGIN IMMEDIATE')
    with pytest.raises(FenceBlocked,match='Financial schema unavailable'):continuity.snapshot(con)


def test_internal_roundtrip_preserves_same_wallet_and_period_history(prepared):
    uid,path=prepared
    with auth.db() as con:
        con.execute('BEGIN IMMEDIATE');original=continuity.snapshot(con)
        continuity.commit_preserving_balances(con,transition_id='balance-cutover',expected_revision=0,readiness_check=lambda _:True)
    with auth.db() as con:
        con.execute('BEGIN IMMEDIATE');reconcile_mirror(con,path,'balance-cutover')
        continuity.finalize_preserving_balances(con,mirror_path=path,transition_id='balance-cutover',readiness_check=lambda _:True)
    with auth.db() as con:
        con.execute('BEGIN IMMEDIATE')
        reserve(con,transition_id='return-commercial',target='COMMERCIAL',expected_revision=1,evidence={'ready':True,'unresolved':[]})
        continuity.commit_preserving_balances(con,transition_id='return-commercial',expected_revision=1,readiness_check=lambda _:True)
    with auth.db() as con:
        con.execute('BEGIN IMMEDIATE');reconcile_mirror(con,path,'return-commercial')
        continuity.finalize_preserving_balances(con,mirror_path=path,transition_id='return-commercial',readiness_check=lambda _:True)
        assert continuity.snapshot(con)==original and accounts._balance(con,uid)==999877
        assert con.execute('SELECT regime,revision,transitioning FROM regime_fence_state').fetchone()[:]==('COMMERCIAL',2,0)
