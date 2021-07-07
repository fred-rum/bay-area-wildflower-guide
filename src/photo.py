import subprocess

# My files
from error import *
from files import *
from page import *

thumb_set = get_file_set(f'thumbs', 'jpg')

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
        thumb_file = f'{root_path}/thumbs/' + name + '.jpg'
        os.remove(thumb_file)

mod_list = []
for name in jpg_files:
    photo_file = f'{root_path}/photos/' + name + '.jpg'
    thumb_file = f'{root_path}/thumbs/' + name + '.jpg'
    if (name not in thumb_set or
        os.path.getmtime(photo_file) > os.path.getmtime(thumb_file)):
        mod_list.append(photo_file)


def which_plus(program, use_path, plus):
    if use_path:
        cmd = shutil.which(program)
        if cmd:
            return cmd

    if plus:
        for env in ('ProgramFiles', 'ProgramFiles(x86)'):
            dir = os.environ.get(env)
            if dir:
                cmd = shutil.which(program, path=os.path.join(dir, plus))
                if cmd:
                    return cmd

    return None

def cvt_irfanview(cmd):
    with open(working_path + "/convert.txt", "w") as w:
        for filename in mod_list:
            filename = convert_path_to_windows(filename)
            w.write(f'{filename}\n')
    convert_list = convert_path_to_windows(f'{working_path}/convert.txt')
    thumb_glob = convert_path_to_windows(f'{root_path}/thumbs/*.jpg')
    cmd = [cmd,
           f'/filelist={convert_list}',
           '/aspectratio',
           '/resize_long=200',
           '/resample',
           '/jpgq=80',
           f'/convert={thumb_glob}']
    if arg('-steps'):
        print(f'Generating {len(mod_list)} thumbnails with IrfanView:\n{cmd}')
    subprocess.Popen(cmd).wait()

def cvt_imagemagick(cmd):
    try:
        os.mkdir(root_path + '/thumbs')
    except FileExistsError:
        pass
    with open(working_path + "/convert.txt", "w") as w:
        for filename in mod_list:
            filename = convert_path_to_windows(filename)
            w.write(f'"{filename}"\n')
    convert_list = convert_path_to_windows(f'{working_path}/convert.txt')
    thumb_path = convert_path_to_windows(f'{root_path}/thumbs')
    cmd.extend(
        ['-path', thumb_path,            # write files to thumbs directory
         '-define', 'jpeg:size=400x400', # read JPGs much faster
         '-thumbnail', '200x200>',       # strip EXIF data and gen. thumbnails
         '-quality', '80%',              # reduce quality
         f'@{convert_list}',             # list of files must be last?
        ])
    if arg('-steps'):
        print(f'Generating {len(mod_list)} thumbnails with ImageMagick:\n{cmd}')
    subprocess.Popen(cmd).wait()

def cvt_magick(cmd):
    # ImageMagic7 is invoked with 'magick mogrify'.
    cvt_imagemagick([cmd, 'mogrify'])

def cvt_mogrify(cmd):
    # ImageMagic6 is invoked with just 'mogrify'.
    cvt_imagemagick([cmd])

if mod_list:
    # ImageMagick's 'convert' utility is confusing because it collides with
    # windows standard disk format conversion utility.  Therefore, when we
    # search for 'convert.exe', we don't want to look in the standard path.
    # And when we search for 'convert' in the standard path, we don't want
    # to search using the standard Windows executable extensions (i.e. '.exe')
    os.environ.pop("PATHEXT", None)

    cmds = [
        ('magick.exe', True, 'ImageMagick', cvt_magick),
        ('magick', True, None, cvt_magick),
        ('mogrify.exe', True, 'ImageMagick-6', cvt_mogrify),
        ('mogrify', True, None, cvt_mogrify),
        ('i_view32.exe', True, 'IrfanView', cvt_irfanview),
        ('i_view65.exe', True, 'IrfanView', cvt_irfanview),
    ]

    for (program, use_path, plus, fn) in cmds:
        cmd = which_plus(program, use_path, plus)
        if cmd:
            fn(cmd)
            break
    else:
        warning('No photo conversion program found.  Skipping.')


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
