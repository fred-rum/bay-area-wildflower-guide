import subprocess

# My files
from error import *
from files import *
from page import *

thumb_set = get_file_set(f'{db_pfx}thumbs', 'jpg')

def get_name_from_jpg(jpg):
    name = re.sub(r',([-0-9]\S*|)$', r'', jpg)

    return name

# Compare the photos directory with the thumbs directory.
# If a file exists in photos and not thumbs, create it.
# If a file is newer in photos than in thumbs, re-create it.
# If a file exists in thumbs and not photos, delete it.
# If a file is newer in thumbs than in photos, leave it unchanged.
#
# We manipulate thumbs in root_path instead of working_path because
# not all files get re-created (normally just a small minority), and
# it'd be a pain to merge the changes later.  Since thumbs aren't
# compared to the previous version, the only disadvantage in not
# using working_path is that some thumbs may disappear during the run,
# and that is OK.
for name in thumb_set:
    if name not in jpg_files:
        thumb_file = f'{root_path}/{db_pfx}thumbs/' + name + '.jpg'
        os.remove(thumb_file)

mod_list = []
for name in jpg_files:
    photo_file = f'{root_path}/{db_pfx}photos/' + name + '.jpg'
    thumb_file = f'{root_path}/{db_pfx}thumbs/' + name + '.jpg'
    if (name not in thumb_set or
        os.path.getmtime(photo_file) > os.path.getmtime(thumb_file)):
        mod_list.append(photo_file)

if mod_list:
    with open(working_path + "/convert.txt", "w") as w:
        for filename in mod_list:
            filename = convert_path_to_windows(filename)
            w.write(filename + '\n')
    convert_list = convert_path_to_windows(f'{working_path}/convert.txt')
    thumb_glob = convert_path_to_windows(f'{root_path}/{db_pfx}thumbs/*.jpg')
    cmd = ['C:/Program Files (x86)/IrfanView/i_view32.exe',
           f'/filelist={convert_list}',
           '/aspectratio',
           '/resize_long=200',
           '/resample',
           '/jpgq=80',
           f'/convert={thumb_glob}']
    subprocess.Popen(cmd).wait()


# Record jpg names for associated pages.
# Create a blank page for all unassociated jpgs.
def assign_jpgs():
    for jpg in sorted(jpg_files):
        name = get_name_from_jpg(jpg)
        if name == '':
            error(f'No name for {jpg}')
        else:
            page = find_page1(name)
            if not page:
                page = Page(name)
            page.add_jpg(jpg)
