"""Source-bound review of service admission entry/work/continuation boundaries.

All app source bytes are pinned,including code outside the explicit AST census.
This is not arbitrary native-code analysis or external kernel/HA certification.
"""
import ast
import hashlib
import json
from pathlib import Path

if __package__:
    from .check_remote_transport_inventory import call_shape
    from .check_security_review import source_hashes
else:
    from check_remote_transport_inventory import call_shape
    from check_security_review import source_hashes


def discover(root):
    sites=[]
    for p in sorted((root/'app').rglob('*.py')):
        tree=ast.parse(p.read_text());aliases={}
        for n in ast.walk(tree):
            if isinstance(n,ast.Import):
                for a in n.names:aliases[a.asname or a.name]=a.name
            elif isinstance(n,ast.ImportFrom):
                for a in n.names:aliases[a.asname or a.name]=(n.module or '')+'.'+a.name
        def dotted(n):
            if isinstance(n,ast.Name):return aliases.get(n.id,n.id)
            if isinstance(n,ast.Attribute):return dotted(n.value)+'.'+n.attr
            return ''
        def visit(n,function='<module>'):
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):function=n.name
            kind=None;name=''
            if isinstance(n,ast.Call):
                name=dotted(n.func)
                leaf=name.rsplit('.',1)[-1]
                if leaf in {'Thread','worker_thread','ThreadPoolExecutor','ProcessPoolExecutor','Process','Pool',
                            'create_task','ensure_future','run_in_executor','BackgroundTask','BackgroundTasks'}:kind='asynchronous_lifetime'
                elif name=='sqlite3.connect':kind='database_connection'
                elif name in {'subprocess.Popen','subprocess.run','subprocess.call','subprocess.check_call','subprocess.check_output'} or name in {'os.system','os.fork','os.posix_spawn','os.execve','os.execv','os.execvp'}:kind='process_boundary'
                elif leaf in {'FastAPI','HTTPServer','ThreadingHTTPServer','serve','run_server'} or name=='uvicorn.run':kind='service_entry'
            elif isinstance(n,ast.If) and isinstance(n.test,ast.Compare) and '__name__' in ast.unparse(n.test):kind='command_entry';name='__main__'
            if kind:sites.append({'path':p.relative_to(root).as_posix(),'function':function,'line':n.lineno,'kind':kind,'call':name,
                                 'ast_sha256':hashlib.sha256(call_shape(n).encode()).hexdigest()})
            for child in ast.iter_child_nodes(n):visit(child,function)
        visit(tree)
    return sorted(sites,key=lambda x:(x['path'],x['line'],x['kind']))


def validate(root,review):
    expected={p:'sha256:'+value for p,value in source_hashes(root).items()}
    if (review.get('schema')!='mta-service-admission-review-1' or review.get('source_sha256')!=expected
            or review.get('checker_sha256')!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()):
        raise ValueError('Service admission review missing or stale')
    sites=discover(root);entries=review.get('sites',[])
    if len(sites)!=len(entries):raise ValueError('New or missing admission boundary')
    allowed={'tracked_work','request_lifetime','periodic_cycle','owned_continuation','read_only','offline_empty_target',
             'offline_control','external_worker','native_only','journal_control'}
    for site,item in zip(sites,entries):
        if any(item.get(k)!=v for k,v in site.items()):raise ValueError('Admission boundary changed')
        if item.get('disposition') not in allowed or any(len(item.get(k,'').strip())<25 for k in ['boundary','verification']):
            raise ValueError('Unreviewed admission boundary')
    return {'inventory_passed':True,'source_files':len(review['source_sha256']),'reviewed_sites':len(sites),
            'scope':'Supported single pinned Linux authority replicas and HTTPS-only original workers',
            'financial_transition_authorized':False,'external_kernel_or_multihost_accepted':False,'release_candidate':False}


def main():
    root=Path(__file__).resolve().parents[1]
    print(json.dumps(validate(root,json.loads((root/'docs/security/SERVICE_ADMISSION_REVIEW_R210.json').read_text())),sort_keys=True))


if __name__=='__main__':main()
