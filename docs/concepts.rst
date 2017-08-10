.. _concepts:

========
Concepts
========

Fitting parameters
==================

ESPEI has two steps, which can be completed independently, if desired.
The first is to use single-phase data, which includes heat capacities, entropies, enthalpies, and mixing data, to select (generate) parameters and fit them numerically.
The second is to treat these calculated parameters (or parameters of your choosing from a supplied database) as degrees of freedom and optimize them to multi-phase equilibria with Markov chain Monte Carlo (MCMC).

Single-phase
------------

The most important take away of ESPEI's single-phase fitting is this: **if you don't have the data to describe a parameter, you will not generate that parameter**.
The rest of this section is dedicated to describing what this means.

Multi-phase
-----------

Once you have determined your degrees of freedom, either by generating parameters with the single phase fitting or by renaming some parameters in a TDB file to conform to ESPEI's expectation of names starting with ``VV``, e.g. ``VV0042``, then you can perform the multi-phase fitting.
Traditionally, CALPHAD modelers perform multi-phase fitting in systems with many degrees of freedom by using their experience and knowledge of thermodynamics to break the problem of fitting all the parameters into small problems where only a few degrees of freedom (on the order of 1-5) change at a time.
Modelers iteratively allow several parameters to be degrees of freedom and perform a least squares minimization to optimize those parameters to their selected data, then a different (sometimes overlapping) set of parameters are chosen and optimized again.
This is repeated until the system has converged.

One drawback to this approach is that many different sets of parameters, and indeed different values for the same set of parameters can reproduce similar energetics and thus the same phase diagram.
This is because parameters are correlated within the description of each phase and between phases.
The order in which parameters are optimized can often affect the final result and the previous iterative methods of modeling typically involved adding parameters (sensibly, of course) as needed.
This required the same thermodynamic evaluation be performed multiple times once the final set of parameters was chosen, in order to find any irregularities introduced during the initial modeling.

ESPEI attempts to avoid these drawbacks completely.
First, for all multi-phase fitting, the total number of degrees of freedom are fixed at the time of initialization: no parameters are added or removed during the run (though the values of some parameters may approach zero).
Second, all of the parameters are concurrently treated as degrees of freedom, eliminating bias by the order that parameters are optimized in.
Unlike traditional modeling with limited active degrees of freedom, a single global optimum for all of the parameters is not tractable to compute numerically.
Instead, ESPEI uses the `emcee package <http://dan.iel.fm/emcee/>`_, which provides an interface to Markov Chain Monte Carlo (MCMC) algorithms for Bayesian optimization.

The basic idea of MCMC is to
1. take the entire set of parameters
2. update one parameter with a guess
3. use an objective function to determine if that guess improves the parameter set
4. if the new parameter set is closer to the objective, accept that guess as the new parameter set, otherwise sometimes accept and sometimes reject

The key points are in step 3 and 4.
In step 3, the objective function we are using is the same least squares criteria as in traditional modeling for the data.
Here, the data is *only* the multi-phase equilibria (points on the phase diagram).
All other data, such as single-phase heat capacities are not considered in the least squares calculation.
Step 4 is truly the heart of MCMC.
In step 4, if our new parameter set is better, we always want to keep that new guess that we made for a parameter so that we can optimize our parameters.
The rejection step can be counter intuitive: why would we want to accept a new parameter if overall we are further from reproducing our phase diagram?
Acceptance of parameter sets that are slightly worse at optimizing the objective function (again, minimizing the mean square error) helps us to avoid getting stuck in local minima and help to search the parameter space, overcoming the problem of optimization order.

Much like with single phase-data, successful optimization depends highly on input data.
The objective function compares phase equilibria calculated by pycalphad with the guessed parameter set to only the multi-phase data.
This means that the more data to compare, the better defined the optimum parameter set is.
The reverse is also true.

One particular catch is that for three phases in equilibrium, such as phases A, B, and C, if there are phase equilibria for A and B and B and C, but not A and B, then that phase boundary could freely wander in any way that allows the A-B and B-C phase equilibria to be optimized.
This can be unfamiliar to experienced modelers who are used to seeing rapid feedback in the form of phase diagrams as they optimize parameters.
Humans can use sketches, intuition and experience to tell when a phase boundary does not well represent the physical nature of the system being modeled, but a computer that can only interface with the phase diagram through scalar values calculated a objective function cannot.

For both types of fitting, the overall conclusion is the same: ESPEI requires data to well define all parameters and equilibria in the system of interest.

References
----------

1. `Richard Otis's thesis <https://etda.libraries.psu.edu/catalog/s1784k73d>`_, chapter 3, covers this fitting procedure, particularly for single-phases parameter selection and fitting in more detail.
2. `MCMC sampling for dummies <http://twiecki.github.io/blog/2015/11/10/mcmc-sampling/>`_ by Thomas Wiecki (one of the main developers behind `pymc3 <https://pymc-devs.github.io/pymc3/index.html>`_, a popular MCMC package for Python).
