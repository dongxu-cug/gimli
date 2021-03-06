/***************************************************************************
 *   Copyright (C) 2008-2014 by the resistivity.net development team       *
 *   Carsten Rücker carsten@resistivity.net                                *
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 *   This program is distributed in the hope that it will be useful,       *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
 *   GNU General Public License for more details.                          *
 *                                                                         *
 *   You should have received a copy of the GNU General Public License     *
 *   along with this program; if not, write to the                         *
 *   Free Software Foundation, Inc.,                                       *
 *   59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.             *
 ***************************************************************************/

#ifndef GIMLI_MESHGENERATORS__H
#define GIMLI_MESHGENERATORS__H

#include "gimli.h"

namespace GIMLI{

/*! Unified interface. Generate simple grid with nodes at the given positions */
DLLEXPORT Mesh createGrid(const RVector & x);

/*! Unified interface. Generate simple grid with nodes at the given positions */
DLLEXPORT Mesh createGrid(const RVector & x, const RVector & y);

/*! Unified interface. Generate simple grid with nodes at the given positions */
DLLEXPORT Mesh createGrid(const RVector & x, const RVector & y, const RVector & z);

/*! Generate simple one dimensional mesh with nodes at position in RVector pos. */
DLLEXPORT Mesh createMesh1D(const RVector & x); 

/*! Generate simple 1D mesh with nCells cells of length 1, and nCells + 1 nodes.
 * In case of more than one property quasi-2d mesh with regions is generated.*/
DLLEXPORT Mesh createMesh1D(Index nCells, Index nProperties=1);

/*! Generate 1D block model of thicknesses and properties */
DLLEXPORT Mesh createMesh1DBlock(Index nLayers, Index nProperties=1);

/*! Generate simple two dimensional mesh with nodes at position in RVector x and y. */
DLLEXPORT Mesh createMesh2D(const RVector & x, const RVector & y, int markerType=0);

/*! Generate a simple 2D mesh by extruding a 1D polygone into 
 * RVector y using quads.
 * We assume a 2D mesh here consisting on nodes and edge boundaries.
 * Nodes with marker are extruded as edges with marker or set to front- and backMarker.
 * Edges with marker are extruded as cells with marker.
 * All back y-coordinates are adjusted if adjustBack is set. */
DLLEXPORT Mesh createMesh2D(const Mesh & mesh, const RVector & y,
                            int frontMarker=0, int backMarker=0,
                            int leftMarker=0, int rightMarker=0,
                            bool adjustBack=false);
                            
/*! Generate simple two dimensional mesh with nRows x nCols cells with each length = 1.0 */
DLLEXPORT Mesh createMesh2D(Index xDim, Index yDim, int markerType=0);

/*! Generate simple three dimensional mesh with nodes at position in RVector x and y. */
DLLEXPORT Mesh createMesh3D(const RVector & x, const RVector & y, const RVector & z, int markerType=0);

/*! Generate a simple three dimensional mesh by extruding a two dimensional mesh into RVector z using triangle prism or hexahedrons or both.
 * 3D cell marker are set from 2D cell marker.
 * The boundary marker for the side boundaries are set from edge marker in mesh.
 * Top and bottomLayer boundary marker are set from parameter topMarker and bottomMarker. */
DLLEXPORT Mesh createMesh3D(const Mesh & mesh, const RVector & z, int topMarker=0, int bottomMarker=0);

/*! Generate simple three dimensional mesh with nx x nx x nz cells with each length = 1.0 */
DLLEXPORT Mesh createMesh3D(Index xDim, Index yDim, Index zDim, int markerType=0);


/*! Add triangle boundary to the mesh. Return false on failors. */
DLLEXPORT bool addTriangleBoundary(Mesh & mesh,
                                   double xBoundary, double yBoundary, int cellMarker,
                                   bool save=false);

//
// /*! Shortcut */
// DLLEXPORT Mesh createMesh3D(const Mesh & mesh, const RVector & z);



} // namespace GIMLI

#endif // GIMLI_MESHGENERATORS__H
