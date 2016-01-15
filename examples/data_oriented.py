'''
First example showing a Data Oriented ORM with object-instance like 
data accessors

This file is part of Data Oriented Python.
Copyright (C) 2016 Elliot Hallmark (permfacture@gmail.com)

Data Oreinted Python is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

Data Oriented Python is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

'''

import numpy as np
from numpy import sin, cos, pi, sqrt
from math import atan2
import pyglet
from pyglet import gl
from collections import namedtuple

#TODO make running examples not require path mangling
import sys
sys.path.append('..') #to get from examples to DOP
from DOP.datadomain import DataDomain, ArrayAttribute, SingleAttribute

class PolygonDomain(DataDomain):
    '''Data Domain for convex polygons to be rendered in pyglet
    TODO: push DOP related code to a DataDomain class and put polygon
    rendering specific code into a subclass'''
    dtype_tuple = namedtuple('Dtype',('np','gl'))
    vert_dtype = dtype_tuple(np.float32,gl.GL_FLOAT)
    color_dtype = dtype_tuple(np.float32,gl.GL_FLOAT)

    def __init__(self,size=16):
      super(PolygonDomain,self).__init__(size=size)

      #arrayed data
      self.data = ArrayAttribute(size,5,np.float32)
      self.verts = ArrayAttribute(size,2,self.vert_dtype.np)
      self.colors = ArrayAttribute(size,3,self.color_dtype.np)
      self.array_attributes.extend([self.data,self.verts,self.colors])

      #property data
      self.positions = SingleAttribute('position',2,np.float32)
      self.angles = SingleAttribute('angle',1,np.float32)
      self.single_attributes.extend([self.positions, self.angles])
 
      self.DataAccessor = self.generate_accessor('PolygonDataAccessor')


    def polyOfN(self,radius,n):
        '''helper function for making polygons'''
        r=radius
        if n < 3:
            n=3
        da = 2*pi/(n)     #angle between divisions
        return [[r*cos(da*x),r*sin(da*x)] for x in range(n)]


    def add(self,n,r,position=(0,0),color=(1,0,0)):
      '''add a regular convex polygon with n sides or radius r'''
      #TODO assert shape of pos and color
      pts = self.polyOfN(r,n)
      data = self.gen_data(pts)
      n = len(data) 

      start = self.safe_alloc(n)
      selector = slice(start,start+n,1)
      
      index = self.positions.add(position)
      self.angles.add(0)
      self.indices[selector] = index

      self.data[selector] = data
      self.colors[selector] = color #relies on broadcasting

      id =self._next_id 
      self._id2index_dict[id] = index
      self._next_id += 1
      return self.DataAccessor(self,id)

    def gen_data(self,pts): 
        l = len(pts)
        #wind up the vertices, so we don't have to do it when speed counts.
        #I dont really know which is clock wise and the other counter clock wise, btw
        cw = pts[:l//2]
        ccw = pts[l//2:][::-1]
        flatverts = [None]*(l)
        flatverts[::2]=ccw
        flatverts[1::2]=cw
        wound = [flatverts[0]]+flatverts+[flatverts[-1]]
        #prewound vertices can be transformed without care for winding.
        #Now, store the vertices in a way that can be translated as efficiently as possible later 
        #construct list of (x,y,r, x_helper, y_helper)
        #note that from alpha to theta, x changes by r*[cos(theta+alpha)-cos(alpha)]
        #lets call the initial angle of a vert alpha
        #so later, at theta, we want to remember cos(alpha) and sin(alpha)  
        #they are the helper values
        return [(pt[0],pt[1],sqrt(pt[0]**2+pt[1]**2),
              cos(atan2(pt[1],pt[0])),sin(atan2(pt[1],pt[0]))) for pt in wound]

    def update_vertices(self):
        '''Update vertices to render based on positions and angles communicated
        through the data accessors'''
        initiald = self.data

        all_valid = self.get_selector()
        end = all_valid.stop   #TODO need a way to add slices/selectors togther 
        indices = self.indices[:end]
        angles = self.angles[:]
        positions = self.positions[:]
        cos_ts, sin_ts = cos(angles), sin(angles)
        cos_ts -= 1
        #here's a mouthfull.  see contruction of initial_data in init.  sum-difference folrmula applied 
        #and simplified.  work it out on paper if you don't believe me.
        xs, ys, rs, xhelpers, yhelpers = (initiald[:end,x] for x in range(5))
       
        pts = self.verts
        

        pts[:end,0] = xhelpers*cos_ts[indices]  #this is how singles are broadcast to plurals
        pts[:end,1] = yhelpers*sin_ts[indices]      
        pts[:end,0] -= pts[:end,1]                 
        pts[:end,0] *= rs                
        pts[:end,0] += xs                
        pts[:end,0] += positions[indices,0]

        pts[:end,1] = yhelpers*cos_ts[indices]
        tmp = xhelpers*sin_ts[indices]
        pts[:end,1] += tmp
        pts[:end,1] *= rs
        pts[:end,1] += ys
        pts[:end,1] += positions[indices,1]

        #flatten and return as correct type
        #pts.shape = ( reduce(lambda xx,yy: xx*yy, pts.shape), )
        #return pts.astype(vert_dtype.np_type)

    def draw(self):
        gl.glClearColor(0.2, 0.4, 0.5, 1.0)
        gl.glBlendFunc (gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)                             
        gl.glEnable (gl.GL_BLEND)                                                            
        gl.glEnable (gl.GL_LINE_SMOOTH);                                                     
        gl.glEnableClientState(gl.GL_VERTEX_ARRAY)
        gl.glEnableClientState(gl.GL_COLOR_ARRAY)

        all_valid=self.get_selector()
        #TODO verts._buffer.ctypes.data is awkward
        gl.glVertexPointer(2, self.vert_dtype.gl, 0, self.verts._buffer.ctypes.data)
        gl.glColorPointer(3,  self.color_dtype.gl, 0, self.colors._buffer.ctypes.data)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, len(self.verts[all_valid]))

if __name__ == '__main__':
    width, height = 640,480
    window = pyglet.window.Window(width=width, height=height, vsync=False)
    fps_display = pyglet.clock.ClockDisplay()
    text = """Data Domain"""
    label = pyglet.text.HTMLLabel(text, x=10, y=height-10)

    test_domain=PolygonDomain()
    create = test_domain.add

    ## Create shapes
    n=100
    positions = [(x*width,y*height) for x,y in np.random.random((n,2))]
    poly_args = [(r*50,int(m*10)+3) for r,m in np.random.random((n,2))] 
    colors = np.random.random((n,3)).astype(test_domain.color_dtype.np)


    ents = [create(m,r,position=pos, color=col) for (r,m),pos,col in zip(poly_args,positions,colors)]

    angles= [0]*n
    rates = list(np.random.random(n)*.02)

    @window.event
    def on_draw():
        global angles

        window.clear()
        for i, ent in enumerate(ents):
          ent.angle+=rates[i]

        test_domain.update_vertices()
        test_domain.draw()
        fps_display.draw()

    pyglet.clock.schedule(lambda _: None)

    pyglet.app.run()
