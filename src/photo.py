import subprocess

# My files
from error import *
from files import *
from page import *

old_thumb_set = get_file_set(f'thumbs', 'jpg')

jpg_files = jpg_photos.union(jpg_figures)

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
for name in old_thumb_set:
    if name not in jpg_files:
        thumb_file = f'{root_path}/thumbs/' + name + '.jpg'
        os.remove(thumb_file)

mod_list = []
def check_thumb(name, dir):
    photo_file = f'{root_path}/{dir}/{name}.jpg'
    thumb_file = f'{root_path}/thumbs/{name}.jpg'
    if (name not in old_thumb_set or
        os.path.getmtime(photo_file) > os.path.getmtime(thumb_file)):
        mod_list.append(photo_file)

for name in jpg_photos:
    check_thumb(name, 'photos')

for name in jpg_figures:
    check_thumb(name, 'figures')


def which_plus(program, plus):
    cmd = shutil.which(program)
    if cmd:
        return cmd

    if plus:
        # plus only gets used on Windows, so treat it as case insensitive.
        plus = plus.lower()

        # Search the known standard installation directories for Windows
        # programs.  (If not on Windows, than these environment variables
        # aren't found, and this section is effectively skipped.)
        for env in ('ProgramFiles', 'ProgramFiles(x86)'):
            dir = os.environ.get(env)
            if dir:
                # Search for any sub-directory that starts with the
                # plus name.
                file_list = os.listdir(dir)
                for filename in file_list:
                    if filename.lower().startswith(plus):
                        # Check whether the program is in the sub-directory.
                        cmd = shutil.which(program, path=os.path.join(dir,
                                                                      filename))
                        if cmd:
                            return cmd

    return None

def run(cmd):
    # Run a command and capture its returncode.
    # If the command emits any messages, let those go to STDOUT/STDERR
    # per the default behavior.
    result = subprocess.run(cmd)

    if result.returncode:
        if arg('-steps'):
            # command was already printed
            pass
        else:
            info(' '.join(cmd))
        error(f"Command returned non-zero exit status {result.returncode}")

def cvt_irfanview(cmd):
    # IrvanView creates the destination directory if necessary
    # so we don't have to create it ourselves.

    # Since every OS has a limit on how long the ocmmand line can be,
    # we put the file list in convert.txt and then point IrfanView to
    # that file.  IrfanView expects a newline to separate each file
    # in the list.
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
        info(f'Generating {len(mod_list)} thumbnails with IrfanView:')
        info(' '.join(cmd))

    subprocess.Popen(cmd).wait()

def cvt_imagemagick(cmd):
    # ImageMagick does not create the destination directory,
    # so we create it ourselves if necessray.
    mkdir('thumbs')

    # Since every OS has a limit on how long the ocmmand line can be,
    # we put the file list in convert.txt and then point ImageMagick to
    # that file.  ImageMagick allows any whitespace to separate each file
    # in the list, so we surround each filename with double-quotes to
    # prevent a space in a filename from doing the wrong thing.
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
        info(f'Generating {len(mod_list)} thumbnails with ImageMagick:')
        info(' '.join(cmd))

    run(cmd)

def cvt_magick(cmd):
    # ImageMagic7 is invoked with 'magick mogrify'.
    cvt_imagemagick([cmd, 'mogrify'])

def cvt_mogrify(cmd):
    # ImageMagic6 is invoked with just 'mogrify'.
    cvt_imagemagick([cmd])

if mod_list:
    # Search for a program that can generate photo thumbnails.
    # Each tuple in cmd has the following information:
    # - the root name of the command (not including '.exe' on Windows)
    # - a subdirectory of 'Program Files' that it might be in
    # - the function to run if the program is found.
    cmds = [
        ('magick', 'ImageMagick', cvt_magick),
        ('mogrify', 'ImageMagick', cvt_mogrify),
        ('i_view32', 'IrfanView', cvt_irfanview),
        ('i_view64', 'IrfanView', cvt_irfanview),
    ]

    for (program, plus, fn) in cmds:
        cmd = which_plus(program, plus)
        if cmd:
            fn(cmd)
            break
    else:
        warn('No photo conversion program found.  Skipping.')

# Return the relative URL to a thumbnail photo.
def thumb_url(jpg):
    return url(f'../thumbs/{jpg}.jpg')
