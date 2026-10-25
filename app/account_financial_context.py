"""Owner-scoped financial context; never combine voluntary shares and debts."""
from .noncommercial_contributions import overview
from .worker_loss_resolution import history


def build(connection,user_id,resource_state):
    if type(user_id) is not int or user_id<=0 or connection.execute('SELECT 1 FROM users WHERE id=?',(user_id,)).fetchone() is None:
        raise ValueError('Invalid accounting owner')
    data=overview(connection,user_id)
    statements=data['statements'];contributions=data['contributions']
    def total(rows,key):
        values=[row[key] for row in rows]
        if any(type(value) is not int or value<0 for value in values):raise ValueError('Invalid personal financial totals')
        return sum(values)
    return {'regime':data['regime'],'currency':'EUR','aggregate_outstanding_debt_micro':None,
            'noncommercial':{'statement_count':len(statements),'allocated_cost_cents':total(statements,'contribution_cents'),
               'verified_received_cents':total(contributions,'received_cents'),
               'declared_remaining_cents':total(contributions,'remaining_cents'),
               'refund_due_cents':total(contributions,'excess_cents'),
               'reported_pending_count':sum(item['reported'] and item['remaining_cents']>0 for item in contributions),
               'collection_allowed':data['enabled'],'mutations_allowed':data['mutations_allowed'],
               'voluntary':True,'affects_access':False,'fiscal_receipt':False,
               'periods':[{'start':item['start'],'end':item['end']} for item in statements]},
            'commercial':{'credit_balance_micro':resource_state['credits_micro'],'subscription':resource_state['subscription'],
               'funded':resource_state['funded'],'controls_allowed':data['regime']=='COMMERCIAL'},
            'operator_assumed_unknown_jobs':len(history(connection,user_id))}
