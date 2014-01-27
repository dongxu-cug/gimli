#!/usr/bin/env python
# -*- coding: utf-8 -*-

import numpy as np

#from geomagnetics import GeoMagT0, date

mu0 = 4.0 * np.pi * 1e-7

G = 6.6742e-11 # in [m³/(kg s²)]
G = 6.6742e-11 / 1e-5 # / mGal

deltaACyl = lambda R__, rho__: 2. * np.pi * R__**2. * rho__ #[m^2 * kg/m³] = [kg/m]
deltaMSph = lambda R__, rho__: 4./3. * np.pi * R__**3. * rho__ #[kg]
rabs   = lambda r__: np.asarray([np.sqrt(x__.dot(x__)) for x__ in r__])
gradR  = lambda r__: (r__.T / rabs(r__))
adot = lambda M__, x__: np.asarray([(a__.dot(M__)) for a__ in x__]) 


#def magnetization(lat, lon, suszept, dat=date.today()): 
    #'''
    #'''
    #T0, I, D = GeoMagT0(lat, lon, dat) 
    #'''indizierte Magnetisierung'''
    #Mi = 1./mu0 * suszept * T0  
    #'''remanente Magnetisierung'''
    #Mr = 0. 

    #print T0, I, D, "abs: ", np.sqrt(T0.dot(T0))

    #return Mr + Mi;
## magnetization(...)
        

def dBZPoly(pnts, poly, M, openPoly=False):
    '''
        pnts Measurment points = [[p1x, p1z], [p2x, p2z],...]
        poly Polygon = [[p1x, p1z], [p2x, p2z],...]
        Magnetization = [M_x, M_y, M_z]
        
    '''
    dg, dgz = calcPolyGz(pnts, poly, 1.0, openPoly)   
    return poissonEoetvoes(adot(M, -dgz))
   
def dBZKugel(pnts, R, pos, M):
    """
    Calculate the vertical component of the magnetic response dBz for a buried
    sphere at position pos with radius R for a given magnetization M at
    measurement points pnts.

    pnts: measurement points -- array[x,y,z]
    R: radius -- float
    pos: sphere center -- [x,y,z]
    M: magnetization -- [Mx, My, Mz]
    """
    return poissonEoetvoes(adot(M, gradGZKugel(pnts, R, rho=1.0, pos=pos)))

def dBZZylinderHoriz(pnts, R, pos, M):
    """"""
    return poissonEoetvoes(adot(M, gradGZZylinderHoriz(pnts, R, rho=1.0, pos=pos)))
    
def poissonEoetvoes(dg):
    """"""
    return mu0/(4.0 * np.pi * G) * dg
#def poissonEoetvoes(...)
    
def uKugel(r, R, rho, pos=[0., 0., 0.]):
    """
    Gravitationspotential einer Kugel mit Radius R und Dichte rho an pos.

    u = -G * dM * 1/r
    """
    return -G * deltaMSph(R, rho) * 1. / rabs(r - pos)

def gradUKugel(r, R, rho, pos=[0., 0., 0.]):
    '''
        Gravitationsfeldstärke einer Kugel mit Radius R und Dichte rho an pos 
        g = -grad u, return [gx, gy, gz]
        g = -G[m³/(kg s²)] * dM[kg] * 1/r²[1/m²] * grad(r)[1/1] = [m³/(kg s²)] * [kg] * 1/m² * [1/1] == m/s²
    '''
    
    # gesucht eigentlich g_z aber nach unten als -z
    return [1., 1., -1.] * (gradR(r - pos) * - G * deltaMSph(R, rho) * 1. / (rabs(r - pos)**2)).T
#def gKugel(...)
    
def gradGZKugel(r, R, rho, pos=[0., 0., 0.]):
    '''
        g = -grad u, 
        return grad gz [gz_x gz_y, gz_z]
    '''
    t = pos[2]
    
    gzxyz = np.asarray([-3.0 * t * r[:,0], 
                        -3.0 * t * r[:,1], 
                         2.0 * t*t - r[:,0]**2 - r[:,1]**2])
    return (G * deltaMSph(R, rho) / rabs(r - pos)**5. * gzxyz).T


def uZylinderHoriz(pnts, R, rho, pos=[0., 0.]):
    """"""
    u = np.zeros(len(pnts))
    for i, r in enumerate(rabs(pnts-pos)):
        if r > R:
            u[i] = -2 * np.pi * G * R * R * rho * np.log(r / R)
        else:
            u[i] =    - np.pi * G * rho(r * r - R * R)
    
    return u
    
    
def gradUZylinderHoriz(r, R, rho, pos=[0., 0.]):
    '''
        calculate horizontal component of gravimetric field in mGal
        R   = cylinder radius in [Meter]
        p   = cylinder center (x, z) 
        rho = density in [kg/m^3]
        g = -G[m³/(kg s²)] * dM[kg/m] * 1/r[1/m] * grad(r)[1/1] = [m³/(kg s²)] * [kg/m] * 1/m * [1/1] == m/s²
        
    '''
    return [1., -1.0] * (gradR(r - pos) * -G * deltaACyl(R, rho) * 1. / (rabs(r - pos))).T 
#def gZylinderHoriz():


def gradGZZylinderHoriz(r, R, rho, pos=[0., 0.]):
    '''
        g = -grad u(r), with r = [x,z], |r| = \sqrt(x^2+z^2)
        return grad gz [gz_x, gz_z]
    '''
    t = pos[1]
    
    gz_xz = np.asarray([-2.0 * r[:,0]*(t - r[:,1]), 
                         1.0 * (- r[:,0]**2 + (t - r[:,1])**2)])
    
    return (G * deltaACyl(R, rho) / rabs(r - pos)**4. * gz_xz).T
#def gZKugel(...)


def gzHalfPlateHoriz(pnts, t, rho, pos=[0.0, 0.0]):
    '''
        g = -grad u, return z-component of g;  grad (d u/d r)_z
    '''
    gz = np.zeros(len(pnts))
    
    for i, q in enumerate(pnts):
        zz1 = q[1] - pos[1]
        xx1 = q[0] - pos[0]
        #gz[i] = G * rho * (np.pi - 2. * np.arctan((q[0] - pos[0]) / (q[2] - pos[2])))
        #in -z richtung
        gz[i] = -G * rho * t*(np.pi + 2.0 * np.arctan2(xx1, zz1)) * -1.
        #gz[i] = G * rho * (np.pi)

    return gz
#def gzPlatteHoriz(...)

def gradGZHalfPlateHoriz(pnts, t, rho, pos=[0.0, 0.0]):
    '''
        g = -grad u, return z-component of g;  grad (d u/d r)_z
    '''
    gz = np.zeros((len(pnts), 2))
    
    for i, q in enumerate(pnts):
        
        zz1 = q[1] - pos[1]
        xx1 = q[0] - pos[0]
        
        gz[i,0] = -2.0 * G * rho * t *((zz1)/(xx1*xx1 + zz1*zz1))
        gz[i,1] =  2.0 * G * rho * t *((xx1)/(xx1*xx1 + zz1*zz1))

    return gz
#def gzPlatteHoriz(...)


def lineIntegralZ_WonBevis(p1, p2):
    """
    WonBevis1987.

    Return g = -grad u =(Fx, 0.0, Fz), dFz(Fzx, Fzy, Fzz)
    """
    #print p1, p2
    x1 = p1[0]
    z1 = p1[1]
    x2 = p2[0]
    z2 = p2[1]
   
    x21 = x2 - x1
    z21 = z2 - z1
    z21s = z21 * z21
    x21s = x21 * x21
    
    xz12 = x1 * z2 - x2 * z1
    
    if x1 == 0. and z1 == 0.:
        return np.asarray((0.0, 0.0, 0.0)), np.asarray((0.0, 0.0, 0.0))
    if x2 == 0. and z2 == 0.:
        return np.asarray((0.0, 0.0, 0.0)), np.asarray((0.0, 0.0, 0.0))
    
    theta1 = np.arctan2(z1, x1)
    theta2 = np.arctan2(z2, x2)

    r1s = x1 * x1 + z1 * z1
    r2s = x2 * x2 + z2 * z2
    r1 = np.sqrt(r1s)
    r2 = np.sqrt(r2s)
    
    r21s = x21s + z21s
    R2 = r21s
    
    rln = np.log(r2 / r1)
        
    p = (xz12/r21s) * ((x1*x21 - z1*z21)/r1s - (x2*x21 - z2*z21)/r2s)
    q = (xz12/r21s) * ((x1*z21 + z1*x21)/r1s - (x2*z21 + z2*x21)/r2s)
    
    Fz = 0.0 
    Fx = 0.0
    Fzx = 0.0 # dFz/dx
    Fzz = 0.0 # dFz/dz
    
    if np.sign(z1) != np.sign(z2):
        if (x1*z2 < x2*z1) and z2 >=0.0: 
            theta1 = theta1 + 2.* np.pi
        
        if (x1*z2 > x2*z1) and z1 >=0.0: 
            theta2 = theta2 + 2.* np.pi
        
    if x1*z2 == x2*z1:
        return np.asarray((0., 0.0, 0.)), np.asarray((0., 0.0, 0.))
            
    th12 = (theta1 - theta2)
    
    if abs(x21) < 1e-4: 
        #print "case 3"
        #case 3
        Fz = x1 * rln
        Fx = 0.0
        Fzz = -p
        Fzx = q - z21s/r21s * rln
        #print Zz, Zx, R2, x1, z1, x2, z2
        
    else: #default
        B = z21 / x21
        A = (x21 * xz12) / R2

        Fz = A * (th12 + B * rln)
        Fx = A * (-th12 * B + rln)
        z21dx21 = z21 / x21
        z21x21 = z21 * x21
        
        fz = (th12 + z21dx21 * rln)/r21s
                
        Fzz = -p + x21s * fz
        Fzx = q - x21*z21 * fz
    
        #// check this
        #fx = (th12 * z21dx21 - rln)/r21s
    
    return np.asarray((Fx, 0.0, Fz)), np.asarray((Fzx, 0.0, Fzz))

def calcPolyGz(pnts, poly, density=1, openPoly=False, forceOpen=False):
    """
    Calculate 2D gravimetric response at given points for a polygon with
    relative density change.

    pnts must be numbered clockwise. Else change the sign of the result.
    Return values are in mGal.
    """
    
    qpnts = pnts
    N = len(pnts)
    
    if np.size(pnts[0]) == 1:
        qpnts = list(zip(pnts,np.zeros(N)))
    
    if not forceOpen:
        if np.linalg.norm(poly[0] - poly[-1], 2) < 1e-8: openPoly=True
    
    gz = np.zeros((N,3))
    gzz = np.zeros((N,3))
        
    for i, p in enumerate(qpnts):
        for j in range(len(poly) - (openPoly)):
            a = poly[j]
            b = poly[(j + 1)%len(poly)]
        #    print "a, b", a, b
            gzi, gzzi = lineIntegralZ_WonBevis(a - p, b - p)
         
          #  print gzi, gzzi
            gz[i,:] += -gzi *[1.0, 1.0, -1.0]
            gzz[i,:] += -gzzi 

        
    return density * 2.0 * -G * gz, density * 2.0 * -G * gzz
# def calcPolydgdz()

def angle(p1, p2, p3, Un):
    """
    Finds the angle between planes O-p1-p2
    and O-p2-p3, where p1,p2,p3 are coordinates of three points,
    taken in ccw order as seen from origin O. This is used by
    gravMag for finding the solid angle subtended by a polygon
    at the origin. Un is the unit outward normal vector to the
    polygon.

    @ARTICLE{SinghGup2001,
        author = {Bijendra Singh and D. Guptasarma},
        title = {{N}ew method for fast computation of gravity and magnetic anomalies
                from arbitrary polyhedra},
        journal = {Geophysics},
        year = {2001},
        volume = {66},
        pages = {521-526}}
        
    """
    
    #Check if face is seen from inside
    
    inout = np.sign(Un.dot(p1))
    
    x2 = p2[0]
    y2 = p2[1]
    z2 = p2[2]
    
    # seen from inside; interchange p1 and p3
    if inout > 0 :
        x3 = p1[0]
        y3 = p1[1]
        z3 = p1[2]
        x1 = p3[0]
        y1 = p3[1]
        z1 = p3[2]
    elif inout < 0:
        x1 = p1[0]
        y1 = p1[1]
        z1 = p1[2]
        x3 = p3[0]
        y3 = p3[1]
        z3 = p3[2]
    else:
        ang = 0.0
        perp = 1.0
        return ang, perp

    # Normals
    n1 = np.asarray([y2*z1 - y1*z2, x1*z2 - x2*z1, x2*y1 - x1*y2])
    n2 = np.asarray([y3*z2 - y2*z3, x2*z3 - x3*z2, x3*y2 - x2*y3]) * -1.0
    
    n1 = n1/np.linalg.norm(n1)
    n2 = n2/np.linalg.norm(n2)
    
    perp = np.sum([x3, y3, z3] * n1)
    
    # sign of perp is -ve if points p1 p2 p3 are in cw order
    perp = np.sign(perp)
    r = np.sum((n1 * n2))
    ang = np.arccos(r) 
    
    if perp < 0:
        ang = 2.0 * np.pi - ang 
    
    
    return ang, perp
# angle(...)


def gravMagBoundarySinghGup(boundary):
    """
    Calculate [Fx, Fy, FZ] and [Fzx, Fzy, Fzz] at Origin for a given boundary.

    @ARTICLE{SinghGup2001,
    author = {Bijendra Singh and D. Guptasarma},
    title = {{N}ew method for fast computation of gravity and magnetic
             anomalies from arbitrary polyhedra},
    journal = {Geophysics},
    year = {2001},
    volume = {66},
    pages = {521-526}}
    """
    shape = boundary.shape()
    #print shape

    r = shape.center()
    u = shape.norm()
    di = r.dot(u)

    P = 0.   
    Q = 0.
    R = 0.

    l = u[0]
    m = u[1]
    n = u[2]

    # Berechne Raumwinkel
    W = 0
    for i in range(shape.nodeCount()):
        p1 = shape.node(i).pos()
        p2 = shape.node((i+1)%shape.nodeCount()).pos()
        p3 = shape.node((i+2)%shape.nodeCount()).pos()
    
        a, p = angle(p1, p2, p3, u) 
        W += a
                
    W -= (shape.nodeCount() - 2) * np.pi

    fsign = float(np.sign(u.dot(shape.node(0).pos())))
    Omega = -fsign * W
    
    for i in range(shape.nodeCount()):
       
        vr1 = shape.node(i).pos()
        vr2 = shape.node((i+1)%shape.nodeCount()).pos()

        r1 = vr1.abs()

        L = (vr2-vr1).abs()

        Lx = vr2[0] - vr1[0]
        Ly = vr2[1] - vr1[1]
        Lz = vr2[2] - vr1[2]
    
        b = 2.*(vr1[0] * Lx + vr1[1] * Ly + vr1[2] * Lz)
    
        b2 = b/L/2.
        if r1 + b2 == 0:
            I = (1.0/L) * np.log((L - r1)/r1)
        else:
            I = (1.0/L) * np.log((np.sqrt(L*L + b + r1*r1) + L + b2)/(r1 + b2))

        #print I, L, b, r1,  Lx, Ly, Lz
        P += I * Lx
        Q += I * Ly
        R += I * Lz

    #print "norm:", u
    #print Omega, l, m, n, P, Q, R
    #exitd
    #print "r", r
    
    Fx = di * (l * Omega + n * Q - m * R)
    Fy = di * (m * Omega + l * R - n * P)
    Fz = di * (n * Omega + m * P - l * Q)
    
    #M = [25.575706359959149,    0.000000000000000,   30.479939937615899]
    M = [0, 0, -1.0]
    Pd = u.dot(M)
    
    Fzx = Pd * (l * Omega + n * Q - m * R)
    Fzy = Pd * (m * Omega + l * R - n * P)
    Fzz = Pd * (n * Omega + m * P - l * Q)
     
    #print Fx, Fy, Fz, Fzx, Fzy, Fzz
    #Fzx, Fzy, Fzz = Fz* u
    #exitd
    return np.asarray([Fx, Fy, Fz]), np.asarray([Fzx, Fzy, Fzz]), 


def grav(mesh, pnts, rho):
    """Return."""
    dg = np.zeros((len(pnts), 3))
    dgz = np.zeros((len(pnts), 3))
    upoly = np.zeros(len(pnts))
    
    for i, p in enumerate(pnts):
        mesh.translate(-p)
                    
        for b in mesh.boundaries():
            if b.marker() != 0:
                
                if mesh.dimension() == 2:
                    dgi, dgzi = lineIntegralZ_WonBevis(b.node(0).pos(),
                                                       b.node(1).pos())
                    dgi *= -2.0
                    dgzi *= -2.0
                else:
                    dgi, dgzi = gravMagBoundarySinghGup(b)
                
        
                dg[i]  += dgi * -G * rho
                dgz[i] += dgzi * -G * rho

        mesh.translate(p)

    return dg * [1.0, 1.0, -1.0], dgz
    
def buildCircle(pos, radius, segments=12, leftDirection=True):
    """"""
    poly = np.zeros((segments, 2))
    poly[0, :] = (0, radius)
    for i in range(1, segments):
        if leftDirection:
            xp = np.sin( -i * (2. * np.pi) / segments)
        else:
            xp = np.sin( i * (2. * np.pi) / segments)
            
        yp = np.cos( i * (2. * np.pi) / segments)
        poly[i, :] = (xp * radius, yp * radius)
        
    poly = poly + pos
    return poly
# def buildCircle(pos, radius, segments)

if __name__ == "__main__":
    print(sys.argv[1:])
    print("do some tests here")
    
    
    #print lineIntegralZ([-2,-2], [2,-2])
    
    #exit(1)