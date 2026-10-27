"""Inventory mutation controls;new work primitives or source changes need review."""
import copy
import json
from pathlib import Path
import pytest
from scripts.check_service_admission_inventory import discover,validate

ROOT=Path(__file__).resolve().parents[1]


def test_actual_source_bound_service_admission_review():
    review=json.loads((ROOT/'docs/security/SERVICE_ADMISSION_REVIEW_R210.json').read_text())
    assert validate(ROOT,review)['inventory_passed']


@pytest.mark.parametrize('code',[
 'from threading import Thread as Alias\nAlias(target=run)',
 'import sqlite3 as db\ndb.connect(path)',
 'from asyncio import create_task as schedule\nschedule(work())',
 'from concurrent.futures import ProcessPoolExecutor\nProcessPoolExecutor()',
 'from multiprocessing import Process as Worker\nWorker(target=run)',
 'from fastapi import FastAPI\napp=FastAPI()',
 'import subprocess as tasks\ntasks.Popen(command)',
])
def test_new_alias_boundaries_are_discovered(tmp_path,code):
    (tmp_path/'app').mkdir();(tmp_path/'app/new.py').write_text(code)
    assert len(discover(tmp_path))>=1
    with pytest.raises(ValueError):validate(tmp_path,{'schema':'mta-service-admission-review-1','sites':[]})


def test_unclassified_or_omitted_boundary_and_stale_source_are_rejected():
    review=json.loads((ROOT/'docs/security/SERVICE_ADMISSION_REVIEW_R210.json').read_text())
    for field in ['remove','disposition','source']:
        changed=copy.deepcopy(review)
        if field=='remove':changed['sites'].pop()
        elif field=='disposition':changed['sites'][0]['disposition']='approved-everything'
        else:changed['source_sha256']['app/main.py']='f'*64
        with pytest.raises(ValueError):validate(ROOT,changed)
