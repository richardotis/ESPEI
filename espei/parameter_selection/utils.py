"""
Tools used across parameter selection modules
"""

import itertools
import numpy as np
import sympy
from pycalphad import variables as v
from espei.utils import build_sitefractions
from espei.core_utils import get_samples

feature_transforms = {"CPM_FORM": lambda GM: -v.T*sympy.diff(GM, v.T, 2),
                      "CPM_MIX": lambda GM: -v.T*sympy.diff(GM, v.T, 2),
                      "CPM": lambda GM: -v.T*sympy.diff(GM, v.T, 2),
                      "SM_FORM": lambda GM: -sympy.diff(GM, v.T),
                      "SM_MIX": lambda GM: -sympy.diff(GM, v.T),
                      "SM": lambda GM: -sympy.diff(GM, v.T),
                      "HM_FORM": lambda GM: GM - v.T*sympy.diff(GM, v.T),
                      "HM_MIX": lambda GM: GM - v.T*sympy.diff(GM, v.T),
                      "HM": lambda GM: GM - v.T*sympy.diff(GM, v.T)}


def shift_reference_state(desired_data, feature_transform, fixed_model, mole_atoms_per_mole_formula_unit):
    """
    Shift _MIX or _FORM data to a common reference state in per mole-atom units.

    Parameters
    ----------
    desired_data : List[Dict[str, Any]]
        ESPEI single phase dataset
    feature_transform : Callable
        Function to transform an AST for the GM property to the property of
        interest, i.e. entropy would be ``lambda GM: -sympy.diff(GM, v.T)``
    fixed_model : pycalphad.Model
        Model with all lower order (in composition) terms already fit. Pure
        element reference state (GHSER functions) should be set to zero.
    mole_atoms_per_mole_formula_unit : float
        Number of moles of atoms in every mole atom unit.

    Returns
    -------
    np.ndarray
        Data for this feature in [qty]/mole-formula in a common reference state.

    Raises
    ------
    ValueError

    Notes
    -----
    pycalphad Model parameters are stored as per mole-formula quantites, but
    the calculated properties and our data are all in [qty]/mole-atoms. We
    multiply by mole-atoms/mole-formula to convert the units to
    [qty]/mole-formula.

    """
    total_response = []
    for dataset in desired_data:
        values = np.asarray(dataset['values'], dtype=np.object)*mole_atoms_per_mole_formula_unit
        for config_idx in range(len(dataset['solver']['sublattice_configurations'])):
            occupancy = dataset['solver'].get('sublattice_occupancies', None)
            if dataset['output'].endswith('_FORM'):
                pass
            elif dataset['output'].endswith('_MIX'):
                if occupancy is None:
                    raise ValueError('Cannot have a _MIX property without sublattice occupancies.')
                else:
                    values[..., config_idx] += feature_transform(fixed_model.models['ref'])*mole_atoms_per_mole_formula_unit
            else:
                raise ValueError(f'Unknown property to shift: {dataset["output"]}')
            for excluded_contrib in dataset.get('excluded_model_contributions', []):
                values[..., config_idx] += feature_transform(fixed_model.models[excluded_contrib])*mole_atoms_per_mole_formula_unit
        total_response.append(values.flatten())
    return total_response


def get_data_quantities(desired_property, fixed_model, fixed_portions, data):
    """
    Parameters
    ----------
    desired_property : str
        String property corresponding to the features that could be fit, e.g. HM, SM_FORM, CPM_MIX
    fixed_model : pycalphad.Model
        Model with all lower order (in composition) terms already fit. Pure
        element reference state (GHSER functions) should be set to zero.
    fixed_portions : List[sympy.Expr]
        SymPy expressions for model parameters and interaction productions for
        higher order (in T) terms for this property, e.g. [0, 3.0*YS*v.T]. In
        [qty]/mole-formula.
    data : List[Dict[str, Any]]
        ESPEI single phase datasets for this property.

    Returns
    -------
    np.ndarray[:]
        Ravelled data quantities in [qty]/mole-formula

    Notes
    -----
    pycalphad Model parameters (and therefore fixed_portions) are stored as per
    mole-formula quantites, but the calculated properties and our data are all
    in [qty]/mole-atoms. We multiply by mole-atoms/mole-formula to convert the
    units to [qty]/mole-formula.

    """
    mole_atoms_per_mole_formula_unit = fixed_model._site_ratio_normalization
    samples = get_samples(data)
    # Define site fraction symbols that will be reused
    YS = sympy.Symbol('YS')
    Z = sympy.Symbol('Z')
    V_I, V_J, V_K = sympy.Symbol('V_I'), sympy.Symbol('V_J'), sympy.Symbol('V_K')
    phase_name = fixed_model.phase_name

    # Construct flattened list of site fractions corresponding to the ravelled data (from shift_reference_state)
    site_fractions = []
    for ds in data:
        for _ in ds['conditions']['T']:
            sf = build_sitefractions(phase_name, ds['solver']['sublattice_configurations'], ds['solver'].get('sublattice_occupancies', np.ones((len(ds['solver']['sublattice_configurations']), len(ds['solver']['sublattice_configurations'][0])), dtype=np.float)))
            site_fractions.append(sf)
    site_fractions = list(itertools.chain(*site_fractions))

    feat_transform = feature_transforms[desired_property]
    data_qtys = np.concatenate(shift_reference_state(data, feat_transform, fixed_model, mole_atoms_per_mole_formula_unit), axis=-1)
    # Remove existing partial model contributions from the data, convert to per mole-formula units
    data_qtys = data_qtys - feat_transform(fixed_model.ast)*mole_atoms_per_mole_formula_unit
    # Subtract out high-order (in T) parameters we've already fit, already in per mole-formula units
    data_qtys = data_qtys - feat_transform(sum(fixed_portions))
    # if any site fractions show up in our data_qtys that aren't in this datasets site fractions, set them to zero.
    for sf, i, (_, (sf_product, inter_product)) in zip(site_fractions, data_qtys, samples):
        missing_variables = sympy.S(i).atoms(v.SiteFraction) - set(sf.keys())
        sf.update({x: 0. for x in missing_variables})
        # The equations we have just have the site fractions as YS
        # and interaction products as Z, so take the product of all
        # the site fractions that we see in our data qtys
        if hasattr(inter_product, '__len__'):  # Z is an array of [V_I, V_J, V_K]
            sf.update({YS: sf_product, V_I: inter_product[0], V_J: inter_product[1], V_K: inter_product[2]})
        else:  # Z is probably a number
            sf.update({YS: sf_product, Z: inter_product})
    data_qtys = [sympy.S(i).xreplace(sf).xreplace({v.T: ixx[0]}).evalf()
                 for i, sf, ixx in zip(data_qtys, site_fractions, samples)]
    data_qtys = np.asarray(data_qtys, dtype=np.float)
    return data_qtys
