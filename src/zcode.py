# Z codes are efficient identifiers used in pages.js.  For each taxon,
# Z codes idtify traits that apply to the taxon and trips that observed
# the taxon.
#
# Z codes are initlally assigned as integers (zint) since we don't yet know
# how many we'll need.  Then we convert the integers to strings of the
# appropriate length (zstr).
#
# A zstr is composed of one or more printable ASCII characters, excluding
# the " and \ characters.
#   It excludes ASCII characters 34 and 92.
#   It includes ASCII characters 32-33, 35-91, and 93-126.
#   It uses 93 characters total.
# 
# and ~ (126), inclusive.  Because the zstr includes only normal ASCII and
# avoids the " character, it can be easily emitted as a JavaScript string.
# It also skips the easily encoded space and ! characters, but it doesn't
# seem worth adding extra code for just these 2 extra encodings.
#
# The zstr puts the most significant portion of the zint in the first
# character, so a simple sort of zstr values results in the same order
# as a sort of the equivalent zint values.

###############################################################################

num_zcodes = 0

# Map an object to a Z code (an integer or string, depending on our progress).
obj_to_zcode = {}

def assign_zcode(obj):
    global num_zcodes
    if obj not in obj_to_zcode:
        obj_to_zcode[obj] = num_zcodes
        num_zcodes += 1

def convert_zint_to_zstr():
    global zstr_len
    zstr_len = 1
    while (num_zcodes > 93**zstr_len):
        zstr_len += 1

    for obj in obj_to_zcode:
        zint = obj_to_zcode[obj]
        zstr = ""
        for i in range(zstr_len):
            (zint, rem) = divmod(zint, 93)
            c = rem + 32
            if c >= 34:
                c += 1
            if c >= 92:
                c += 1
            zstr = chr(c) + zstr
        obj_to_zcode[obj] = zstr
        # print(zstr)

def get_zstr(obj):
    return obj_to_zcode[obj]
