import h5py
import numpy as np
from nav import *
import readgssi
import utils
import matplotlib.pyplot as plt
import scipy.io as scio
import sys,os,fnmatch,struct
# from segpy.reader import create_reader


class ingester:
    # ingester is a class to create a data ingester
    # builds a dictionary with data and metadata from the file
    # need to decide on a standard set of fields
    def __init__(self, ftype):
        # ftype is a string specifying filetype
        # valid options -
        # hdf5, mat, segy
        valid_types = ["h5", "mat", "sgy", "dzt", "img"] # can add more to this
        if (ftype.lower() not in valid_types):
            print("Invalid file type specifier: " + ftype)
            print("Valid file types:")
            print(valid_types)
            exit(1)

        self.ftype = ftype.lower()


    def read(self, fpath):
        # wrapper method for reading in a file
        # better ways to do this than an if/else
        # but for a few file types this is easier
        if (self.ftype == "h5"):
            return self.h5py_read(fpath)
        elif (self.ftype == "mat"):
            return self.mat_read(fpath)
        elif (self.ftype == "sgy"):
            return self.segypy_read(fpath)
        elif (self.ftype == "dzt"):
            return self.gssi_read(fpath)
        elif (self.ftype == "img"):
            return self.sharad_read(fpath)
        else:
            print("File reader for format {} not built yet".format(self.ftype))
            exit(1)


    ### method to ingest OIB-AK radar .h5 data format ###
    def h5py_read(self, fpath):
        print("----------------------------------------")
        print("Loading: " + fpath.split("/")[-1])
        # read in .h5 file
        f = h5py.File(fpath, "r")                               

        # h5 radar data group structure        
        # |-raw
        # |  |-rx0
        # |  |-loc0
        # |-ext
        # |  |-nav0
        # |  |-srf0
        # |-drv
        # |  |-proc0
        # |  |-clutter0
        # |  |-pick

        # pull necessary raw group data
        fs = f["raw/rx0/"].attrs["samplingFrequency-Hz"]        # sampling frequency, Hz
        num_trace = f["raw/rx0"].attrs["numTrace"]              # number of traces in rgram
        num_sample = f["raw/rx0"].attrs["samplesPerTrace"]      # samples per trace in rgram


        # pull necessary ext group nav data - use more precise Larsen nav data pulled from Trimble if available
        if "nav0" in f["ext"].keys():
            lon =  np.array(f["ext/nav0"]["lon"]).astype(np.float64)
            lat =  np.array(f["ext/nav0"]["lat"]).astype(np.float64)
            elev_air =  np.array(f["ext/nav0"]["altM"]).astype(np.float64)
            crs = f["ext/nav0"].attrs["CRS"].decode("utf-8") 
        # pull raw loc0 nav data if Larsen nav DNE
        else:
            lon =  np.array(f["raw/loc0"]["lon"]).astype(np.float64)
            lat =  np.array(f["raw/loc0"]["lat"]).astype(np.float64)
            elev_air =  np.array(f["raw/loc0"]["altM"]).astype(np.float64)
            crs = f["raw/loc0"].attrs["CRS"].decode("utf-8")             

        # pull lidar surface elevation if possible
        if "srf0" in f["ext"].keys():
            elev_gnd = np.array(f["ext/srf0"])                # surface elevation from lidar, averaged over radar first fresnel zone per trace (see code within /zippy/MARS/code/xped/hfProc/ext)
        # create empty arrays to hold surface elevation and twtt otherwise
        else:
            elev_gnd = np.repeat(np.nan, num_trace)

        # pull necessary drv group data
        amp = np.abs(np.array(f["drv/proc0"]))                  # pulse compressed amplitude array
        if "clutter0" in f["drv"].keys():
            clutter = np.array(f["drv/clutter0"])               # simulated clutter array
        else:
            clutter = np.ones(amp.shape)                        # empty clutter array if no sim exists
        
        # read in any existing picks
        pick = {}
        if "twtt_surf" in f["drv/pick"].keys():
            pick["twtt_surf"] = np.array(f["drv/pick"]["twtt_surf"])
        else:
            pick["twtt_surf"] = np.repeat(np.nan, num_trace)
            
        #  determine how many subsurface pick layers exist in the file - read each in as a numpy array to the pick dictionary
        num_file_pick_lyr = len(fnmatch.filter(f["drv/pick"].keys(), "twtt_subsurf*"))
        if num_file_pick_lyr > 0:
            # iterate through any existing subsurface pick layers to import
            for _i in range(num_file_pick_lyr):
                pick["twtt_subsurf" + str(_i)] = np.array(f["drv/pick"]["twtt_subsurf" + str(_i)])

        f.close()                                               # close the file

        # convert lon, lat, elev to nav object of nav class
        if "wgs" in crs.lower(): 
            nav0_proj4 = "+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs"
        else:
            print("Unknown nav coordinate reference system")
            sys.exit()
            
        nav0 = nav()
        nav0.csys = nav0_proj4
        nav0.navdat = np.column_stack((lon,lat,elev_air))

        # create dist array  - convert nav to meters then find cumulative euclidian distance
        ak_nad83_proj4 = "+proj=aea +lat_1=55 +lat_2=65 +lat_0=50 +lon_0=-154 +x_0=0 +y_0=0 +ellps=GRS80 +datum=NAD83 +units=m +no_defs" 
        nav0_xform = nav0.transform(ak_nad83_proj4)
        dist = utils.euclid_dist(nav0_xform)

        # interpolate nav data if not unique location for each trace
        if len(np.unique(lon)) < num_trace:
            nav0.navdat[:,0] = utils.interp_array(lon)
        if len(np.unique(lat)) < num_trace:
            nav0.navdat[:,1] = utils.interp_array(lat)
        if len(np.unique(dist)) < num_trace:
            dist = utils.interp_array(dist)

        dt = 1/fs
        trace = np.arange(num_trace)
        sample = np.arange(num_sample)

        # replace potential erroneous twtt_surf values with nan
        # get indices where twtt_surf is not nan
        idx = np.logical_not(np.isnan(pick["twtt_surf"]))
        pick["twtt_surf"][np.where(pick["twtt_surf"][idx] > sample[-1]*dt)[0]] = np.nan
        pick["twtt_surf"][np.where(pick["twtt_surf"][idx] <= sample[1]*dt)[0]] = np.nan
        
        # get indices of twtt_surf
        surf_idx = utils.twtt2sample(pick["twtt_surf"], dt)

        return {"dt": dt, "trace": trace, "sample": sample, "navdat": nav0, "elev_gnd": elev_gnd, "pick": pick, "surf_idx": surf_idx, "dist": dist, "amp": amp, "clutter": clutter, "num_file_pick_lyr": num_file_pick_lyr} # other fields?


    # method to ingest .mat files. for older matlab files, scio works and h5py does not. for newer files, h5py works and scio does not 
    def mat_read(self,fpath):
        try:
            f = h5py.File(fpath, "r")
            dt = float(f["block"]["dt"][0])
            num_trace = int(f["block"]["num_trace"][0])
            num_sample = int(f["block"]["num_sample"][0])
            lon = np.array(f["block"]["lon"]).flatten().astype(np.float64)
            lat = np.array(f["block"]["lat"]).flatten().astype(np.float64)
            elev_air = np.array(f["block"]["elev_air"]).flatten().astype(np.float64)
            twtt_surf = np.array(f["block"]["twtt_surf"]).flatten().astype(np.float64)
            amp = np.array(f["block"]["amp"])
            clutter = np.array(f["block"]["clutter"])
            f.close()

        except:
            try:
                f = scio.loadmat(fpath)
                dt = float(f["block"]["dt"][0])
                num_trace = int(f["block"]["num_trace"][0])
                num_sample = int(f["block"]["num_sample"][0])
                dist = f["block"]["dist"][0][0].flatten()
                lon = f["block"]["lon"][0][0].flatten().astype(np.float64)
                lat = f["block"]["lat"][0][0].flatten().astype(np.float64)
                elev_air = f["block"]["elev_air"][0][0].flatten().astype(np.float64)
                twtt_surf = f["block"]["twtt_surf"][0][0].flatten().astype(np.float64)
                amp = f["block"]["amp"][0][0]
                clutter = f["block"]["clutter"][0][0]

            except Exception as err:
                print("ingest Error: " + str(err))
                pass

        print("----------------------------------------")
        print("Loading: " + fpath.split("/")[-1])
        
        # transpose amp and clutter if flipped
        if amp.shape[0] == num_trace and amp.shape[1] == num_sample:
            amp = np.transpose(amp)  
        if clutter.shape[0] == num_trace and clutter.shape[1] == num_sample:
            clutter = np.transpose(clutter)
        
        # replace twtt_surf with nan"s if no data
        if not np.any(twtt_surf):
            twtt_surf.fill(np.nan)

        # calculate surface elevation 
        elev_gnd = elev_air - twtt_surf*C/2
        
        # create dictionary to hold picks
        pick = {}
        pick["twtt_surf"] = twtt_surf

        # convert lon, lat, elev to navdat object of nav class
        wgs84_proj4 = "+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs"
        nav0 = nav()
        nav0.csys = wgs84_proj4
        nav0.navdat = np.column_stack((lon,lat,elev_air))

        # create dist array  - convert nav to meters then find cumulative euclidian distance
        ak_nad83_proj4 = "+proj=aea +lat_1=55 +lat_2=65 +lat_0=50 +lon_0=-154 +x_0=0 +y_0=0 +ellps=GRS80 +datum=NAD83 +units=m +no_defs" 
        nav0_xform = nav0.transform(ak_nad83_proj4)
        dist = utils.euclid_dist(nav0_xform)

        # interpolate nav data if not unique location for each trace
        if len(np.unique(lon)) < num_trace:
            nav0.navdat[:,0] = utils.interp_array(lon)
        if len(np.unique(lat)) < num_trace:
            nav0.navdat[:,1] = utils.interp_array(lat)
        if len(np.unique(dist)) < num_trace:
            dist = utils.interp_array(dist)

        trace = np.arange(num_trace)
        sample = np.arange(num_sample)

        # replace potential erroneous twtt_surf values with nan
        # get indices where twtt_surf is not nan
        idx = np.logical_not(np.isnan(twtt_surf))
        twtt_surf[np.where(twtt_surf[idx] > sample[-1]*dt)[0]] = np.nan
        twtt_surf[np.where(twtt_surf[idx] <= sample[1]*dt)[0]] = np.nan

        # get indices of twtt_surf
        surf_idx = np.rint(twtt_surf/dt)


        return {"dt": dt, "trace": trace, "sample": sample, "navdat": nav0, "elev_gnd": elev_gnd, "pick": pick, "surf_idx": surf_idx, "dist": dist, "amp": amp, "clutter": clutter} # other fields?

    # method to ingest .sgy data
    def segypy_read(self, fpath):
        # with open(fpath, "rb") as segy_in_file:
        #     # The seg_y_dataset is a lazy-reader, so keep the file open throughout.
        #     seg_y_dataset = create_reader(segy_in_file, endian=">")  # Non-standard Rev 1 little-endian
        #     print(seg_y_dataset.num_traces())
        sys.exit()


    # method to read PDS SHARAD USRDR data
    def sharad_read(self, fpath):
        print("----------------------------------------")
        print("Loading: " + fpath.split("/")[-1])
        # convert binary .img PDS RGRAM to numpy array
        # reshape array with 3600 lines
        dtype = np.dtype("float32")     
        with open(fpath, "rb") as f:
            amp = np.fromfile(f, dtype)     
        l = len(amp)
        num_sample = 3600
        num_trace = int(len(amp)/num_sample)
        amp = amp.reshape(num_sample,num_trace)
        
        # convert binary .img clutter sim product to numpy array
        with open(fpath.replace("rgram","geom_combined"), "rb") as f:
            clutter = np.fromfile(f, dtype)   
        clutter = clutter.reshape(num_sample,num_trace)

        # open geom nav file for rgram
        geom_path = fpath.replace("rgram","geom").replace("img","tab")

        nav_file = np.genfromtxt(geom_path, delimiter = ",", dtype = str)

        # get necessary data from image file and geom
        dt = .0375e-6                                                                           # sampling interval for 3600 real-values voltage samples
        lon = nav_file[:,3].astype(np.float64)
        lat = nav_file[:,2].astype(np.float64)
        elev_air = nav_file[:,5].astype(np.float64) - nav_file[:,4].astype(np.float64)          # [km]

        elev_gnd = np.repeat(np.nan, num_trace)

        dist = np.arange(num_trace)

        twtt_surf = np.repeat(np.nan, num_trace)

        # create dictionary to hold picks
        pick = {}
        pick["twtt_surf"] = twtt_surf

        # create nav object to hold lon, lat, elev
        nav0 = nav()
        nav0.csys = "+proj=longlat +a=3396190 +b=3376200 +no_defs"
        nav0.navdat = np.column_stack((lon,lat,elev_air))

        # create dist array - convert nav to meters then find cumulative euclidian distance
        mars_equidistant_proj4 = "+proj=eqc +lat_ts=0 +lat_0=0 +lon_0=180 +x_0=0 +y_0=0 +a=3396190 +b=3396190 +units=m +no_defs" 
        nav0_xform = nav0.transform(mars_equidistant_proj4)
        dist = utils.euclid_dist(nav0_xform)

        trace = np.arange(num_trace)
        sample = np.arange(num_sample)


        # get indices of twtt_surf
        surf_idx = np.rint(twtt_surf/dt)
        return {"dt": dt, "trace": trace, "sample": sample, "navdat": nav0, "elev_gnd": elev_gnd, "pick": pick, "surf_idx": surf_idx, "dist": dist, "amp": amp, "clutter": clutter} # other fields?

    
    # method to read gssi dzt data
    def gssi_read(self, fpath):
        print("----------------------------------------")
        print("Loading: " + fpath.split("/")[-1])
        # use readgssi readdzt.dzt reader (credit: https://github.com/iannesbitt/readgssi)
        header, amp = readgssi.readdzt(fpath)#, gps=normalize, spm=spm, start_scan=start_scan, num_scans=num_scans, epsr=epsr, antfreq=antfreq, verbose=verbose)

        num_trace = amp.shape[-1]
        dt = header["dt"]
        trace = np.arange(num_trace)                            # array to hold trace numbers
        sample = np.arange(header["rh_nsamp"])                  # array to hold sample numbers

        clutter = np.ones(amp.shape)                            # place holder for clutter data
        surf_idx = np.repeat(np.nan, num_trace)                 # array to hold sample number for surface pick at each trace
        pick={}                                                 # dictionary to hold picks
        pick["twtt_surf"] = np.repeat(np.nan, num_trace)        # place holder for pick of twtt_surf

        # create nav object to hold lon, lat, elev
        wgs84_proj4 = "+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs"
        nav0 = nav()
        nav0.csys = wgs84_proj4

        # read in gps data if exists
        infile_gps = fpath.replace(".DZT",".DZG")
        if os.path.isfile(infile_gps):
            gps = readgssi.readdzg(infile_gps, 'dzg', header)
            
            # interpolate gps data to length of radara data
            if len(gps["trace"]) < num_trace:
                x = np.arange(gps["trace"][0], gps["trace"][-1] + 1)
                gps["lon"] = np.interp(x, gps["trace"], gps["lon"])
                gps["lat"] = np.interp(x, gps["trace"], gps["lat"])
                gps["elev"] = np.interp(x, gps["trace"], gps["elev"])
                gps["trace"] = x

            # may still need to extrapolate from ends - just copy beginning and end values for now
            if len(gps["trace"]) < num_trace:
                first = int(gps["trace"][0])
                last = int(gps["trace"][-1])
                gps["lon"] = utils.extend_array(gps["lon"], first, last, num_trace)
                gps["lat"] = utils.extend_array(gps["lat"], first, last, num_trace)
                gps["elev"] = utils.extend_array(gps["elev"], first, last, num_trace)
                gps["trace"] = np.arange(num_trace)
            
            # combine gps data as nav object
            nav0.navdat = np.column_stack((gps["lon"],gps["lat"],gps["elev"]))

            # create dist array  - convert nav to meters then find cumulative euclidian distance
            earth_equidist_proj4 = "+proj=aeqd +lat_0=0 +lon_0=0 +x_0=0 +y_0=0 +ellps=WGS84 +datum=WGS84 +units=m no_defs" #"+proj=longlat +a=6378140 +b=6356750 +no_defs"
            nav0_xform = nav0.transform(earth_equidist_proj4)
            dist = utils.euclid_dist(nav0_xform)

        else: 
            # if no gps data file, use nan arrays
            print("Warning: no associated nav data found")
            lon = np.repeat(np.nan, num_trace)
            lat = np.repeat(np.nan, num_trace)
            elev = np.repeat(np.nan, num_trace)
            dist = np.repeat(np.nan, num_trace)
            nav0.navdat = np.column_stack((lon, lat, elev))

        # for ground-based GPR, elev_gnd is the same as GPS recorded elev
        elev_gnd = nav0.navdat[:,2]

        return {"dt": dt, "trace": trace, "sample": sample, "navdat": nav0, "elev_gnd": elev_gnd, "pick": pick, "surf_idx": surf_idx, "dist": dist, "amp": amp, "clutter": clutter}

# load_picks is a method to load picks from a csv file
def load_picks(path):
    dat = np.genfromtxt(path, delimiter=",", dtype = None, names = True)
    twtt_bed = dat["twtt_bed"]
    return twtt_bed