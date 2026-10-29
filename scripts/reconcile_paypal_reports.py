"""Explicit operator-only canonical PayPal settlement recovery."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.paypal_report_reconciliation import reconcile  # noqa: E402


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--actor',type=int,required=True)
    for key in ['order-id','username','key-file','known-hosts','acm-name','stl-name']:
        parser.add_argument('--'+key,required=True)
    parser.add_argument('--confirm',action='store_true')
    args=vars(parser.parse_args())
    actor,order=args.pop('actor'),args.pop('order_id')
    try:
        result=reconcile(actor,order,**args)
        print(json.dumps(result,sort_keys=True))
        return 0 if result.get('settlement_report_resolutions') and not result.get('financial_review_pending') else 2
    except Exception:
        print('Original report recovery blocked;retain original obligations and review evidence/configuration',file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
