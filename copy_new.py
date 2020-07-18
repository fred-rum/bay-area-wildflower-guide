#!/cygdrive/c/Python27/python.exe c:/Users/Chris/Documents/GitHub/bay-area-flowers/copy_new.py

import os
import shutil
import hashlib
import pickle
import time

root = 'c:/Users/Chris/Documents/GitHub/bay-area-flowers'

file_list = ['index.html',
             'bawg.css',
             'search.js',
             'pages.js']

subdir_list = ['html',
               'photos',
               'thumbs',
               'figures',
               'favicon']

excluded_list = ['_mod.html']

print 'get filelist'

for subdir in subdir_list:
    sub_list = os.listdir(root + '/' + subdir)
    for filename in sub_list:
        if filename not in excluded_list:
            file_list.append(subdir + '/' + filename)

print 'read pickle'

try:
    with open(root + '/new.pickle', 'r') as f:
        mod_db = pickle.load(f)
except:
    mod_db = {}

print 'hash files'

mod_list = []
for filename in file_list:
    with open(root + '/' + filename, 'r') as f:
        f_hash = hashlib.sha224(f.read()).hexdigest()
    if filename not in mod_db or f_hash != mod_db[filename]:
        mod_db[filename] = f_hash
        mod_list.append(filename)

print 'delete old directory'

shutil.rmtree(root + '/new', ignore_errors=True)

# Apparently Windows sometimes lets the call complete when the
# remove is not actually done yet, and then the mkdir fails.
# In that case, keep retrying the mkdir until it succeeds.

# But apparently Windows can also return an error but still
# create the directory, and then all future mkdir calls will fail.
# So I hate to do this, but ...
time.sleep(1)

print 'create new directory'

done = False
while not done:
    try:
        os.mkdir(root + '/new')
        done = True
    except WindowsError as error:
        print 'fail'
        time.sleep(1)
        pass

print 'make subdirs'

for subdir in subdir_list:
    os.mkdir(root + '/new/' + subdir)

print 'copy files'

for filename in mod_list:
    print filename
    shutil.copyfile(root + '/' + filename,
                    root + '/new/' + filename)

print 'dump pickle'

with open(root + '/new.pickle', 'w') as f:
    pickle.dump(mod_db, f)
