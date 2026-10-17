"""On-disk AI cache inventory without importing heavy AI runtimes.

Follow file links (HF snapshots) once by inode; never follow directory links.
Report inaccessible trees explicitly instead of claiming a verified zero.
"""
import os
import tempfile
from pathlib import Path
from . import model_updater as demucs


def roots():
    data=Path(os.getenv('MTA_DATA_DIR','/data/projects')).expanduser()
    cache=Path(os.getenv('XDG_CACHE_HOME',str(Path.home()/'.cache'))).expanduser()
    torch=Path(os.getenv('TORCH_HOME',str(cache/'torch'))).expanduser()
    hf=Path(os.getenv('HF_HOME',str(cache/'huggingface'))).expanduser()
    return [('coreml',demucs.COREML_DIR),('onnx',demucs.ONNX_DIR),('server',demucs.SERVER_DIR),
      ('managed',demucs.ROOT),('lyrics',Path(os.getenv('MTA_LYRICS_MODEL_DIR',str(data/'.cache/lyrics-models')))),
      ('torch',torch),('huggingface',hf),('huggingface',Path(os.getenv('HF_HUB_CACHE',str(hf/'hub')))),
      ('whisper',cache/'whisper'),('chords',cache/'madmom_infer/models'),('chords',data/'.cache/madmom_infer/models'),
      ('drumsep',Path(os.getenv('MTA_DRUMSEP_MODEL_DIR','/var/lib/mta/models/drumsep'))),
      ('vocals',Path(os.getenv('MTA_LEAD_BACKING_MODEL_DIR',os.getenv('MTA_AI_VOCAL_MODELS_DIR',str(Path(tempfile.gettempdir())/'audio-separator-models'))))),
      ('ace',Path(os.getenv('MTA_ACE_MODEL_CACHE','/app/checkpoints'))),('huggingface',Path('/var/lib/mta/models/huggingface'))]


def usage():
    seen=set();trees=set();sizes={};errors=[]
    for category,root in roots():
        root=root.expanduser()
        try:
            resolved=root.resolve()
            if resolved in trees:continue
            trees.add(resolved)
            if not root.exists():continue
            def onerror(exc):errors.append(category+': '+type(exc).__name__)
            for folder,dirs,files in os.walk(root,onerror=onerror,followlinks=False):
                dirs[:]=[d for d in dirs if d not in ('.locks','__pycache__')]
                for name in files:
                    try:
                        st=(Path(folder)/name).stat();identity=(st.st_dev,st.st_ino)
                        if identity not in seen:
                            seen.add(identity);sizes[category]=sizes.get(category,0)+st.st_size
                    except OSError as exc:errors.append(category+': '+type(exc).__name__)
        except OSError as exc:errors.append(category+': '+type(exc).__name__)
    return {'total_bytes':sum(sizes.values()),'coreml_bytes':sizes.get('coreml',0),'onnx_bytes':sizes.get('onnx',0),
      'server_bytes':sum(v for k,v in sizes.items() if k not in ('coreml','onnx')),'by_category':sizes,
      'complete':not errors,'warnings':sorted(set(errors)),
      'note':'File locali nelle cache AI note, deduplicati. Runtime Python e modelli su server ACE remoto esclusi.'}
