"""Require reviewed dispositions for Python-owned network boundaries.

This inventories explicit HTTP clients/openers, not arbitrary operator binaries,
native libraries or dynamically constructed socket code. It never grants model
rights, verifies a remote checkpoint or enables commercial remote inference.
"""
import ast
import hashlib
import json
from pathlib import Path


def call_shape(node):
    """Hash AST fields independently of ast.dump presentation across Python versions."""
    def value(item):
        if isinstance(item,ast.AST):
            return [type(item).__name__,[[key,value(child)] for key,child in ast.iter_fields(item)]]
        if isinstance(item,list):return [value(child) for child in item]
        if isinstance(item,bytes):return {'bytes':item.hex()}
        if isinstance(item,complex):return {'complex':repr(item)}
        if item is Ellipsis:return {'ellipsis':True}
        return item
    return json.dumps(value(node),ensure_ascii=True,separators=(',',':'))


def discover(root):
    sites=[]
    for path in sorted((root/'app').rglob('*.py')):
        if path.is_symlink():raise ValueError('Symbolic application source')
        text=path.read_text();tree=ast.parse(text);aliases={}
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                for name in node.names:aliases[name.asname or name.name]=name.name
            elif isinstance(node,ast.ImportFrom):
                for name in node.names:aliases[name.asname or name.name]=(node.module or '')+'.'+name.name
        def dotted(node):
            if isinstance(node,ast.Name):return aliases.get(node.id,node.id)
            if isinstance(node,ast.Attribute):return dotted(node.value)+'.'+node.attr
            if isinstance(node,ast.Call):return dotted(node.func)+'()'
            return ''
        openers=set()
        for node in ast.walk(tree):
            if isinstance(node,(ast.Assign,ast.AnnAssign)) and isinstance(node.value,ast.Call) and dotted(node.value.func).endswith('build_opener'):
                targets=node.targets if isinstance(node,ast.Assign) else [node.target]
                openers.update(x.id for x in targets if isinstance(x,ast.Name))
        def visit(node,function='<module>'):
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):function=node.name
            if isinstance(node,ast.Call):
                name=dotted(node.func)
                network=(name.endswith(('.https_urlopen','.urlopen','.urlretrieve'))
                         or name in ('https_urlopen','urlopen','urlretrieve')
                         or name in ('httpx.Client','httpx.AsyncClient','requests.Session','requests.get','requests.post','requests.request',
                                     'socket.socket','socket.create_connection','http.client.HTTPConnection','http.client.HTTPSConnection',
                                     'urllib3.PoolManager','aiohttp.ClientSession','websockets.connect','websocket.create_connection')
                         or (isinstance(node.func,ast.Attribute) and node.func.attr=='open'
                             and (dotted(node.func.value).endswith('build_opener()') or dotted(node.func.value) in openers)))
                if network:
                    shape=call_shape(node)
                    sites.append({'path':path.relative_to(root).as_posix(),'function':function,'line':node.lineno,
                                  'call':name,'call_sha256':hashlib.sha256(shape.encode()).hexdigest(),
                                  'source_sha256':hashlib.sha256(text.encode()).hexdigest()})
            for child in ast.iter_child_nodes(node):visit(child,function)
        visit(tree)
    return sorted(sites,key=lambda x:(x['path'],x['line']))


def validate(root,review):
    if review.get('schema')!='mta-remote-transport-review-1':raise ValueError('Missing transport inventory review')
    if review.get('checker_sha256')!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        raise ValueError('Transport inventory checker changed; explicit review required')
    sites=discover(root);reviewed=review.get('sites')
    if not isinstance(reviewed,list) or len(reviewed)!=len(sites):raise ValueError('New or missing transport boundary')
    categories={'inference_guarded','recovery_or_metadata','asset_download','payment_provider','authentication','local_health','rights_metadata'}
    for current,item in zip(sites,reviewed):
        if any(item.get(key)!=value for key,value in current.items()):raise ValueError('Transport review is stale')
        if item.get('category') not in categories or any(not isinstance(item.get(key),str) or len(item[key].strip())<20 for key in ('boundary','verification')):
            raise ValueError('Unreviewed transport disposition')
    return {'reviewed_sites':len(sites),'source_files':len({x['path'] for x in sites}),
            'inventory_passed':True,'remote_model_attestation_complete':False,'release_candidate':False}


def main():
    root=Path(__file__).resolve().parents[1]
    review=json.loads((root/'docs/security/REMOTE_TRANSPORT_REVIEW_R210.json').read_text())
    print(json.dumps(validate(root,review),sort_keys=True))


if __name__=='__main__':main()
