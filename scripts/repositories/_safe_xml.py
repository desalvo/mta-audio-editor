"""Bounded standard-library XML reader with DTD/entity processing disabled.

Expat handles XML syntax and namespaces; ElementTree only constructs the tree.
Repository tools can run without the application's installed dependencies.
"""
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.parsers import expat


def parse(source,*,max_bytes=64*1024*1024):
    builder=ET.TreeBuilder();parser=expat.ParserCreate(namespace_separator='}')
    def expanded(name):return '{'+name if '}' in name else name
    def start(name,attributes):builder.start(expanded(name),{expanded(k):v for k,v in attributes.items()})
    def forbidden(*args):raise ValueError('XML document types and entity declarations are forbidden')
    parser.StartElementHandler=start;parser.EndElementHandler=lambda name:builder.end(expanded(name))
    parser.CharacterDataHandler=builder.data
    parser.StartDoctypeDeclHandler=forbidden;parser.EntityDeclHandler=forbidden;parser.ExternalEntityRefHandler=forbidden
    owned=not hasattr(source,'read');stream=Path(source).open('rb') if owned else source
    try:
        total=0
        while True:
            chunk=stream.read(64*1024)
            if not chunk:break
            total+=len(chunk)
            if total>max_bytes:raise ValueError('XML input exceeds verification limit')
            parser.Parse(chunk,False)
        parser.Parse(b'',True)
        return ET.ElementTree(builder.close())
    except expat.ExpatError as exc:
        raise ET.ParseError(str(exc)) from exc
    finally:
        if owned:stream.close()
