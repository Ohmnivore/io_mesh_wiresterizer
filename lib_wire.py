import struct

class WireOptions:

    def __init__(self):
        self.version = -1
        self.header = False
        self.text_mode = False
        self.triangles = False
        self.indexing = False
        self.vertex_normals = False
        self.face_normals = False

    def uses_normals(self):
        return self.vertex_normals or self.face_normals


# Text header export
def _text_write_header_magic_code(_options, file_write):
    file_write('# Wiresterizer\n')

def _text_write_header_opts(options, file_write):
    file_write('# Version %d\n' % options.version)

    if options.triangles:
        file_write('# Triangles\n')
    if options.indexing:
        file_write('# Indexing\n')
    if options.vertex_normals:
        file_write('# Vertex normals\n')
    if options.face_normals:
        file_write('# Face normals\n')


# Binary header export
# WIRE in ASCII, 1464422981 in decimal
BIN_MAGIC_CODE = 0x57495245

# First 10 bits
BIN_VERSION_MASK = 0b1111111111

# 11th bit
BIN_TRIANGLES_POS = 10
BIN_TRIANGLES_BIT = 1 << BIN_TRIANGLES_POS

# 12th bit
BIN_INDEXING_POS = 11
BIN_INDEXING_BIT = 1 << BIN_INDEXING_POS

# 13th bit
BIN_VERTEX_NORMALS_POS = 12
BIN_VERTEX_NORMALS_BIT = 1 << BIN_VERTEX_NORMALS_POS

# 14th bit
BIN_FACE_NORMALS_POS = 13
BIN_FACE_NORMALS_BIT = 1 << BIN_FACE_NORMALS_POS

# Another 18 bits are available for later additions to the header

def _bin_write_header_magic_code(_options, file_write):
    code_packed = struct.pack('>i', BIN_MAGIC_CODE)
    file_write(code_packed)

def _bin_write_header_opts(options, file_write):
    if options.version > BIN_VERSION_MASK or options.version < 0:
        raise Exception('Invalid format version')

    version = options.version
    triangles_bit = options.triangles << BIN_TRIANGLES_POS
    indexing_bit = options.indexing << BIN_INDEXING_POS
    vertex_normals_bit = options.vertex_normals << BIN_VERTEX_NORMALS_POS
    face_normals_bit = options.face_normals << BIN_FACE_NORMALS_POS

    header_word = version | triangles_bit | indexing_bit | vertex_normals_bit | face_normals_bit
    header_word_packed = struct.pack('>i', header_word)
    file_write(header_word_packed)


# Text face export
def _text_write_face_start(_options, file_write, _face):
    file_write('f')

def _text_write_face_end(_options, file_write, _face):
    file_write('\n')

def _text_write_face_norm(_options, file_write, _face, norm):
    file_write(' %.4f %.4f %.4f' % (norm.x, norm.y, norm.z))

def _text_write_face_vert(_options, file_write, _face, vert):
    file_write(' %.6f %.6f %.6f' % (vert.pos.x, vert.pos.y, vert.pos.z))


# Binary face export
def _bin_write_face_start(_options, _file_write, _face):
    pass

def _bin_write_face_end(_options, _file_write, _face):
    pass

def _bin_write_face_norm(_options, _file_write, _face, _norm):
    pass

def _bin_write_face_vert(_options, _file_write, _face, _vert):
    pass


# High-level logic
def open_file(options, file_path):
    if options.text_mode:
        # Open file for UTF8 writing
        return open(file_path, "w", encoding="utf8", newline="\n")

    else:
        # Open file for binary writing
        return open(file_path, "wb")

def close_file(options, file):
    file.close()

def write_header(options, file_write):
    if options.text_mode:
        # Assign text functions
        write_header_magic_code = _text_write_header_magic_code
        write_header_opts = _text_write_header_opts

    else:
        # Assign binary functions
        write_header_magic_code = _bin_write_header_magic_code
        write_header_opts = _bin_write_header_opts

    # Write header
    if options.header:
        write_header_magic_code(options, file_write)
        write_header_opts(options, file_write)

def write_face(options, file_write, face):
    if options.text_mode:
        # Assign text functions
        write_face_start = _text_write_face_start
        write_face_end = _text_write_face_end
        write_face_norm = _text_write_face_norm
        write_face_vert = _text_write_face_vert

    else:
        # Assign binary functions
        write_face_start = _bin_write_face_start
        write_face_end = _bin_write_face_end
        write_face_norm = _bin_write_face_norm
        write_face_vert = _bin_write_face_vert

    write_face_start(options, file_write, face)

    if options.indexing:
        raise Exception('Indexed mode not yet supported')
    else:
        if options.face_normals:
            write_face_norm(options, file_write, face, face.norm)

        for vert in face.vertexes:
            write_face_vert(options, file_write, face, vert)

            if options.vertex_normals:
                raise Exception('Vertex normals not yet supported')

    write_face_end(options, file_write, face)
