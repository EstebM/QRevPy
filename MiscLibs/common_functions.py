import numpy as np
import scipy.stats as sp


def cosd(angle):
    
    return np.cos(np.pi * angle/180)


def sind(angle):
    
    return np.sin(np.pi * angle/180)


def tand(angle):
    
    return np.tan(np.pi * angle/180)


def arctand(angle):
    
    return np.arctan(angle) * 180/np.pi


def cart2pol(x, y):
    
    rho = np.sqrt(x**2 + y**2)
    phi = np.arctan2(y, x)
    
    return phi, rho


def pol2cart(phi, rho):
    
    x = rho * np.cos(phi)
    y = rho * np.sin(phi)
    
    return x, y


def iqr(data):
    """This function computes the iqr consistent with Matlab"""

    # If 2-D array use only 1st row
    if len(data.shape) > 1:
        data_1d = data.flatten()
    else:
        data_1d = data

    # Remove nan elements
    idx = np.where(np.isnan(data_1d) == False)[0]
    data_1d = data_1d[idx]

    # Compute statistics
    q25, q50, q75 = sp.mstats.mquantiles(data_1d, alphap=0.5, betap=0.5)
    sp_iqr = q75 - q25
    return sp_iqr


def azdeg2rad(angle):
    direction = np.deg2rad(90-angle)
    idx = np.where(direction < 0)[0]
    if len(idx) > 1:
        direction[idx] = direction[idx] + 2 * np.pi
    else:
        direction = direction + 2 * np.pi
        
    return direction


def rad2azdeg(angle):
    if isinstance(angle, float):
        deg = np.rad2deg(angle)
        deg = 90 - deg
        if deg < 0:
            deg += 360
            
        return deg
    else:
        # Multiple values
        deg = np.rad2deg(angle)
        deg = 90 - deg
        sub_zero = np.where(deg < 0)
        deg[sub_zero] = deg[sub_zero] + 360
        
        return deg


def nandiff(values):
    
    final_values = []
    for n in range(len(values) - 1):
        
        if np.isnan(values[n]):
            final_values.append(np.nan)
        else:
            i = n + 1
            while np.isnan(values[i]) and i < len(values) - 1:
                i += 1
            
            final_values.append(values[i] - values[n])
        
    return np.array(final_values)


def get_object_values(list_in, item, checked=None):
    if checked is not None:
        working_list = list_in[checked is True]
    else:
        working_list = list_in

    if working_list is list:
        out = []
        for obj in working_list:
            temp = getattr(obj, item)
            out.append(temp)
    else:
        out = getattr(working_list, item)
    return np.array(out)


def sontek_3d_arrange(data_in):
    r1 = np.squeeze(data_in[:, 0, :])
    r2 = np.squeeze(data_in[:, 1, :])
    r3 = np.squeeze(data_in[:, 2, :])
    r4 = np.squeeze(data_in[:, 3, :])
    new_array = np.array([r1, r2, r3, r4])
    return new_array


def valid_number(data_in):
    """Check to see if data_in can be converted to float.

    Parameters
    ----------
    data_in: str
        String to be converted to float

    Returns
    -------
    data_out: float
        Returns a float of data_in or nan if conversion is not possible
    """

    try:
        data_out = float(data_in)
    except ValueError:
        data_out = np.nan
    return data_out


def nans(shape, dtype=float):
    a = np.empty(shape, dtype)
    a.fill(np.nan)
    return a


def checked_idx(transects):
    checked = []
    for n, transect in enumerate(transects):
        if transect.checked:
            checked.append(n)

    return checked

def units_conversion(units_id='SI'):
    """Computes the units conversion from SI units used internally to the
    desired display units.

    Parameters
    ----------
    units: str
        String variable identifying units (English, SI) SI is the default.

    Returns
    -------
    units: dict
        dictionary of unit conversion and labels
    """

    if units_id == 'SI':
        units = {'L': 1,
                 'Q': 1,
                 'A': 1,
                 'V': 1,
                 'label_L': '(m)',
                 'label_Q': '(m3/s)',
                 'label_A': '(m2)',
                 'label_V': '(m/s)',
                 'ID': 'SI'}

    else:
        units = {'L': 1.0 / 0.3048,
                 'Q': (1.0 / 0.3048)**3,
                 'A': (1.0 / 0.3048)**2,
                 'V': 1.0 / 0.3048,
                 'label_L': '(ft)',
                 'label_Q': '(ft3/s)',
                 'label_A': '(ft2)',
                 'label_V': '(ft/s)',
                 'ID': 'English'}

    return units

def convert_temperature(temp_in, units_in, units_out):
    """Converts temperature from F to C or C to F.

    Parameters
    ==========
    temp_in: np.array
        temperature in units_in
    units_in: str
        C for Celcius or F for Fahrenheit
    units_out: str
        C for Celcius or F for Fahrenheit

    Returns
    =======
    temp_out: np.array
        temperature in units_out
    """

    if units_in == 'F':
        if units_out == 'C':
            temp_out = (temp_in - 32) * (5./9.)
        else:
            temp_out = temp_in

    elif units_in == 'C':
        if units_out == 'C':
            temp_out = temp_in
        else:
            temp_out = (temp_in * (9./5.)) + 32

    return temp_out