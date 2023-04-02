import os
import hashlib
import pickle
from contextlib import contextmanager
from base64 import b64encode
import datetime
import io

# My files
from args import *
from files import *
from strip import *

kb_total = 0


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
mod_files = set()
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
        base64 = hash_base64(value.encode())
        entry = {
            'base64': base64,
            'kb': len(value) // 1024 + 1
        }
        try:
            if (path in old_cache
                and old_cache[path]['base64'] == entry['base64']
                and 'mtime' in old_cache[path]
                and old_cache[path]['mtime'] == os.path.getmtime(f'{root_path}/{path}')):
                # the file is unchanged, so we don't need to re-write it
                new_cache[path] = old_cache[path]
            else:
                raise Exception
        except: # if the file is different or the mtime query fails
            if path == 'html/Agaricomycetes.html':
                if old_cache[path]['base64'] != entry['base64']:
                    print('base64 differs')
                elif 'mtime' not in old_cache[path]:
                    print('mtime missing')
                else:
                    print('mtime differs')
            mod_files.add(path)
            # The output is written with the Python-native '\n' line endinge
            # instead of the default OS line endings so that we get the same
            # hash_base64 result on the file as we do internally.
            with open(f'{root_path}/{path}', mode='w',
                      encoding='utf-8', newline='') as w:
                w.write(value)

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
        # Presumably the pickle is equally good.
        mtime = os.path.getmtime(f'{root_path}/{path}')
        if 'mtime' in entry and mtime == entry['mtime']:
            # modification times match, so don't bother calculating a fresh
            # base64 hash.
            return entry
        entry['mtime'] = mtime

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
        cache_list.append(f'["{url(path)}", "{base64}", {kb}]')
        global kb_total
        kb_total += kb

def gen_url_cache():
    with open(f'{root_path}/data/cache.pickle', mode='wb') as w:
        pickle.dump(new_cache, w)

    code = ",\n".join(cache_list)
    with open(f'{root_path}/url_data.json', mode='w') as w:
        w.write(f'[\n{code}\n]\n');

    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    num_urls = len(cache_list)
    code = f'''var upd_timestamp = '{timestamp}';
var upd_num_urls = {num_urls};
var upd_kb_total = {kb_total}'''
    strip_comments('sw.js', code=code)
