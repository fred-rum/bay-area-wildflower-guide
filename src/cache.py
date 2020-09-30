import os
import hashlib
import yaml

# My files
from args import *
from files import *
from strip import *

def get_sw_reg():
    if arg('-with_cache'):
        return '''
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function() {
    navigator.serviceWorker.register('sw.js').then(function(registration) {
      console.log('ServiceWorker registration successful with scope: ',
                  registration.scope);
    }, function(err) {
      console.log('ServiceWorker registration failed: ', err);
    });
  });
}
'''
    else:
        return '''
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.getRegistrations().then( function(registrations) { for(let registration of registrations) { registration.unregister(); } }); 
}
'''

def get_base64(path, use_mtime=True):
    if path in cache:
        entry = cache[path]
    else:
        entry = {}
        cache[path] = entry

    if not use_mtime:
        # The mtime is always different for generated files, so there's no
        # point in collecting it.
        pass
    elif 'mtime' in entry and 'base64' not in entry:
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
            return entry['base64']
        entry['mtime'] = mtime

    if 'mtime' in entry:
        print(f'mtime differs in - {path}')
    else:
        print(f'new unknown path - {path}')

    with open(f'{root_path}/{path}', mode='rb') as f:
        base64 = hashlib.sha224(f.read()).hexdigest()

    entry['base64'] = base64
    return base64

def gen_url_cache():
    if not arg('-with_cache'):
        strip_comments('sw.js', from_filename='no_sw.js')
        return

    global cache
    try:
        with open(f'{root_path}/data/cache.yaml', mode='r', encoding='utf-8') as f:
            cache = yaml.safe_load(f)
    except:
        cache = {}

    path_list = [
        'index.html',
        'photos/home-icon.png',
    ]

    cache_list = []
    for path in path_list:
        base64 = get_base64(path, use_mtime=True)
        cache_list.append(f"['{url(path)}', '{base64}']")

    path_list = [
        'bawg.css',
        'search.js',
        'pages.js',
    ]
    for path in path_list:
        base64 = get_base64(path, use_mtime=False)
        cache_list.append(f"['{url(path)}', '{base64}']")


#    favicon_set = get_file_set('favicon', None)
#    path_list.extend(get_file_list('favicon', favicon_set, None))
#
#    html_set = set()
#    for page in page_array:
#        html_set.add(page.name)
#    path_list.extend(get_file_list('html', html_set, 'html'))
#
#    path_list.extend(get_file_list('html', glossary_files, 'html'))
#
#    path_list.extend(get_file_list('thumbs', jpg_files, 'jpg'))
#
#    path_list.extend(get_file_list('photos', jpg_files, 'jpg'))
#
#    figure_set = get_file_set('figures', 'svg')
#    figure_set.discard('_figure template')
#    path_list.extend(get_file_list('figures', figure_set, 'svg'))

    code = ",\n".join(cache_list)
    strip_comments('sw.js', code=code)

    with open(f'{root_path}/data/cache.yaml', mode='w', encoding='utf-8') as w:
        w.write(yaml.dump(cache, default_flow_style=False))
