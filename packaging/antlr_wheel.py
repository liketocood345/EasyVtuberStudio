"""Deterministic pure-Python wheel for the pinned ANTLR 4.9.3 sdist.

Upstream publishes only a source tarball. This narrow adapter copies its Python
sources and pygrun script without executing setup.py or downloading build tools.
The source tarball and resulting wheel are both hash locked in the recipe.
"""
import base64
import csv
import hashlib
import io
import tarfile
import zipfile


def build(source, target):
    prefix = 'antlr4-python3-runtime-4.9.3/'
    info = 'antlr4_python3_runtime-4.9.3.dist-info/'
    entries = {}
    with tarfile.open(source, 'r:gz') as archive:
        for member in archive.getmembers():
            if not member.isfile(): continue
            name = member.name
            if name.startswith(prefix + 'src/antlr4/') and name.endswith('.py'):
                entries[name[len(prefix+'src/'):]] = archive.extractfile(member).read()
            elif name == prefix+'PKG-INFO': entries[info+'METADATA'] = archive.extractfile(member).read()
            elif name == prefix+'bin/pygrun':
                data=archive.extractfile(member).read().split(b'\n',1)[1]
                entries['antlr4_python3_runtime-4.9.3.data/scripts/pygrun'] = b'#!python\n'+data
    if 'antlr4/__init__.py' not in entries or info+'METADATA' not in entries:
        raise ValueError('Unexpected ANTLR sdist layout')
    entries[info+'WHEEL']=b'Wheel-Version: 1.0\nGenerator: EVS pinned pure-source adapter 1\nRoot-Is-Purelib: true\nTag: py3-none-any\n'
    entries[info+'top_level.txt']=b'antlr4\n'
    record=io.StringIO(newline=''); writer=csv.writer(record,lineterminator='\n')
    for name,data in sorted(entries.items()):
        digest=base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
        writer.writerow((name,'sha256='+digest,len(data)))
    writer.writerow((info+'RECORD','',''))
    entries[info+'RECORD']=record.getvalue().encode()
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as out:
        for name,data in sorted(entries.items()):
            member=zipfile.ZipInfo(name,(1980,1,1,0,0,0)); member.compress_type=zipfile.ZIP_DEFLATED
            member.external_attr=0o100644 << 16
            out.writestr(member,data,compresslevel=9)
