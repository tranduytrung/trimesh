'''
trimesh.py

Library for importing and doing simple operations on triangular meshes
Styled after transformations.py
'''

import numpy as np
import time, struct
from collections import deque

def load_mesh(file_obj, type=None):
    #Load a mesh file into a Trimesh object
    mesh_loaders = {'stl': load_stl, 
                    'obj': load_wavefront}
    if type == None and file_obj.__class__.__name__ == 'str':
        type = (str(file_obj).split('.')[-1]).lower()
        file_obj = open(file_obj, 'rb')
    
    if type in mesh_loaders:
        mesh = mesh_loaders[type](file_obj)
        file_obj.close()
        return mesh
    else: raise NameError('No mesh loader for files of type .' + type)

class Trimesh():
    def __init__(self, 
                 vertices      = None, 
                 faces         = None, 
                 normal_face   = None, 
                 normal_vertex = None,
                 edges         = None, 
                 color_face    = None,
                 color_vertex  = None):
        self.vertices      = vertices
        self.faces         = faces
        self.normal_face   = normal_face
        self.normal_vertex = normal_vertex
        self.edges         = edges
        self.color_face    = color_face
        self.color_vertex  = color_vertex

    def cross_section(self, 
                      plane_origin=[0,0,0], 
                      plane_normal=[0,0,1], 
                      return_planar=True,
                      TOL=1e-9):
        '''
        Return a cross section of the trimesh based on plane origin and normal. 
        Basically a bunch of plane-line intersection queries with validation checks.
        Depends on properly ordered edge information, as done by generate_edges

        origin:        (3) array of plane origin
        normal:        (3) array for plane normal
        return_planar: bool, if True returns (m, 2) planar crossection, False returns (m, 3)
        TOL:           float, cutoff tolerance for 'in plane'
        
        returns: lines (in point pair format) of cross section, for example: 
                     [A,B,C,D,E,A], where lines are AB CD EA
        '''
        if len(self.faces) == 0: raise NameError("Cannot compute cross section of empty mesh.")
        self.generate_edges()
        
        #dot products of edge vertices and plane normal
        d0 = np.dot(self.vertices[[self.edges[:,0]]] - plane_origin, plane_normal)
        d1 = np.dot(self.vertices[[self.edges[:,1]]] - plane_origin, plane_normal)

        hits = np.logical_not(np.logical_xor((d0 > 0), (d1 <= 0)))

        #line endpoints for plane-line intersection
        p0 = self.vertices[[self.edges[hits][:,0]]]
        p1 = self.vertices[[self.edges[hits][:,1]]]
        
        #this results in a set of unmerged point pairs like: 
        #[A,B,C,D,E,A], where lines are AB CD EA
        intersections = plane_line_intersection(plane_origin, plane_normal, p0, p1)

        if return_planar: 
            return points_to_plane(intersections, plane_origin, plane_normal).reshape((-1,2,2))
        else: 
            return intersections

    def convex_hull(self, merge_radius=1e-3):
        '''
        Get a new Trimesh object representing the convex hull of the 
        current mesh. Requires scipy >.12, and doesn't produce properly directed normals

        merge_radius: when computing a complex hull, at what distance do we merge close vertices 
        '''
        from scipy.spatial import ConvexHull
        mesh = Trimesh()
        mesh.vertices = self.vertices
        mesh.faces = np.array([])
        mesh.merge_vertices(merge_radius)
        mesh.faces = ConvexHull(mesh.vertices).simplices
        mesh.remove_unreferenced()
        return mesh

    def merge_vertices(self, tolerance=1e-7):
        '''
        Merges vertices which are identical and replaces references
        Does this by creating a KDTree.
        cKDTree requires scipy >= .12 for this query type and you 
        probably don't want to use plain python KDTree as it is crazy slow (~1000x in my tests)

        tolerance: to what precision do vertices need to be identical
        '''
        from scipy.spatial import cKDTree as KDTree

        tree    = KDTree(self.vertices)
        used    = np.zeros(len(self.vertices), dtype=np.bool)
        unique  = []
        replacement_dict = dict()

        for index, vertex in enumerate(self.vertices):
            if used[index]: continue
            neighbors = tree.query_ball_point(self.vertices[index], tolerance)
            used[[neighbors]] = True
            replacement_dict.update(np.column_stack((neighbors,
                                                     [len(unique)]*len(neighbors))))
            unique.append(index)
        self.vertices = self.vertices[[unique]]
        replace_references(self.faces, replacement_dict)

    def remove_unreferenced(self):
        '''
        Removes all vertices which aren't in a face
        Reindexes vertices from zero and replaces face references
        '''
        referenced = self.faces.view().reshape(-1)
        unique_ref = np.int_(np.unique(referenced))
        replacement_dict = dict()
        replacement_dict.update(np.column_stack((unique_ref,
                                                 range(len(unique_ref)))))                                         
        replace_references(self.faces, replacement_dict)
        self.vertices = self.vertices[[unique_ref]]

    def generate_edges(self):
        '''
        Populate self.edges from face information
        '''
        self.edges = np.sort(np.vstack((self.faces[:,(0,1)],
                                        self.faces[:,(1,2)],
                                        self.faces[:,(2,0)])), axis=1)
        
    def generate_normals(self, fix_direction=False):
        '''
        If no normal information is loaded, we can get it from cross products
        Normal direction will be incorrect if mesh faces aren't ordered (right-hand rule)
        '''
        self.normal_face = np.zeros((len(self.faces),3))
        self.vertices = np.array(self.vertices)
        for index, face in enumerate(self.faces):
            v0 = (self.vertices[face[0]] - self.vertices[face[1]])
            v1 = (self.vertices[face[2]] - self.vertices[face[1]])
            self.normal_face[index] = np.cross(v0, v1)
        if fix_direction: self.fix_normals_direction()
            
    def fix_normals_direction(self):
        '''
        NONFUNCTIONAL
        Will eventually fix normals for a mesh. 
        '''
        visited_faces = np.zeros(len(self.faces))
        centroid = np.mean(self.vertices, axis=1)
        return None

    def transform(self, transformation_matrix):
        stacked = np.column_stack((self.vertices, np.ones(len(self.vertices))))
        self.vertices = np.dot(transformation_matrix, stacked.T)[:,0:3]

    def bounding_box(self):
        box = np.vstack((np.min(self.vertices, axis=0),
                         np.max(self.vertices, axis=0)))
        return box

    def generate_face_graph(self):
        '''
        Graph of face connections
        nodes are faces
        edges are connected faces
        edge weights are angles between faces
        '''
        import networkx as nx
        edge_graph = nx.graph
        for i, face in enumerate(self.faces):
            pass
        
        
    def export(self, filename):
        export_stl(self, filename)



def replace_references(data, reference_dict, return_array=False):
    '''
    Replace elements in an array as per a dictionary of replacement values

    data:           numpy array
    reference_dict: dictionary of replacements. example:
                       {2:1, 3:1, 4:5}

    return_array: if false, replaces references in place and returns nothing
    '''
    dv = data.view().reshape((-1))
    for i in xrange(len(dv)):
        if dv[i] in reference_dict:
            dv[i] = reference_dict[dv[i]]
    if return_array: return dv

def detect_binary_file(file_obj):
    '''
    Returns True if file has non-ascii charecters
    http://stackoverflow.com/questions/898669/how-can-i-detect-if-a-file-is-binary-non-text-in-python
    '''
    textchars = ''.join(map(chr, [7,8,9,10,12,13,27] + range(0x20, 0x100)))
    start     = file_obj.tell()
    fbytes    = file_obj.read(1024)
    file_obj.seek(start)
    return bool(fbytes.translate(None, textchars))

def plane_line_intersection(plane_ori, plane_dir, pt0, pt1):
    '''
    Calculates plane-line intersections

    plane_ori: plane origin, (3) list
    plane_dir: plane direction (3) list
    pt0: first list of line segment endpoints (n,3)
    pt1: second list of line segment endpoints (n,3)
    '''
    line_dir  = unitize(pt1 - pt0)
    plane_dir = unitize(plane_dir)
    t = np.dot(plane_dir, np.transpose(plane_ori - pt0))
    b = np.dot(plane_dir, np.transpose(line_dir))
    d = t / b
    return pt0 + np.reshape(d,(np.shape(line_dir)[0],1))*line_dir

def point_plane_distance(plane_ori, plane_dir, points):
    w = points - plane_ori
    return np.abs(np.dot(plane_dir, w.T) / np.linalg.norm(plane_dir))
    
def unitize(points):
    '''
    One liner which will unitize vectors by row
    axis arg to sum is so one vector (3,) gets vectorized correctly 
    as well as 10 vectors (10,3)

    points: numpy array/list of points to be unit vector'd
    '''
    points = np.array(points)
    return (points.T/np.sum(points ** 2, 
                            axis=(len(points.shape)-1)) ** .5 ).T
    
def major_axis(points):
    '''
    Returns an approximate vector representing the major axis of points
    '''
    sq = np.dot(np.transpose(points), points)
    d, v = np.linalg.eig(sq)
    return v[np.argmax(d)]
        
def surface_normal(points):
    '''
    Returns a normal estimate:
    http://www.lsr.ei.tum.de/fileadmin/publications/KlasingAlthoff-ComparisonOfSurfaceNormalEstimationMethodsForRangeSensingApplications_ICRA09.pdf

    points: (n,m) set of points

    '''
    return np.linalg.svd(points)[2][-1]

def radial_sort(points, origin=None, normal=None):
    '''
    Sorts a set of points radially (by angle) around an origin/normal

    points: (n,3) set of points
    '''
    #if origin and normal aren't specified, generate one at the centroid
    if origin==None: origin = np.average(points, axis=0)
    if normal==None: normal = surface_normal(points)
    
    #create two axis perpendicular to each other and the normal, and project the points onto them
    axis0 = [normal[0], normal[2], -normal[1]]
    axis1 = np.cross(normal, axis0)
    ptVec = points - origin
    pr0 = np.dot(ptVec, axis0)
    pr1 = np.dot(ptVec, axis1)

    #calculate the angles of the points on the axis
    angles = np.arctan2(pr0, pr1)

    #return the points sorted by angle
    return points[[np.argsort(angles)]]
               
def points_to_plane(points, origin=[0,0,0], normal=[0,0,1]):
    '''
    projects a set of (n,3) points onto a plane, returning (n,2) points
    '''
    axis0 = [normal[2], normal[0], normal[1]]
    axis1 = np.cross(normal, axis0)
    pt_vec = np.array(points) - origin
    pr0 = np.dot(pt_vec, axis0)
    pr1 = np.dot(pt_vec, axis1)
    return np.column_stack((pr0, pr1))
    
def mesh_to_plane(mesh, plane_normal= [0,0,1], TOL=1e-8):
    '''
    INCOMPLETE
    Orthographic projection of a mesh to a plane
    
    input
    mesh: trimesh object
    plane_normal: plane normal (3) list
    TOL: comparison tolerance

    output:
    list of non-overlapping but possibly adjacent polygons
    '''
    planar       = points_to_plane(mesh.vertices, plane_normal)
    face_visible = np.zeros(len(mesh.faces), dtype=np.bool)
    
    for index, face in enumerate(mesh.faces):
        dot = np.dot(mesh.normals[index], plane_normal)
        '''
        dot product between face normal and plane normal:
        greater than zero: back faces
        zero: polygon viewed on edge (zero thickness)
        less than zero: front facing
        '''
        if (dot < -TOL):
            face_visible[index] = True
    return planar[[face_visible]]


def unique_rows(data):
    '''
    Returns unique rows of an array, using string hashes. 
    '''
    first_occur = dict()
    unique      = np.ones(len(data), dtype=np.bool)
    for index, row in enumerate(data):
        hashable = row_to_string(row)
        if hashable in first_occur:
            unique[index]                 = False
            unique[first_occur[hashable]] = False
        else:
            first_occur[hashable] = index
    return unique

def row_to_string(row, format_str="0.6f"):
    result = ""
    for i in row:
        result += format(i, format_str)
    return result
    
def load_stl(file_obj):
    if detect_binary_file(file_obj): return load_stl_binary(file_obj)
    else:                            return load_stl_ascii(file_obj)
        
def load_stl_binary(file_obj):
    def read_face():
        normal_face[current[1]] = np.array(struct.unpack("<3f", file_obj.read(12)))
        for i in xrange(3):
            vertex = np.array(struct.unpack("<3f", file_obj.read(12)))               
            faces[current[1]][i] = current[0]
            vertices[current[0]] = vertex
            current[0] += 1
        #this field is occasionally used for color, but is usually just ignored.
        colors[current[1]] = int(struct.unpack("<h", file_obj.read(2))[0]) 
        current[1] += 1

    #get the file_obj header
    header = file_obj.read(80)
    #use the header information about number of triangles
    tri_count   = int(struct.unpack("@i", file_obj.read(4))[0])
    faces       = np.zeros((tri_count, 3),   dtype=np.int)  
    normal_face = np.zeros((tri_count, 3),   dtype=np.float) 
    colors      = np.zeros( tri_count,       dtype=np.int)
    vertices    = np.zeros((tri_count*3, 3), dtype=np.float) 
    #current vertex, face
    current   = [0,0]
    while True:
        try: read_face()
        except: break
    vertices = vertices[:current[0]]
    if current[1] <> tri_count: 
        raise NameError('Number of faces loaded is different than specified by header!')
    return Trimesh(vertices    = vertices, 
                   faces       = faces, 
                   normal_face = normal_face, 
                   color_face  = colors)

def load_stl_ascii(file_obj):
    def parse_line(line):
        return map(float, line.strip().split(' ')[-3:])
    def read_face(file_obj):
        normals.append(parse_line(file_obj.readline()))
        faces.append(np.arange(0,3) + len(vertices))
        file_obj.readline()
        for i in xrange(3):      
            vertices.append(parse_line(file_obj.readline()))
        file_obj.readline(); file_obj.readline()
    faces    = deque() 
    normals  = deque()
    vertices = deque()

    #get the file header
    header = file_obj.readline()
    while True:
        try: read_face(file_obj)
        except: break
    return Trimesh(faces       = np.array(faces,    dtype=np.int),
                   normal_face = np.array(normals,  dtype=np.float),
                   vertices    = np.array(vertices, dtype=np.float))

def load_wavefront(file_obj):
    '''
    Loads a Wavefront .obj file_obj into a Trimesh object
    Discards texture normals and vertex color information
    https://en.wikipedia.org/wiki/Wavefront_.obj_file
    '''
    def parse_face(line):
        #faces are vertex/texture/normal and 1-indexed
        face = [None]*3
        for i in xrange(3):
            face[i] = int(line[i].split('/')[0]) - 1
        return face
    vertices = deque()
    faces    = deque()
    normals  = deque()
    line_key = {'vn': normals, 'v': vertices, 'f':faces}

    for raw_line in file_obj:
        line = raw_line.strip().split()
        if len(line) == 0: continue
        if line[0] ==  'v': vertices.append(map(float, line[-3:])); continue
        if line[0] == 'vn': normals.append(map(float, line[-3:])); continue
        if line[0] ==  'f': faces.append(parse_face(line[-3:]));
    mesh = Trimesh(vertices      = np.array(vertices, dtype=float),
                   faces         = np.array(faces,    dtype=int),
                   normal_vertex = np.array(normals,  dtype=float))
    mesh.generate_normals()
    return mesh
    
def export_stl(mesh, filename):
    #Saves a Trimesh object as a binary STL file. 
    def write_face(file_object, vertices, normal):
        #vertices: (3,3) array of floats
        #normal:   (3) array of floats
        file_object.write(struct.pack('<3f', *normal))
        for vertex in vertices: 
            file_object.write(struct.pack('<3f', *vertex))
        file_object.write(struct.pack('<h', 0))
    if len(mesh.normals) == 0: mesh.generate_normals(fix_directions=True)
    with open(filename, 'wb') as file_object:
        #write a blank header
        file_object.write(struct.pack("<80x"))
        #write the number of faces
        file_object.write(struct.pack("@i", len(mesh.faces)))
        #write the faces
        for index in xrange(len(mesh.faces)):
            write_face(file_object, 
                       mesh.vertices[[mesh.faces[index]]], 
                       mesh.normals[index])    

if __name__ == '__main__':
    '''
    import os, time
    test_dir = './models'
    meshes = []
    for filename in os.listdir(test_dir):
        try:
            tic = time.clock()
            meshes.append(load_mesh(os.path.join(test_dir, filename)))
            toc = time.clock()
            print 'successfully loaded', filename, 'with', len(meshes[-1].vertices), 'vertices in', toc-tic, 'seconds.'
        except: print 'failed to load', filename
    '''


    m = load_mesh('./models/octagonal_pocket.stl')
    
    plane_ori = np.mean(m.bounding_box(), axis=0)
    plane_dir = [0,0,1]   
    
    m.merge_vertices()
    m.remove_unreferenced()
    p = points_to_plane(m.vertices, plane_ori, plane_dir)
    edge_dict = dict()
    tic = time.clock()
    for face_index, face in enumerate(m.faces):
        for i in xrange(3):
            key = np.sort(face[[np.mod(np.arange(2)+i,3)]]).tostring()
            if key in edge_dict: edge_dict[key].append(face_index)
            else:                edge_dict[key] = [face_index]
    toc = time.clock()
    print 'adjacency referenced in ', toc-tic
    