#!/cygdrive/c/Python27/python.exe c:/Users/Chris/Documents/GitHub/bay-area-flowers/copy_new.py

import os
import shutil
import pickle
import time

root = 'c:/Users/Chris/Documents/GitHub/bay-area-flowers'

file_list = ['index.html',
             'bafg.css',
             'search.js',
             'pages.js']

subdir_list = ['html',
               'photos',
               'thumbs',
               'favicon']

for subdir in subdir_list:
    sub_list = os.listdir(root + '/' + subdir)
    for filename in sub_list:
        file_list.append(subdir + '/' + filename)

try:
    with open(root + '/new.pickle', 'r') as f:
        mod_db = pickle.load(f)
except:
    mod_db = {}

mod_list = []
for filename in file_list:
    mtime = os.path.getmtime(root + '/' + filename)
    if filename not in mod_db or mtime != mod_db[filename]:
        mod_db[filename] = mtime
        mod_list.append(filename)

shutil.rmtree(root + '/new', ignore_errors=True)

# Apparently Windows sometimes lets the call complete when the
# remove is not actually done yet, and then the mkdir fails.
# In that case, keep retrying the mkdir until it succeeds.

# But apparently Windows can also return an error but still
# create the directory, and then all future mkdir calls will fail.
# So I hate to do this, but ...
time.sleep(1)

done = False
while not done:
    try:
        os.mkdir(root + '/new')
        done = True
    except WindowsError as error:
        print 'fail'
        time.sleep(1)
        pass

for subdir in subdir_list:
    os.mkdir(root + '/new/' + subdir)

for filename in mod_list:
    print filename
    shutil.copyfile(root + '/' + filename,
                    root + '/new/' + filename)

with open(root + '/new.pickle', 'w') as f:
    pickle.dump(mod_db, f)
