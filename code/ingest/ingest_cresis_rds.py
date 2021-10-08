# RAGU - Radar Analysis Graphical Utility
#
# copyright © 2020 btobers <tobers.brandon@gmail.com>
#
# distributed under terms of the GNU GPL3.0 license
"""
ingest_cresis_rds is a module developed to ingest CReSIS radar depth sounder (RDS) data. 
"""
### imports ###
from radar import garlic
from nav import navparse
from tools import utils
import h5py, fnmatch
import numpy as np
import sys
import matplotlib.pyplot as plt
# method to ingest CReSIS RDS data
def read_mat(fpath, navcrs, body):
    rdata = garlic(fpath)
    rdata.fn = fpath.split("/")[-1][:-4]
    rdata.dtype = "cresis_rds"
    f = h5py.File(rdata.fpath, "r")                      

    # assign signal info
    rdata.info["System"] = str(f["param_records"]["radar_name"][:], 'utf-16')
    if "mcords" not in rdata.info["System"]:
        raise ValueError(None)
        return

    print("----------------------------------------")
    print("Loading: " + rdata.fn)

    rdata.set_dat(np.array(f["Data"][:]).T)
    rdata.set_proc(np.abs(rdata.get_dat()))

    rdata.snum = rdata.dat.shape[0]                                                 # samples per trace in rgram
    rdata.tnum = rdata.dat.shape[1]                                                 # number of traces in rgram 
    rdata.dt = np.mean(np.diff(f["Time"]))                                          # sampling interval, sec
    rdata.prf = f["param_records"]["radar"]["prf"][0][0]                            # pulse repitition frequency
    rdata.nchan = 1
    rdata.set_twtt()

    # parse nav
    rdata.navdf = navparse.getnav_cresis_mat(fpath, navcrs, body)
    
    # pull surface elevation and initilize horizon
    rdata.set_srfElev(dat = f["Surface"][:].flatten()) 

    rdata.pick.horizons["srf"] = utils.twtt2sample(rdata.get_srfElev(), rdata.dt)
    # rdata.set_srfElev(rdata.navdf["elev"] - utils.twtt2depth(rdata.pick.horizons["srf"], eps_r=1))
    rdata.pick.set_srf("srf")

    rdata.info["PRF [kHz]"] = rdata.prf * 1e-3

    f.close()                                                   # close the file

    rdata.check_attrs()

    return rdata