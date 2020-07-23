import numpy as np
import gdal, osr
import sys
    
class navpath:
  # A list of loc objects, representing a path. Along with some useful
  # metadata
  def __init__(self, csys = None, navdat = None):
    self.navdat = navdat
    self.csys = csys


  def copy(self):
    # Returns a copy of the Pointlist
    return navpath(self.csys,self.navdat)


  def transform(self,targ):
    #print(self)
    # Transforms a Pointlist to another coordinate system, can read Proj4 format
    # and WKT

    navpath = self.copy()

    source = osr.SpatialReference()  
    target = osr.SpatialReference()  

    # Deciding whether the coordinate systems are Proj4 or WKT
    sc0 = self.csys[0]
    if(sc0 == 'G' or sc0 == 'P'):
      source.ImportFromWkt(navpath.csys)
    else:
      source.ImportFromProj4(navpath.csys)

    tc0 = targ[0]
    if(tc0 == 'G' or tc0 == 'P'):
      target.ImportFromWkt(targ)
    elif(tc0 == '+'):
      target.ImportFromProj4(targ)
    else:
      print("Unrecognized target coordinate system:")
      print(targ)
      sys.exit()

    nav_xform = np.zeros(navpath.navdat.shape)

    # The actual transformation
    transform = osr.CoordinateTransformation(source, target)
    xform = transform.TransformPoint

    for _i in range(navpath.navdat.shape[0]):  
      nav_xform[_i,:] = np.asarray(xform(navpath.navdat[_i,0],navpath.navdat[_i,1],navpath.navdat[_i,2]))

    navpath.navdat = nav_xform
    navpath.csys = targ
    return navpath

def transformPt(nav, in_csys, out_csys):
  # Transforms a point to another coordinate system, can read Proj4 format
  # and WKT

  # The actual transformation
  transform = osr.CoordinateTransformation(in_csys, out_csys)
  npt = transform.TransformPoint(nav[:,0],nav[:,1], nav[:,2]) # x, y, z data list

  return npt