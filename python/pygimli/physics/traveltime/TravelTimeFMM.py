# -*- coding: utf-8 -*-
"""
Created on Tue Jul 07 09:44:36 2015

@author: Marcus
"""

import pygimli as pg
import numpy as np
from pygimli.physics.traveltime.fastMarchingTest import fastMarch
import matplotlib.pyplot as plt
from pygimli.mplviewer import drawMesh  # , drawField, drawStreamLines


class TravelTimeFMM(pg.ModellingBase):
    """
    Class that implements the Fast Marching Method (FMM). It can be used
    instead of Dijkstra modelling. Although it is currently quite slow!

    """
    def __init__(self, mesh, data, verbose=False):
        """
        Init function.

        Parameters:
        -----------
        mesh : pygimli.Mesh
            2D mesh to be used in the forward calculations.
        data : pygimli.DataContainer
            The datacontainer with sensor positions etc.
        verbose : boolean
            More printouts or not...
        """

        pg.ModellingBase.__init__(self, mesh, data, verbose)
        self.timefields = dict()
        self._jac = dict()
        self.num_sensors = data.sensorCount()
#        num_shots = len(np.unique(data("s")))

    def response(self, slowness):
        """
        Response function. Returns the result of the forward calculation.
        Uses the shot- and sensor positions specified in the data container.
        """

        mesh = self.mesh()
        param_markers = np.unique(mesh.cellMarkers())
        param_count = len(param_markers)
        if len(slowness) == mesh.cellCount():
            self.mapModel(slowness)
        elif len(slowness) == param_count:
            # map the regions in the mesh to slowness
            slow_map = pg.stdMapF_F()
            min_reg_num = min(param_markers)
            for i, si in enumerate(slowness):
                slow_map.insert(float(i+min_reg_num), si)

            mesh.mapCellAttributes(slow_map)
        else:
            raise ValueError("Wrong no of parameters. Mesh size: {}, no "
                             "of regions: {}, and number of slowness values:"
                             "{}".format(self.mesh().cellCount(), param_count,
                                         len(slowness)))

        data = self.data()
        n_data = data.size()
        t_fmm = np.zeros(n_data)
        idx = 0
        for source_idx in [0]:  # np.unique(data("s")):
            # initialize source position and trvel time vector
            n_sensors = np.sum(data("s") == source_idx)
            # maybe not always same number of sensors
            source = data.sensorPosition(int(source_idx))
            times = pg.RVector(mesh.nodeCount(), 0.)

            # initialize sets and tags
#            upwind, downwind = set(), set()
            downwind = set()
            upTags = np.zeros(mesh.nodeCount())
            downTags = np.zeros(mesh.nodeCount())

            # define initial condition
            cell = mesh.findCell(source)

            for i, n in enumerate(cell.nodes()):
                times[n.id()] = cell.attribute() * n.pos().distance(source)
                upTags[n.id()] = 1
            for i, n in enumerate(cell.nodes()):
                tmpNodes = pg.commonNodes(n.cellSet())
                for nn in tmpNodes:
                    if not upTags[nn.id()] and not downTags[nn.id()]:
                        downwind.add(nn)
                        downTags[nn.id()] = 1

            # start fast marching
            while len(downwind) > 0:
                fastMarch(mesh, downwind, times, upTags, downTags)
            self.timefields[source_idx] = np.array(times)

            sensor_idx = data("g")[data("s") == source_idx]

            t_fmm[idx:idx+n_sensors] = np.array(
                [times[mesh.findNearestNode(data.sensorPosition(int(i)))]
                 for i in sensor_idx])
            idx += n_sensors

        return t_fmm

    def createJacobian(self, model):
        """
        Computes the jacobian matrix from the model.
        """
        pass

    def _intersect_lines(self, l1, l2):
        """
        Finds the parameters for which the two lines intersect.

        Assumes 2D lines!

        Parameters:
        -----------
        l1, l2 : pygimli Line
            Line objects from pygimli. Useful because they nicely wrap
            a line and has some utility functions.

        Returns:
        --------
        v : numpy array (length 2)
            The parameters (s and t) for l1 and l2, respectively. None if
            no intersection (i.e. parallell lines).
        """
#        print("l1: {}".format(l1))
#        print("l2: {}".format(l2))
#        first just check if parallell
        epsilon = 1.0e-4
        dir1 = l1.p1()-l1.p0()
        dir2 = l2.p1()-l2.p0()
#        print("dir1: {}, and length: {}".format(dir1, dir1.length()))
#        print("dir2: {}, and length: {}".format(dir2, dir2.length()))
        dir1 /= dir1.length()
        dir2 /= dir2.length()
#        print("dir1: {}, and length: {}".format(dir1, dir1.length()))
#        print("dir2: {}, and length: {}".format(dir2, dir2.length()))
        if abs(np.dot(dir1, dir2)) > 1.0 - epsilon:
            return np.array([1./epsilon, 1./epsilon])
#            raise Warning("parallell lines!")

        # Solve system: Av = w, were v, w are vectors. v = (s,t)
        ndim = 2
        A = np.ndarray((ndim, ndim))
        A[0, 0] = l1.p1().x() - l1.p0().x()
        A[1, 0] = l1.p1().y() - l1.p0().y()
        A[0, 1] = -(l2.p1().x() - l2.p0().x())
        A[1, 1] = -(l2.p1().y() - l2.p0().y())

        w = np.array([l2.p0().x() - l1.p0().x(), l2.p0().y() - l1.p0().y()])

        v = np.linalg.solve(A, w)
        if not np.allclose(np.dot(A, v), w):
            raise Warning("Problem with linear solver for intersection!")
        return v

    def _intersect_lines_by_points(self, p1, p2, p3, p4):
        """
        Finds the parameters for which the two lines intersect. The lines
        are defined by four points.

        Assumes 2D lines!

        Parameters:
        -----------
        p1, p2, p3, p4 : pygimli RVector3
            Position objects from pygimli. The lines are defined as:
                l1 : P1 to P2
                l2 : P3 to P4

        Returns:
        --------
        v : numpy array (length 2)
            The parameters (s and t) for l1 and l2, respectively. Will
            return "large" values if the lines are parallell.
        """

        # first just check if parallell
        epsilon = 1.0e-4
        dir1 = (p2 - p1).norm()
        dir2 = (p4 - p3).norm()

        if abs(np.dot(dir1, dir2)) > 1.0 - epsilon:
            return np.array([1./epsilon, 1./epsilon])
#            raise Warning("parallell lines!")

        # Solve system: Av = w, were v, w are vectors. v = (s,t)
        ndim = 2
        A = np.ndarray((ndim, ndim))
        A[0, 0] = p2.x() - p1.x()
        A[1, 0] = p2.y() - p1.y()
        A[0, 1] = p3.x() - p4.x()
        A[1, 1] = p3.y() - p4.y()

        w = np.array([p3.x() - p1.x(), p3.y() - p1.y()])

        v = np.linalg.solve(A, w)
        if not np.allclose(np.dot(A, v), w):
            raise Warning("Problem with linear solver for intersection!")
        return v[0], v[1]

    def _check_param(self, param, t_low=0, t_high=1.0):
        """
        Returns the "proper" t-value from the list. It should be
        positive along with the corresponding index value.
        """
        t_list = param[:, 0]
        par_pos = np.maximum(t_list, t_low)
        par_gt_eps = par_pos[par_pos > t_low+1e-5]
        print("t_list: {}\npar_pos: {}\npar_gt_eps: {}".format(
            t_list, par_pos, par_gt_eps))

        stay_on_edge = False
        try:
            t = np.min(par_gt_eps)
        except ValueError:
            stay_on_edge = True
            t = max(t_list)

        idx = int(param[t_list == t, 1][0])
        return t, idx, stay_on_edge

    def _check_param2(self, param, t_low=0, t_high=1.0):
        """
        Returns the "proper" t-value from the list. It should be
        positive along with the corresponding index value.
        """
        t_list = param[:, 0]
        par_pos = np.maximum(t_list, t_low)
        par_gt_eps = par_pos[par_pos > t_low+1e-5]
        print("t_list: {}\npar_pos: {}\npar_gt_eps: {}".format(
            t_list, par_pos, par_gt_eps))

        stay_on_edge = False
        try:
            t = np.min(par_gt_eps)
        except ValueError:
            stay_on_edge = True
            t = max(t_list)

        idx = int(param[t_list == t, 1][0])

        if np.all(t_list < 0):
            t = 1e-5

        return t, idx, stay_on_edge

    def _get_new_cell(self, boundary, current):
        """
        """
        if boundary.leftCell().id() == current.id():
            new_cell = boundary.rightCell()
        else:
            new_cell = boundary.leftCell()

        return new_cell

    def _get_new_cell2(self, boundary, current):
        """

        """

        if boundary.leftCell() is None or boundary.rightCell() is None:
            return current, False

        if boundary.leftCell().id() == current.id():
            new_cell = boundary.rightCell()
        else:
            new_cell = boundary.leftCell()

        print(current.attribute(), new_cell.attribute())
        fast_to_slow = new_cell.attribute() > current.attribute()

        return new_cell, fast_to_slow

    def _get_next_node(self, boundary, current_cell_id, ray_pos, ray_dir):
        """
        Gets the next node in the case that the ray should follow an
        interface. Will decide which cell is the one that is travelled
        through by choosing the one with highest velocity.

        Parameters:
        -----------
        boundary : pygimli Boundary
            The boundary we are coming from.
        current_cell_id : int
            The current cell index.
        ray_pos : pygimli RVector3
            The origin of the ray.
        ray_dir : pygimli RVector3
            Direction of the ray.
        Returns:
        --------
        node_id : int
            The global node index. (Using the mesh numbering)
        cell_id : int
            The global cell index of the cell we will use.
        """

        left = boundary.leftCell()
        right = boundary.rightCell()

        if left is not None:
            l_id = left.id()  # boundary.leftCell().attribute()
            left_slowness = self.mesh().cell(l_id).attribute()
        else:
            l_id = None
            left_slowness = 10000.

        if right is not None:
            r_id = right.id()  # boundary.rightCell().attribute()
            right_slowness = self.mesh().cell(r_id).attribute()
        else:
            r_id = None
            right_slowness = 10000.

        print("left slow: {}, right slow: {}".format(
            left_slowness, right_slowness))
        # Pick the fastest cell
        if left_slowness < right_slowness:
            cell_id = l_id  # boundary.leftCell().id()
        else:
            cell_id = r_id  # boundary.rightCell().id()

        # pick the right direction to go
        line_segment = ray_pos - boundary.node(0).pos()
        if np.dot(line_segment, ray_dir) < 0.:
            node_id = boundary.node(0).id()
        else:
            node_id = boundary.node(1).id()

        return node_id, cell_id

    def _trace_back(self, sensor_idx, source_idx, epsilon=1e-5):
        """
        Traces a ray backwards through the mesh from a particular sensor
        towards the seismic source.
        """
        msh = self.mesh()
        self.poslist = []
        self._jac[source_idx] = np.zeros((msh.cellCount()))

        pos_offset = pg.RVector3(0., epsilon, 0.)

        sensor_pos = self.data().sensorPosition(sensor_idx)
        source_pos = self.data().sensorPosition(source_idx)
        source_node = msh.findNearestNode(source_pos)

        current_cell = msh.findCell(sensor_pos - pos_offset)
        new_cell = current_cell
        ray_origin = sensor_pos - pos_offset
        was_on_edge = False
        while ray_origin.dist(source_pos) > epsilon:
            self.poslist.append(ray_origin)
            if new_cell is None:
                print("Ended up outside mesh!")
                print("Last valid cell: {}".format(current_cell))
                break
#                other_boundary = pg.findBoundary(
#                    current_cell.node((node_idx+2)%nnodes),
#                    current_cell.node((node_idx+1)%nnodes))
#                new_cell = self._get_new_cell(other_boundary, current_cell)
#                gradient = current_cell.node((node_idx+1)%nnodes).pos() -
#                current_cell.node(node_idx).pos()
            else:
                old_cell_id = current_cell.id()  # going to slower cell
#                if new_cell.attribute() > current_cell.attribute():
#                    gradient = current_cell.grad(current_cell.center(),
#                                             self.timefields[source_idx])
#                else:
#                    gradient = new_cell.grad(current_cell.center(),
#                                             self.timefields[source_idx])
                current_cell = new_cell

                if not was_on_edge:
                    gradient = current_cell.grad(
                        current_cell.center(), self.timefields[source_idx])
                else:
                    was_on_edge = False
            print("Current cell: {}".format(current_cell.id()))
#            gradient = current_cell.grad(current_cell.center(),
#                                         self.timefields[source_idx])
#            gradient_norm = -gradient / gradient.length()
            gradient_norm = -gradient.norm()
            nnodes = current_cell.nodeCount()
            params = np.zeros((nnodes, 2))
            gradient_line = pg.Line(ray_origin, ray_origin + gradient_norm)
            for i in range(nnodes):
                if current_cell.node(i).id() == source_node:
                    print("cell closest to source")
                    params[i, :] = [ray_origin.dist(source_pos), i]
                    break
                edge = pg.Line(current_cell.node(i).pos(),
                               current_cell.node((i+1) % nnodes).pos())
#                print("Grad: {}".format(gradient_line))
#                print("Edge: {}".format(edge))

                s_t = self._intersect_lines(gradient_line, edge)

#                print("s_t: {}".format(s_t))
                params[i, :] = [s_t[0], i]

            t, node_idx, stay_on_edge = self._check_param(params)
            print("Stay on edge: {}".format(stay_on_edge))

            boundary = pg.findBoundary(
                current_cell.node(node_idx),
                current_cell.node((node_idx+1) % nnodes))
            if stay_on_edge:
                # break
                next_node_id, next_cell_id = self._get_next_node(
                    boundary, current_cell.id(), ray_origin, gradient_norm)
                t = ray_origin.dist(msh.node(next_node_id).pos())
                print("Current: {}, next: {}, t: {}".format(
                    current_cell.id(), next_cell_id, t))
                print("")
                self._jac[source_idx][next_cell_id] += t
                temp = msh.node(next_node_id).pos() - ray_origin
                ray_origin = msh.node(next_node_id).pos() + \
                    1e-5 * temp.norm() - pg.RVector3(0.0, 1e-6, 0.0)
                # new_cell = mesh.cell(next_cell_id)
                new_cell = msh.findCell(ray_origin)
                was_on_edge = True
#                print("next_cell_id: {}, findCell: {}".format(
#                    next_cell_id, new_cell.id()))
            else:
                # print("params: {}, t: {}, i: {}".format(params, t, node_idx))
                # Save distance travelled in the cell (t) and update origin
                self._jac[source_idx][current_cell.id()] = t
                ray_origin = gradient_line.lineAt(t)
#            print("ray origin: {}".format(ray_origin))
                new_cell = self._get_new_cell(boundary, current_cell)
            if new_cell.id() == old_cell_id:
                # If we keep jumping back and forth between two cells.
                print("Jumping back and forth...")
                break

        return self._jac

if __name__ == '__main__':
    """
    Currently, this script assumes that the data was generated with Dijkstra
    modelling and computes the differences between the FMM modelling.
    """

    mesh = pg.Mesh('vagnh_fwd_mesh.bms')
    mesh.createNeighbourInfos()
    data = pg.DataContainer('vagnh_NONOISE.sgt', 's g')
    vel = [1400., 1700., 5000.]
    slo = np.array([0, 0, 1./1400., 1./1700., 1./5000.])
    cslo = slo.take(mesh.cellMarkers())
    print(mesh)
    print(data)

    fwd = TravelTimeFMM(mesh, data, True)
    pg.tic()
    t_fmm = fwd.response(cslo)
#    t_fmm = fwd.response(1.0/np.array(vel))
    pg.toc()
#    delta_t = np.array(data("t")) - t_fmm
#    f, ax = plt.subplots()
#    x = pg.x(data.sensorPositions())
#    ax.plot(abs(delta_t), 'r-.', label='abs. diff')
#    ax.plot(delta_t, 'b-', label='diff')
#    ax.legend(loc='best')
#    f.show()
#    raise SystemExit()

    l = fwd._trace_back(50, 0)

    fig, a = plt.subplots()
    drawMesh(a, mesh)
    pg.show(mesh, axes=a, data=l[0])

    cells = fwd.mesh().cells()
    active_cells = [cells[i] for i in range(mesh.cellCount()) if l[0][i]]
#    active_cells.append(cells[2044])
    for c in active_cells:
        pos = c.center()
        gradient = 2000*c.grad(pos, fwd.timefields[0])
        dx, dy = gradient.x(), gradient.y()
        a.text(pos.x(), pos.y(), str(c.id()))
        a.arrow(pos.x(), pos.y(), dx, dy)

    ray = fwd.poslist
    a.plot(pg.x(ray), pg.y(ray), 'm-*', )
    plt.show()

    # look at if next gradient contradicts the previous
    # if so, then follow the interface instead (line segment to next node)
    # this will stop when the gradients are more aligned.

#    drawMesh(a, mesh)
#    drawField(a, mesh, fwd.timefields[0], True, 'Spectral')
#    drawStreamLines(a, mesh, fwd.timefields[0], nx=50, ny=50)

    # some stats:
    delta_t = np.array(data("t")) - t_fmm
    diff_rms = np.sqrt(np.sum(delta_t**2)/len(delta_t))
    print("RMS of difference: {}".format(diff_rms))
    print("Mean of difference: {}".format(np.mean(delta_t)))
    print("Standard dev of difference: {}".format(np.std(delta_t)))
    print("Median of difference: {}".format(np.median(delta_t)))
