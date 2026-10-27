"""Bounded,fail-closed availability errors;never cache authentication or money."""
import sqlite3
from .regime_operation_fence import FenceBlocked


def is_busy(error):
    if not isinstance(error,sqlite3.OperationalError): return False
    code = getattr(error,'sqlite_errorcode',None)
    if isinstance(code,int): return code & 255 in {sqlite3.SQLITE_BUSY,sqlite3.SQLITE_LOCKED}
    text = str(error).lower()
    return text in {'database is locked','database is busy'} or text.startswith(('database table is locked','database schema is locked'))


class BarrierUnavailable(FenceBlocked):
    def __init__(self,error):
        self.retryable = is_busy(error)
        super().__init__('Service barrier read temporarily unavailable' if self.retryable else 'Service barrier evidence unavailable')


def response(error=None,*,method='GET'):
    from starlette.responses import JSONResponse
    from .i18n import current_language
    busy = error is None or is_busy(error) or isinstance(error,BarrierUnavailable) and error.retryable
    retryable = bool(busy and method.upper() in {'GET','HEAD'})
    message = ('Database temporaneamente occupato. Attendere e riprovare.' if current_language.get()=='it'
               else 'Database temporarily busy. Please wait and retry.')
    return JSONResponse({'detail':message if busy
                         else 'Service state unavailable;administrator review required',
        'code':'database_busy' if busy else 'service_state_unavailable','retryable':retryable},
        status_code=503,headers={'Cache-Control':'private, no-store','Retry-After':'1'})
