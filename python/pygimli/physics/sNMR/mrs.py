#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    Magnetic resonance sounding module
"""

# general modules to import according to standards
import time
import numpy as np
import matplotlib.pyplot as plt
# pygimli main package and specific functions
import pygimli as pg
from pygimli.utils import iterateBounds
from pygimli.utils.base import gmat2numpy
# local functions in package
from . modelling import MRS1dBlockQTModelling
from . plotting import showErrorBars, showWC, showT2, drawModel1D


class MRS():
    """magnetic resonance sounding (MRS) manager class

    Attributes
    ----------
    t, q : ndarray - time and pulse moment vectors

    data, error : 2d ndarray - data and error cubes

    K, z : ndarray - (complex) kernel and its vertical discretization

    model, modelL, modelU : vectors - model vector and lower/upper bound to it

    Methods
    -------
    loadMRSI - load MRSI (MRSmatlab format) data

    showCube - show any data/error/misfit as data cube (over q and t)

    showDataAndError - show data and error cubes

    showKernel - show Kernel matrix

    createFOP - create forward operator

    createInv - create pygimli Inversion instance

    run - run block-mono (alternatively smooth-mono) inversion (with bootstrap)

    calcMCM - compute model covariance matrix and thus uncertainties

    splitModel - return thickness, water content and T2* time from vector

    showResult/showResultAndFit - show inversion result (with fit)

    runEA - run evolutionary algorithm (GA, PSO etc.) using inspyred

    plotPopulation - plot final population of an EA run
    """

    def __init__(self, name=None, verbose=True, **kwargs):
        """MRS init with optional data load from mrsi file

        Parameters
        ----------
        name : string
            Filename with load data and kernel (*.mrsi) or just data (*.mrsd)
        verbose : bool
            be verbose
        kwargs - see :func:`MRS.loadMRSI`.
        """
        self.verbose = verbose
        self.t, self.q, self.z = None, None, None
        self.data, self.error = None, None
        self.K, self.f, self.INV = None, None, None
        self.nlay = 0
        self.model, self.modelL, self.modelU = None, None, None
        self.lowerBound = [1.0, 0.0, 0.02]  # d, theta, T2*
        self.upperBound = [30., 0.45, 1.00]  # d, theta, T2*
        self.startval = [10., 0.30, 0.20]  # d, theta, T2*
        self.logpar = False
        self.basename = 'new'
        if name is not None:  # load data and kernel
            # check for mrsi/d/k
            if name[-5:-1].lower() == '.mrs':  # mrsi or mrsd
                self.loadMRSI(name, **kwargs)
                self.basename = name.rstrip('.mrsi')
#            elif name[-5:].lower() == '.mrsd':
#                self.loadMRSD(name, **kwargs)
            else:
                self.loadDir(name)

    def __repr__(self):  # for print function
        out = ""
        if len(self.t) > 0 and len(self.q) > 0:
            out = "<MRSdata: %d qs, %d times" % \
                (len(self.q), len(self.t))
        if hasattr(self.z, '__iter__') and len(self.z) > 0:
            out += ", %d layers" % len(self.z)
        return out + ">"

    def loadMRSI(self, filename, usereal=False, mint=0., maxt=2.0, **kwargs):
        """load data, error and kernel from mrsi or mrsd file

        Parameters
        ----------
        usereal : bool [False]
            use real parts (after data rotation) instead of amplitudes
        mint/maxt : float [0.0/2.0]

        """
        from scipy.io import loadmat  # loading Matlab mat files

        if filename[-5:].lower() == '.mrsd':
            idata = None
            pl = loadmat(filename, struct_as_record=False,
                         squeeze_me=True)['proclog']
            self.q = np.array([q.q for q in pl.Q])
            self.t = pl.Q[0].rx.sig[0].t + pl.Q[0].timing.tau_dead1
            nq = len(pl.Q)
            nt = len(self.t)
            self.dcube = np.zeros((nq, nt))
            self.ecube = np.zeros((nq, nt))
#            self.ecube = np.ones((nq, nt))*20e-9
            for i in range(nq):
                self.dcube[i, :] = pl.Q[i].rx.sig[1].V
                self.ecube[i, :] = np.real(pl.Q[i].rx.sig[1].E)
        else:
            idata = loadmat(filename, struct_as_record=False,
                            squeeze_me=True)['idata']
            self.t = idata.data.t + idata.data.effDead
            self.q = idata.data.q
            self.K = idata.kernel.K
            self.z = np.hstack((0., idata.kernel.z))
            self.dcube = idata.data.dcube
            self.ecube = idata.data.ecube

        good = (self.t <= maxt) & (self.t >= mint)
        self.t = self.t[good]
        self.dcube = self.dcube[:, good]
        self.ecube = self.ecube[:, good]

        ndcubet = len(self.dcube[0])
        if len(self.dcube) == len(self.q) and ndcubet == len(self.t):
            if usereal:
                self.data = np.real(self.dcube.flat)
            else:
                self.data = np.abs(self.dcube.flat)

        necubet = len(self.dcube[0])
        if self.verbose:
            print("loaded file: " + filename)
        if self.ecube[0][0] == 0:
            if self.verbose:
                defaultNoise = kwargs.pop("defaultNoise", 100e-9)
                print("no errors in file, assuming", defaultNoise*1e9, "nV")
            self.ecube = np.ones((len(self.q), len(self.t))) * defaultNoise
            if idata is not None:
                self.ecube /= np.sqrt(idata.data.gateL)
        if len(self.ecube) == len(self.q) and necubet == len(self.t):
            self.error = self.ecube.ravel()

        if min(self.error) < 0.:
            if self.verbose:
                print(
                    "Warning: negative errors present! Taking absolute value")
            self.error = np.absolute(self.error)
        if min(self.error) == 0.:
            if self.verbose:
                print("Warning: zero error, assuming", defaultNoise)
            self.error[self.error == 0.] = defaultNoise
        # clip data if desired (using vmin and vmax keywords)
        if "vmax" in kwargs:
            vmax = kwargs['vmax']
            self.error[self.data > vmax] = max(self.error)*3
            self.data[self.data > vmax] = vmax
        if "vmin" in kwargs:
            vmin = kwargs['vmin']
            self.error[self.data < vmin] = max(self.error)*3
            self.data[self.data < vmin] = vmin
        # load model from matlab file (result of MRSQTInversion)
        if filename[-5:].lower() == '.mrsi' and hasattr(idata, 'inv1Dqt'):
            if hasattr(idata.inv1Dqt, 'blockMono'):
                sol = idata.inv1Dqt.blockMono.solution[0]
                self.model = np.hstack((sol.thk, sol.w, sol.T2))
                self.nlay = len(sol.w)
        if self.verbose:
            print(self)

    def loadMRSD(self, filename, usereal=False, mint=0., maxt=2.0, **kwargs):
        """ load mrsd (MRS data) file: not really used as in MRSD """
        from scipy.io import loadmat  # loading Matlab mat files

        pl = loadmat(filename, struct_as_record=False,
                     squeeze_me=True)['proclog']
        self.q = np.array([q.q for q in pl.Q])
        self.t = pl.Q[0].rx.sig[0].t + pl.Q[0].timing.tau_dead1
        nq = len(pl.Q)
        nt = len(self.t)
        self.dcube = np.zeros((nq, nt))
        for i in range(nq):
            self.dcube[i, :] = np.abs(pl.Q[i].rx.sig[1].V)
        self.ecube = np.ones((nq, nt))*20e-9

    def loadDataCube(self, filename='datacube.dat'):
        """ load data cube from single ascii file (old stuff)"""
        A = np.loadtxt(filename).T
        self.q = A[1:, 0]
        self.t = A[0, 1:]
        self.data = A[1:, 1:].ravel()

    def loadErrorCube(self, filename='errorcube.dat'):
        """ load error cube from a single ascii file (old stuff) """
        A = np.loadtxt(filename).T
        if len(A) == len(self.q) and len(A[0]) == len(self.t):
            self.error = A.ravel()
        elif len(A) == len(self.q) + 1 and len(A[0]) == len(self.t) + 1:
            self.error = A[1:, 1:].ravel()
        else:
            self.error = np.ones(len(self.q) * len(self.t)) * 100e-9

    def loadKernel(self, name=''):
        """load kernel matrix from mrsk or two bmat files"""
        from scipy.io import loadmat  # loading Matlab mat files

        if name[-5:].lower() == '.mrsk':
            kdata = loadmat(name, struct_as_record=False,
                            squeeze_me=True)['kdata']
            self.K = kdata.K
            self.z = np.hstack((0., kdata.model.z))
        else:  # try load real/imag parts (backward compat.)
            KR = pg.RMatrix(name + 'KR.bmat')
            KI = pg.RMatrix(name + 'KI.bmat')
            self.K = np.zeros((KR.rows(), KR.cols()), dtype='complex')
            for i in range(KR.rows()):
                self.K[i] = np.array(KR[i]) + np.array(KI[i]) * 1j

    def loadZVector(self, filename='zkernel.vec'):
        """load the kernel discretisation"""
        self.z = pg.RVector(filename)

    def loadDir(self, dirname):
        """load several files from dir (old Borkum stage)"""
        if not dirname[-1] == '/':
            dirname += '/'
        self.loadDataCube(dirname + 'datacube.dat')
        self.loadErrorCube(dirname + 'errorcube.dat')
        self.loadKernel(dirname)
        self.loadZVector(dirname + 'zkernel.vec')
        self.dirname = dirname  # to save results etc.

    def showCube(self, ax=None, vec=None, islog=None, clim=None, clab=None):
        """plot data (or response, error, misfit) cube nicely"""
        if vec is None:
            vec = np.array(self.data).flat
            print(len(vec))
        mul = 1.0
        if max(vec) < 1e-3:  # Volts
            mul = 1e9
        if ax is None:
            fig, ax = plt.subplots(1, 1)
        if islog is None:
            islog = (min(vec) > 0.)
        negative = (min(vec) < 0)
        if islog:
            vec = np.log10(np.abs(vec))
        if clim is None:
            if negative:
                cmax = max(max(vec), -min(vec))
                clim = (-cmax, cmax)
            else:
                cmax = max(vec)
                if islog:
                    cmin = cmax - 1.5
                else:
                    cmin = 0.
                clim = (cmin, cmax)

        xt = range(0, len(self.t), 10)
        xtl = [str(ti) for ti in np.round(self.t[xt] * 1000.)]
        qt = range(0, len(self.q), 5)
        qtl = [str(qi) for qi in np.round(np.asarray(self.q)[qt] * 10.) / 10.]
        mat = np.array(vec).reshape((len(self.q), len(self.t)))*mul
        im = ax.imshow(mat, interpolation='nearest', aspect='auto')
        im.set_clim(clim)
        ax.set_xticks(xt)
        ax.set_xticklabels(xtl)
        ax.set_yticks(qt)
        ax.set_yticklabels(qtl)
        ax.set_xlabel('$t$ [ms]')
        ax.set_ylabel('$q$ [As]')
        cb = plt.colorbar(im, ax=ax, orientation='horizontal')
        if clab is not None:
            cb.ax.set_title(clab)

        return clim

    def showDataAndError(self, figsize=(10, 8), show=False):
        """show data cube and error cube"""
        fig, ax = plt.subplots(1, 2, figsize=figsize)
        self.showCube(ax[0], self.data * 1e9, islog=False)
        self.showCube(ax[1], self.error * 1e9, islog=True)
        if show:
            plt.show()
        return fig, ax

    def showKernel(self, ax=None):
        """show the kernel as matrix"""
        if ax is None:
            fig, ax = plt.subplots()
        ax.imshow(self.K.T, interpolation='nearest', aspect='auto')
        yt = ax.get_yticks()
        maxzi = self.K.shape[1]
        yt = yt[(yt >= 0) & (yt < maxzi)]
        if yt[-1] < maxzi-2:
            yt = np.hstack((yt, maxzi))
        ytl = [str(self.z[int(yti)]) for yti in yt]
        zl = self.z[[int(yti) for yti in yt]]
        ytl = [str(zi) for zi in np.round(zl, 1)]
        ax.set_yticks(yt)
        ax.set_yticklabels(ytl)
        xt = ax.get_xticks()
        maxqi = self.K.shape[0]
        xt = xt[(xt >= 0) & (xt < maxqi)]
        xtl = [np.round(self.q[iq], 2) for iq in xt]
        ax.set_xticks(xt)
        ax.set_xticklabels(xtl)

        return fig, ax

    def createFOP(self, nlay=3, verbose=True, **kwargs):
        """create forward operator instance"""
        self.nlay = nlay
        self.f = MRS1dBlockQTModelling(nlay, self.K, self.z, self.t)
        for i in range(3):
            self.f.region(i).setParameters(self.startval[i],
                                           self.lowerBound[i],
                                           self.upperBound[i], "log")

    def createInv(self, nlay=3, lam=100., verbose=True, **kwargs):
        """ create inversion instance (and fop if necessary with nlay) """
        if self.f is None or self.nlay != nlay:
            self.createFOP(nlay)
        self.INV = pg.RInversion(self.data, self.f, verbose)
        self.INV.setLambda(lam)
        self.INV.setMarquardtScheme(kwargs.pop('lambdaFactor', 0.8))
        self.INV.stopAtChi1(False)  # now in MarquardtScheme
        self.INV.setDeltaPhiAbortPercent(0.5)
        self.INV.setAbsoluteError(self.error)
        self.INV.setRobustData(kwargs.pop('robust', False))
        return self.INV

    def run(self, nlay=3, lam=100., startvec=None,
            verbose=True, uncertainty=False, **kwargs):
        """ easiest variant doing all (create fop and inv) in one call """
        if self.INV is None or self.nlay != nlay:
            self.INV = self.createInv(nlay, lam, verbose, **kwargs)
        self.INV.setVerbose(verbose)
        if startvec is not None:
            self.INV.setModel(startvec)
        if verbose:
            print("Doing inversion...")
        self.model = np.array(self.INV.run())
        if uncertainty:
            if verbose:
                print("Computing uncertainty...")
            self.modelL, self.modelU = iterateBounds(
                self.INV, dchi2=self.INV.chi2() / 2, change=1.2)
            if verbose:
                print("ready")

    def splitModel(self, model=None):
        """split model vector into d, theta and T2*"""
        if model is None:
            model = self.model
        nl = self.nlay
        thk = model[:nl - 1]
        wc = model[nl - 1:2 * nl - 1]
        t2 = model[2 * nl - 1:3 * nl - 1]
        return thk, wc, t2

    def result(self):
        """return block model results"""
        return self.splitModel()

    def showResult(self, figsize=(10, 8), save='', fig=None, ax=None):
        """show theta(z) and T2*(z) (+uncertainties if there)"""
        if ax is None:
            fig, ax = plt.subplots(1, 2, sharey=True, figsize=figsize)
        thk, wc, t2 = self.splitModel()
        showWC(ax[0], thk, wc)
        showT2(ax[1], thk, t2)
        if self.modelL is not None and self.modelU is not None:
            thkL, wcL, t2L = self.splitModel(self.modelL)
            thkU, wcU, t2U = self.splitModel(self.modelU)
            showErrorBars(ax[0], thk, wc, thkL, thkU, wcL, wcU)
            showErrorBars(ax[1], thk, t2*1e3, thkL, thkU, t2L*1e3, t2U*1e3)

        if fig is not None:
            if save:
                fig.savefig(save, bbox_inches='tight')
            return fig, ax

    def showResultAndFit(self, figsize=(12, 10), save='', plotmisfit=False,
                         maxdep=0, clim=None):
        """show theta(z), T2*(z), data and model response"""
        fig, ax = plt.subplots(2, 2 + plotmisfit, figsize=figsize)
        thk, wc, t2 = self.splitModel()
        showWC(ax[0, 0], thk, wc, maxdep=maxdep)
        showT2(ax[0, 1], thk, t2, maxdep=maxdep)
        ax[0, 0].set_title(r'MRS water content $\theta$')
        ax[0, 1].set_title(r'MRS decay time $T_2^*$')
        ax[0, 0].set_ylabel('$z$ [m]')
        ax[0, 1].set_ylabel('$z$ [m]')
        if self.modelL is not None and self.modelU is not None:
            thkL, wcL, t2L = self.splitModel(self.modelL)
            thkU, wcU, t2U = self.splitModel(self.modelU)
            showErrorBars(ax[0, 0], thk, wc, thkL, thkU, wcL, wcU)
            showErrorBars(ax[0, 1], thk, t2*1e3, thkL, thkU, t2L*1e3, t2U*1e3)

        if maxdep > 0.:
            ax[0, 0].set_ylim([maxdep, 0.])
            ax[0, 1].set_ylim([maxdep, 0.])
        clim = self.showCube(ax[1, 0], self.data * 1e9, islog=False, clim=clim)
        ax[1, 0].set_title('measured data [nV]')  # log10
        self.showCube(
            ax[1, 1], self.INV.response() * 1e9, clim=clim, islog=False)
        ax[1, 1].set_title('simulated data [nV]')  # log10
        if plotmisfit:
            self.showCube(ax[0, 2], (self.data - self.INV.response()) * 1e9,
                          islog=False)
            ax[0, 2].set_title('misfit [nV]')  # log10
            ewmisfit = (self.data - self.INV.response()) / self.error
            self.showCube(ax[1, 2], ewmisfit, islog=False)
            ax[1, 2].set_title('error-weighted misfit')

        if save:
            fig.savefig(save, bbox_inches='tight')
        return fig, ax

    def saveResult(self, filename):
        """save inversion result to column text file"""
        thk, wc, t2 = self.splitModel()
        z = np.hstack((0., np.cumsum(thk)))
        ALL = np.column_stack((z, wc, t2))
        if self.modelL is not None and self.modelU is not None:
            thkL, wcL, t2L = self.splitModel(self.modelL)
            thkU, wcU, t2U = self.splitModel(self.modelU)
            zL = z.copy()
            zL[1:] += (thkL - thk)
            zU = z.copy()
            zU[1:] += (thkU - thk)
            ALL = np.column_stack((z, wc, t2, zL, zU, wcL, wcU, t2L, t2U))

        np.savetxt(filename, ALL, fmt='%.3f')

    def loadResult(self, filename):
        """load inversion result from column file"""
        A = np.loadtxt(filename)
        z, wc, t2 = A[:, 0], A[:, 1], A[:, 2]
        thk = np.diff(z)
        self.nlay = len(wc)
        self.model = np.hstack((thk, wc, t2))
        if len(A[0]) > 8:
            zL, wcL, t2L = A[:, 3], A[:, 5], A[:, 7]
            zU, wcU, t2U = A[:, 4], A[:, 6], A[:, 8]
            thkL = thk + zL[1:] - z[1:]
            thkU = thk + zU[1:] - z[1:]
            t2L[t2L < 0.01] = 0.01
            self.modelL = np.hstack((thkL, wcL, t2L))
            t2U[t2U > 1.0] = 1.0
            self.modelU = np.hstack((thkU, wcU, t2U))

    def calcMCM(self):
        """compute model covariance matrix"""
        J = gmat2numpy(self.f.jacobian())  # (linear) jacobian matrix
        D = np.diag(1 / self.error)
        DJ = D.dot(J)
        JTJ = DJ.T.dot(DJ)
        MCM = np.linalg.inv(JTJ)   # model covariance matrix
        var = np.sqrt(np.diag(MCM))  # standard deviations from main diagonal
        di = (1. / var)  # variances as column vector
        # scaled model covariance (=correlation) matrix
        MCMs = di.reshape(len(di), 1) * MCM * di
        return var, MCMs

    def calcMCMbounds(self):
        """comute model bounds using covariance matrix diagonals"""
        self.mcm = self.calcMCM()[0]
        self.modelL = self.model - self.mcm
        self.modelU = self.model + self.mcm

    def genMod(self, individual):
        """ generate (GA) model from random vector (0-1) using model bounds """
        model = np.asarray(individual) * (self.lUB - self.lLB) + self.lLB
        if self.logpar:
            return pg.exp(model)
        else:
            return model

    def runEA(self, nlay=None, eatype='GA', pop_size=100, num_gen=100,
              runs=1, mp_num_cpus=8, **kwargs):
        """ Run evolutionary algorithm using inspyred library

            Parameters
            ----------
            nlay : int - number of layers\n
            pop_size : int - population size\n
            num_gen : int - number of generations\n
            runs : int - number of independent runs (with random population)\n
            eatype : string - algorithm, choose among:\n
            'GA' - Genetic Algorithm [default]\n
            'SA' - Simulated Annealing\n
            'DEA' - Discrete Evolutionary Algorithm\n
            'PSO' - Particle Swarm Optimization\n
            'ACS' - Ant Colony Strategy\n
            'ES' - Evolutionary Strategy
        """
        import inspyred
        import random

        def mygenerate(random, args):
            """generate a random vector of model size"""
            return [random.random() for i in range(nlay * 3 - 1)]

        def my_observer(population, num_generations, num_evaluations, args):
            """ print fitness over generation number """
            best = min(population)
            print('{0:6} -- {1}'.format(num_generations, best.fitness))

        @inspyred.ec.evaluators.evaluator
        def datafit(individual, args):
            """ error-weighted data misfit as basis for evaluating fitness """
            misfit = (self.data - self.f.response(self.genMod(individual))) / \
                self.error
            return np.mean(misfit**2)

        # prepare forward operator
        if self.f is None or (nlay is not None and nlay is not self.nlay):
            self.createFOP(nlay)

        lowerBound = pg.cat(pg.cat(pg.RVector(self.nlay - 1,
                                              self.lowerBound[0]),
                                   pg.RVector(self.nlay, self.lowerBound[1])),
                            pg.RVector(self.nlay, self.lowerBound[2]))
        upperBound = pg.cat(pg.cat(pg.RVector(self.nlay - 1,
                                              self.upperBound[0]),
                                   pg.RVector(self.nlay, self.upperBound[1])),
                            pg.RVector(self.nlay, self.upperBound[2]))
        if self.logpar:
            self.lLB, self.lUB = pg.log(lowerBound), pg.log(
                upperBound)  # ready mapping functions
        else:
            self.lLB, self.lUB = lowerBound, upperBound

#        self.f = MRS1dBlockQTModelling(nlay, self.K, self.z, self.t)
        # setup random generator
        rand = random.Random()
        # choose among different evolution algorithms
        if eatype == 'GA':
            ea = inspyred.ec.GA(rand)
            ea.variator = [
                inspyred.ec.variators.blend_crossover,
                inspyred.ec.variators.gaussian_mutation]
            ea.selector = inspyred.ec.selectors.tournament_selection
            ea.replacer = inspyred.ec.replacers.generational_replacement
        if eatype == 'SA':
            ea = inspyred.ec.SA(rand)
        if eatype == 'DEA':
            ea = inspyred.ec.DEA(rand)
        if eatype == 'PSO':
            ea = inspyred.swarm.PSO(rand)
        if eatype == 'ACS':
            ea = inspyred.swarm.ACS(rand, [])
        if eatype == 'ES':
            ea = inspyred.ec.ES(rand)
            ea.terminator = [inspyred.ec.terminators.evaluation_termination,
                             inspyred.ec.terminators.diversity_termination]
        else:
            ea.terminator = inspyred.ec.terminators.evaluation_termination

#        ea.observer = my_observer
        ea.observer = [
            inspyred.ec.observers.stats_observer,
            inspyred.ec.observers.file_observer]
        tstr = '{0}'.format(time.strftime('%y%m%d-%H%M%S'))
        self.EAstatfile = self.basename + '-' + eatype + 'stat' + tstr + '.csv'
        with open(self.EAstatfile, 'w') as fid:
            self.pop = []
            for i in range(runs):
                rand.seed(int(time.time()))
                self.pop.extend(ea.evolve(
                    evaluator=datafit, generator=mygenerate, maximize=False,
                    pop_size=pop_size, max_evaluations=pop_size*num_gen,
                    bounder=inspyred.ec.Bounder(0., 1.), num_elites=1,
                    statistics_file=fid, **kwargs))
#                self.pop.extend(ea.evolve(
#                    generator=mygenerate, maximize=False,
#                    evaluator=inspyred.ec.evaluators.parallel_evaluation_mp,
#                    mp_evaluator=datafit, mp_num_cpus=mp_num_cpus,
#                    pop_size=pop_size, max_evaluations=pop_size*num_gen,
#                    bounder=inspyred.ec.Bounder(0., 1.), num_elites=1,
#                    statistics_file=fid, **kwargs))
        self.pop.sort(reverse=True)
        self.fits = [ind.fitness for ind in self.pop]
        print('minimum fitness of ' + str(min(self.fits)))

    def plotPopulation(self, maxfitness=None, fitratio=1.05, savefile=True):
        """ Plot fittest individuals (fitness<maxfitness) as 1d models

        Parameters
        ----------
        maxfitness : float - maximum fitness value (absolute) OR

        fitratio : float [1.05] - maximum ratio to minimum fitness
        """
        if maxfitness is None:
            maxfitness = min(self.fits) * fitratio
        fig, ax = plt.subplots(1, 2, sharey=True)
        maxz = 0
        for ind in self.pop:
            if ind.fitness < maxfitness:
                model = np.asarray(self.genMod(ind.candidate))
                thk = model[:self.nlay - 1]
                wc = model[self.nlay - 1:self.nlay * 2 - 1]
                t2 = model[self.nlay * 2 - 1:]
                drawModel1D(ax[0], thk, wc * 100, color='grey')
                drawModel1D(ax[1], thk, t2 * 1000, color='grey')
                maxz = max(maxz, sum(thk))

        model = np.asarray(self.genMod(self.pop[0].candidate))
        thk = model[:self.nlay - 1]
        wc = model[self.nlay - 1:self.nlay * 2 - 1]
        t2 = model[self.nlay * 2 - 1:]
        drawModel1D(ax[0], thk, wc * 100, color='black', linewidth=3)
        drawModel1D(ax[1], thk, t2 * 1000, color='black', linewidth=3,
                    plotfunction='semilogx')

        ax[0].set_xlim(self.lowerBound[1] * 100, self.upperBound[1] * 100)
        ax[0].set_ylim((maxz * 1.2, 0))
        ax[1].set_xlim(self.lowerBound[2] * 1000, self.upperBound[2] * 1000)
        ax[1].set_ylim((maxz * 1.2, 0))
        xt = [10, 20, 50, 100, 200, 500, 1000]
        ax[1].set_xticks(xt)
        ax[1].set_xticklabels([str(xti) for xti in xt])
        if savefile:
            fig.savefig(self.EAstatfile.replace('.csv', '.pdf'),
                        bbox_inches='tight')

        plt.show()

    def plotEAstatistics(self, fname=None):
        """plot Evolutionary Algorithm statistics (best, worst, ...) over time
        """
        if fname is None:
            fname = self.EAstatfile
        gen, psize, worst, best, med, avg, std = np.genfromtxt(
            fname, unpack=True, usecols=range(7), delimiter=',')
        stderr = std / np.sqrt(psize)

        data = [avg, med, best, worst]
        colors = ['black', 'blue', 'green', 'red']
        labels = ['average', 'median', 'best', 'worst']

        fig, ax = plt.subplots()
        ax.errorbar(gen, avg, stderr, color=colors[0], label=labels[0])
        ax.set_yscale('log')
        for d, col, lab in zip(data[1:], colors[1:], labels[1:]):
            ax.plot(gen, d, color=col, label=lab)
        ax.fill_between(gen, data[2], data[3], color='#e6f2e6')
        ax.grid(True)
        ymin = min([min(d) for d in data])
        ymax = max([max(d) for d in data])
        yrange = ymax - ymin
        ax.set_ylim((ymin - 0.1*yrange, ymax + 0.1*yrange))
        ax.legend(loc='upper left')  # , prop=prop)
        ax.set_xlabel('Generation')
        ax.set_ylabel('Fitness')

if __name__ == "__main__":
    datafile = 'example.mrsi'
    nlay = 4
    mrs = MRS(datafile)
    mrs.run(nlay, uncertainty=True)
    thk, wc, t2 = mrs.result()
    mrs.saveResult(mrs.basename+'.result')
    mrs.showResultAndFit(save=mrs.basename+'.pdf')
    plt.show()
