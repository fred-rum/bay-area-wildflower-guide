import os
import hashlib
import pickle
from contextlib import contextmanager
from base64 import b64encode

# My files
from args import *
from files import *
from strip import *
from page import *
from photo import *
from glossary import *


def init_cache():
    global old_cache
    try:
        with open(f'{root_path}/data/cache.pickle', mode='rb') as f:
            old_cache = pickle.load(f)

        # In case the cache file is empty due to a prior crash.
        if not old_cache:
            old_cache = {}
    except:
        old_cache = {}
init_cache()

new_cache = {}
cache_list = []

def hash_base64(value):
    return bytes.decode(b64encode(hashlib.sha224(value).digest(), b'-_'))

@contextmanager
def write_and_hash(path):
    s = io.StringIO()
    try:
        yield s
    finally:
        value = s.getvalue()
        with open(f'{working_path}/{path}', mode='w', encoding='utf-8') as w:
            w.write(value)
        entry = {
            'base64': hash_base64(value.encode()),
            'kb': len(value) // 1024 + 1
        }
        new_cache[path] = entry

def get_base64(path):
    if path in new_cache:
        # If we already have the new base64 value, return it.
        entry = new_cache[path]
        if 'base64' in entry:
            return entry
    elif path in old_cache:
        # If we have a cached base64 value, verify it.
        entry = old_cache[path]
    else:
        # If we have no info, generate it.
        entry = {}

    # The new cache gets the old cached entry, with whatever modifications
    # we make to it.  Yes, the entries are shared between the old and new
    # caches, but *which* entries are in the new cache are generated fresh
    # every time.
    new_cache[path] = entry

    if 'mtime' in entry and 'base64' not in entry:
        # If we have 'mtime' and not 'base64', that means we've already
        # noticed an 'mtime' change.  The 'mtime' has already been updated,
        # and the 'base64' was discarded in preparation for calculating a
        # new value.
        pass
    else:
        # I checked, and Python deliberately uses enough digits in the
        # yaml float to guarantee equality after a dump and load.
        mtime = os.path.getmtime(f'{root_path}/{path}')
        if 'mtime' in entry and mtime == entry['mtime']:
            # modification times match, so don't bother calculating a fresh
            # base64 hash.
            return entry
        entry['mtime'] = mtime

#    if 'mtime' in entry:
#        print(f'mtime differs in - {path}')
#    else:
#        print(f'new unknown path - {path}')

    with open(f'{root_path}/{path}', mode='rb') as f:
        value = f.read()
        entry['base64'] = hash_base64(value)
        entry['kb'] = len(value) // 1024 + 1

    return entry

def update_cache(path_list):
    for path in path_list:
        path = filename(path)
        entry = get_base64(path)
        base64 = entry['base64']
        kb = entry['kb']
        cache_list.append(f"['{url(path)}', '{base64}', {kb}]")

def gen_url_cache():
    with open(f'{root_path}/data/cache.pickle', mode='wb') as w:
        pickle.dump(new_cache, w)

    code = ",\n".join(cache_list)
    strip_comments('sw.js', code=code)
