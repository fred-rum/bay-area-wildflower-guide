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

def record_hash(entry, value):
    entry['base64'] = hash_base64(value)
    entry['kb'] = len(value) // 1024 + 1 # treat empty file as 1 KB

@contextmanager
def write_and_hash(path):
    s = io.StringIO()
    try:
        yield s
    finally:
        entry = {}
        record_hash(entry, s.getvalue().encode())

        try: # in case the file no longer exists
            if (path in old_cache
                and old_cache[path]['base64'] == entry['base64']
                and 'mtime' in old_cache[path]
                and old_cache[path]['mtime'] == os.path.getmtime(f'{root_path}/{path}')):
                # the file is unchanged, so we don't need to re-write it
                new_cache[path] = old_cache[path]
            else:
                raise Exception
        except: # if the file is different or the mtime query fails
            # The output is written with the Python-native '\n' line endinge
            # instead of the default OS line endings so that we get the same
            # hash_base64 result on the file as we do internally.
            with open(f'{root_path}/{path}', mode='w',
                      encoding='utf-8', newline='') as w:
                w.write(value)
            mod_files.add(path)
            new_cache[path] = entry

def get_base64(path):
    if path in new_cache:
        # We already have some information about the file
        # (either 'base64' or 'mtime', but not both).
        entry = new_cache[path]
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
        mtime = os.path.getmtime(f'{root_path}/{path}')
        if 'base64' in entry:
            if 'mtime' not in entry:
                # If we have 'base64' and not 'mtime', then we must have
                # written and hashed this file during this script invocation.
                # We just have to update the mtime
                entry['mtime'] = mtime
                return entry
            if 'mtime' in entry and mtime == entry['mtime']:
                # If we have both 'base64' and 'mtime', then we haven't
                # changed this file during this script invocation.
                # If the user hasn't changed the file outside the script,
                # don't bother calculating a fresh hash.
                return entry

        # Either we've updated the file without hashing it
        entry['mtime'] = mtime

    with open(f'{root_path}/{path}', mode='rb') as f:
        record_hash(entry, f.read())

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

    # Ideally we would only update sw.js if something has changed.
    # But:
    # - we'd also have to changes in the sw.js
    # - script errors can create the appearance of change when there isn't any
    # So it's easier and more predictable to just always update sw.js.
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    num_urls = len(cache_list)
    code = f'''var upd_timestamp = '{timestamp}';
var upd_num_urls = {num_urls};
var upd_kb_total = {kb_total}'''
    strip_comments('sw.js', code=code)
