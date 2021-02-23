# RAGU - Radar Analysis Graphical Utility
#
# copyright © 2020 btobers <tobers.brandon@gmail.com>
#
# distributed under terms of the GNU GPL3.0 license
"""
wvpick class is a tkinter frame which handles the RAGU waveform view and radar pick optimization
"""
### imports ###
from tools import utils
import numpy as np
from scipy.interpolate import CubicSpline
from scipy.signal import find_peaks
import tkinter as tk
import sys,os,time,copy
import matplotlib as mpl
mpl.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

class wvpick(tk.Frame):
    # wvpick is a class to optimize the picking of horizons from radar data
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent
        self.winSize = tk.IntVar(value=100)
        self.stepSize = tk.IntVar(value=10)
        self.horVar = tk.StringVar()
        self.segVar = tk.IntVar()
        self.color = tk.StringVar()
        self.interpType = tk.StringVar()
        self.interpType.set("cubic")
        self.setup()

    def setup(self):
        # set up frames
        infoFrame0 = tk.Frame(self.parent)
        infoFrame0.pack(side="top",fill="both")        
        infoFrame = tk.Frame(infoFrame0)
        infoFrame.pack(side="left",fill="both")
        interpFrame = tk.Frame(infoFrame0)
        interpFrame.pack(side="right",fill="both")
        # interpFrame.pack_propagate(0)
        toolbarFrame = tk.Frame(infoFrame)
        toolbarFrame.pack(side="bottom",fill="both")
        self.dataFrame = tk.Frame(self.parent)
        self.dataFrame.pack(side="top", fill="both", expand=1)

        # interpFrame = tk.Frame(toolbarFrame)
        # interpFrame.pack(side="right",fill="both")
        # subsurf_interpFrame = tk.Frame(interpFrame)
        # subsurf_interpFrame.pack(side="right",fill="both")    
        # tk.ttk.Separator(interpFrame,orient="vertical").pack(side="right", fill="both", padx=10, pady=4)
        # surf_interpFrame = tk.Frame(interpFrame)
        # surf_interpFrame.pack(side="right",fill="both")
        # tk.ttk.Separator(interpFrame,orient="vertical").pack(side="right", fill="both", padx=10, pady=4)
        # self.dataFrame = tk.Frame(self.parent)
        # self.dataFrame.pack(side="bottom", fill="both", expand=1)

        # self.segmentVar = tk.IntVar()
        # self.segmentVar.trace('w', self.plot_wv)

        # infoFrame exists for options to be added based on optimization needs
        tk.Label(infoFrame, text = "Amplitude Window [#Samples]: ").pack(side="left")
        tk.Entry(infoFrame, textvariable=self.winSize, width = 5).pack(side="left")
        tk.Label(infoFrame, text = "\tStep Size [#Traces]: ").pack(side="left")
        tk.Entry(infoFrame, textvariable=self.stepSize, width = 5).pack(side="left")
        tk.Label(infoFrame, text="\t").pack(side="left")
        tk.Button(infoFrame, text="←", command = self.stepBackward, pady=0).pack(side="left")
        tk.Button(infoFrame, text="→", command = self.stepForward, pady=0).pack(side="left")
        tk.Label(infoFrame, text="\t").pack(side="left")
        
        # set up frame to hold pick information
        interpFrameT = tk.Frame(interpFrame)
        interpFrameT.pack(fill="both",expand=True)
        # interpFrameT.pack_propagate(0)
        interpFrameB = tk.Frame(interpFrame)
        interpFrameB.pack(fill="both",expand=True)
        # interpFrameB.pack_propagate(0)

        interpFrameTl = tk.Frame(interpFrameT,width=400,relief="ridge", borderwidth=1)
        interpFrameTl.pack(side="left",fill="both",expand=True)
        # interpFrameTl.pack_propagate(0)

        interpFrameBl = tk.Frame(interpFrameB,width=400,relief="ridge", borderwidth=1)
        interpFrameBl.pack(side="left",fill="both",expand=True)
        # interpFrameBl.pack_propagate(0)

        tk.Label(interpFrameTl,text="Horizon:\t").pack(side="left")
        self.horizons=[None]
        self.horMenu = tk.OptionMenu(interpFrameTl, self.horVar, *self.horizons)
        self.horMenu.pack(side="left")
        self.horMenu.config(width=20)
        self.horVar.trace("w", lambda *args, last=True : self.update_seg_opt_menu(last)) 
        self.horVar.trace("w", lambda *args, menu=self.horMenu : self.set_menu_color(menu))
        # tk.Button(interpFrameTl, text="Delete", width=4, command=lambda:self.rm_horizon(horizon=self.horVar.get(), verify=True)).pack(side="right")
        # tk.Button(interpFrameTl, text="New", width=4, command=self.init_horizon).pack(side="right")

        tk.Label(interpFrameBl,text="Segment: ").pack(side="left")
        segments=[None]
        self.segMenu = tk.OptionMenu(interpFrameBl, self.segVar, *segments)
        self.segMenu.pack(side="left")
        self.segMenu.config(width=2)
        # tk.Button(interpFrameBl, text="Delete", width=4, command=lambda:self.rm_segment(horizon=self.horVar.get(),seg=self.segVar.get())).pack(side="right")
        # tk.Button(interpFrameBl, text="Edit", width=4, command=lambda:self.edit_segment(horizon=self.horVar.get(),seg=self.segVar.get())).pack(side="right")
        # tk.Button(interpFrameBl, text="New", width=4, command=lambda:self.init_segment(horizon=self.horVar.get())).pack(side="right")


        # self.segments=[0]
        # self.segmentMenu = tk.OptionMenu(infoFrame, self.segmentVar, *self.segments)
        # self.segmentMenu.pack(side="right",pady=0)
        # tk.Label(infoFrame, text = "subsurface pick seg: ").pack(side="right")

        # create figure object and datacanvas from it
        plt.rcParams.update({'font.size': 12})
        self.fig = mpl.figure.Figure()
        self.fig.patch.set_facecolor("#d9d9d9")
        self.dataCanvas = FigureCanvasTkAgg(self.fig, self.parent)
        self.dataCanvas.get_tk_widget().pack(in_=self.dataFrame, side="bottom", fill="both", expand=1) 
        self.click = self.fig.canvas.mpl_connect("button_press_event", self.onpress)
        self.unclick = self.fig.canvas.mpl_connect('button_release_event', self.onrelease)

        # add toolbar to plot
        self.toolbar = NavigationToolbar2Tk(self.dataCanvas, toolbarFrame)
        self.toolbar.pack(side="left")
        # self.toolbar.update()

        # label = tk.Label(surf_interpFrame, text = "surface pick optimization")
        # label.pack(side="top")
        # f = tk.font.Font(label, label.cget("font"))
        # f.configure(underline=True)
        # label.configure(font=f)
        # tk.Button(surf_interpFrame, text="auto-pick", command=self.surf_autoPick, pady=0).pack()

        # label = tk.Label(subsurf_interpFrame, text = "subsurface pick optimization")
        # label.pack(side="top")
        # f = tk.font.Font(label, label.cget("font"))
        # f.configure(underline=True)
        # label.configure(font=f)
        # tk.Button(subsurf_interpFrame, text="auto-pick", command=self.subsurf_autoPick, pady=0).pack(side="right")
        # tk.Button(subsurf_interpFrame, text="interpolate", command=self.subsurf_interpPicks, pady=0).pack(side="right")
        # tk.Radiobutton(subsurf_interpFrame, text="linear", variable=self.interpType, value="linear").pack(side="right")
        # tk.Radiobutton(subsurf_interpFrame,text="cubic spline", variable=self.interpType, value="cubic").pack(side="right")

        # create the figure axes
        self.ax = self.fig.add_subplot(111)
        self.fig.tight_layout(rect=[.02,.05,.97,1])
        self.ax.set_visible(False)

        # update the canvas
        self.dataCanvas._tkcanvas.pack()
        self.dataCanvas.draw()
    

    def set_vars(self):
        # set up variables
        self.pick_dict0 = {}
        self.pick_dict1 = {}
        self.rePick = None
        self.rePick_idx = {}        # dictionary of indeces of repicked traces for each seg


        self.rdata = None
        self.horizon_paths_opt = {}
        self.ln_colors = {}
        self.horizons = []



    # set_data is a method to receive the radar data
    def set_data(self, rdata):
        # get data in dB
        self.rdata = rdata


    # receive horizon paths from impick
    def set_horizon_paths(self, horizon_paths):
        self.horizon_paths = copy.deepcopy(horizon_paths)
        self.horizon_paths_opt = copy.deepcopy(horizon_paths)
        self.horizons = list(self.horizon_paths_opt)


    # receive horizon line colors
    def set_horizon_colors(self, ln_colors):
        self.ln_colors = ln_colors


    # set_picks is a method which receives horizon interpretations for optimization
    def set_picks(self):
        # determine number of horizons
        self.nhorizons = len(self.horizons)
        self.ax.set_visible(True)
        self.update_hor_opt_menu()
        self.update_seg_opt_menu()
        # create lists of first and last picked trace number for each seg in each horizon
        self.segment_traces = {}
        # create dict to hold current trace number for each horizon
        self.trace = {}
        if self.nhorizons > 0:
            # set horVar
            self.horVar.set(self.horizons[-1])
            # iterate through horizon_paths
            for horizon, hdict in self.horizon_paths_opt.items():
                self.segment_traces[horizon] = bounds([],[])
                self.trace[horizon] = None
                # iterate through segments for each horizon
                for seg, path in hdict.items():
                    picked_traces = np.where(~np.isnan(path.x))[0]
                    if picked_traces.shape[0] > 0:
                        self.segment_traces[horizon].first.append(picked_traces[0])
                        self.segment_traces[horizon].last.append(picked_traces[-1])
                        self.trace[horizon]= picked_traces[0]
        else:
            self.trace[""] = 0


    # plot_wv is a method to draw the waveform on the datacanvas
    def plot_wv(self, *args):
        horizon = self.horVar.get()
        seg = self.segVar.get()
        winSize = self.winSize.get()
        # if self.pick_dict1:
        self.ax.clear()
        self.ax.set(xlabel = "Sample", ylabel = "Power [dB]", title="Trace: " + str(int(self.trace[horizon] + 1)) + "/" + str(int(self.rdata.tnum)))

        # plot trace power
        self.ax.plot(self.rdata.proc[:,self.trace[horizon]], c="0.5")

        # get pick value range
        val = np.array(())

        # if self.nhorizons > 0:
        for horizon in self.horizons:
            # get sample index of pick for given trace
            pick_idx0 = self.horizon_paths[horizon][seg].y[self.trace[horizon]]
            pick_idx1 = self.horizon_paths_opt[horizon][seg].y[self.trace[horizon]]
            val = np.append(val, (pick_idx0+pick_idx1)//2)

            self.ax.axvline(x = pick_idx0, c=self.ln_colors[horizon], label=horizon)

            if pick_idx0 != pick_idx1:
                self.ax.axvline(x = pick_idx1, c=self.ln_colors[horizon], ls = "--", label=horizon + "_v2")
        
        # save un-zoomed view to toolbar
        self.toolbar.push_current()

        # zoom in to window around horizons
        if not np.isnan(val).all():
            self.ax.set(xlim=(int(min(val)-(2*winSize)),int(max(val)+(2*winSize))))

        if self.nhorizons > 0:
            self.ax.legend()

        self.dataCanvas.draw()


    # full extent for trace
    def fullExtent(self):
        horizon = self.horVar.get()
        self.ax.set_xlim(0, self.rdata.snum)
        self.ax.set_ylim(self.rdata.proc[:,self.trace[horizon]].min(), self.rdata.proc[:,self.trace[horizon]].max())
        self.dataCanvas.draw()


    # stepBackward is a method to move backwards by the number of traces entered to stepSize
    def stepBackward(self):
        horizon = self.horVar.get()
        seg = self.segVar.get()
        step = self.stepSize.get()
        newTrace = self.trace[horizon] - step
        if self.horizon_paths_opt:
            firstTrace_seg = self.segment_traces[horizon].first[seg]
            if newTrace >= firstTrace_seg:
                self.trace[horizon] -= step
            elif newTrace < firstTrace_seg:
                self.trace[horizon] = firstTrace_seg

        else:
            if newTrace >= 0:
                self.trace[0] -= step
            elif newTrace < 0:
                self.trace[0] = 0
            
        self.plot_wv()


    # stepForward is a method to move forward by the number of traces entered to stepSize
    def stepForward(self):
        horizon = self.horVar.get()
        seg = self.segVar.get()
        step = self.stepSize.get()
        newTrace = self.trace[horizon] + step
        if self.nhorizons > 0:
            lastTrace_seg = self.segment_traces[horizon].last[seg]
            if newTrace <= lastTrace_seg:
                self.trace[horizon] += step
            # if there are less traces left in the pick seg than the step size, move to the last trace in the seg
            elif newTrace > lastTrace_seg:
                if self.trace[seg] == lastTrace_seg:
                    if seg + 2 <= self.nhorizons and tk.messagebox.askokcancel("Next Sement","Finished optimization of current pick seg\n\tProceed to next seg?") == True:
                        self.segmentVar.set(seg + 1) 
                else:
                    self.trace[horizon] = self.segment_traces[horizon].last[seg]
        
        else:
            if newTrace <= self.rdata.tnum:
                self.trace[0] += step
            elif newTrace > self.rdata.tnum:
                if self.trace[0] == self.rdata.tnum - 1:
                    return
                else:
                    self.trace[0] = self.rdata.tnum - 1

        self.plot_wv()


    # surf_autoPick is a method to automatically optimize surface picks by selecting the maximul amplitude sample within the specified window around existing self.rdata.surf
    def surf_autoPick(self):
        if np.all(np.isnan(self.rdata.pick.current_surf)):
            if self.rdata.flags.sampzero:
                self.rdata.pick.current_surfOpt = np.zeros(self.rdata.tnum)
            else:
                # if surf idx array is all nans, take max power to define surface 
                max_idx = np.nanargmax(self.rdata.proc[10:,:], axis = 0) + 10
                # remove outliers
                not_outlier = utils.remove_outliers(max_idx)
                # interpolate, ignoring outliers
                x = np.arange(self.rdata.tnum)
                self.rdata.pick.current_surfOpt = np.interp(x, x[not_outlier], max_idx[not_outlier])

        else:
            # if existing surface pick, find max within specified window form existing pick
            winSize = self.winSize.get()
            x = np.argwhere(~np.isnan(self.rdata.pick.current_surf))
            y = self.rdata.pick.current_surf[x]
            for _i in range(len(x)):
                # find argmax for window for given data trace in pick
                max_idx = np.argmax(self.rdata.proc[int(y[_i] - (winSize/2)):int(y[_i] + (winSize/2)), x[_i]])
                # add argmax index to pick_dict1 - account for window index shift
                self.rdata.pick.current_surfOpt[x[_i]] = max_idx + int(y[_i] - (winSize/2))
        self.plot_wv()


    # subsurf_autoPick is a method to automatically optimize subsurface picks by selecting the maximul amplitude sample within the specified window around existing picks
    def subsurf_autoPick(self):
        if self.nhorizons > 0:
            winSize = self.winSize.get()
            for _i in range(self.nhorizons):
                x = np.where(~np.isnan(self.rdata.pick.current_subsurf[_i]))[0]
                y = self.rdata.pick.current_subsurf[_i][x]
                for _j in range(len(x)):
                    # find argmax for window for given data trace in pick
                    max_idx = np.argmax(self.rdata.proc[int(y[_j] - (winSize/2)):int(y[_j] + (winSize/2)), x[_j]])
                    # add argmax index to pick_dict1 - account for window index shift
                    self.rdata.pick.current_subsurfOpt[_i][x[_j]] = max_idx + int(y[_j] - (winSize/2))
            self.plot_wv()


    # manualPick is a method to manually adjust existing picks by clicking along the displayed waveform
    def manualPick(self, event):
        if (not self.nhorizons > 0) or (event.inaxes != self.ax):
            return
        seg = self.segmentVar.get()
        # append trace number to rePick_idx list to keep track of indeces for interpolation
        if (len(self.rePick_idx[seg]) == 0) or (self.rePick_idx[seg][-1] != self.trace[seg]):
            self.rePick_idx[seg].append(self.trace[seg])
        
        self.rdata.pick.current_subsurfOpt[seg][self.trace[seg]] = int(event.xdata)        
        self.plot_wv()


    # interpPicks is a method to interpolate between manually refined subsurface picks
    def subsurf_interpPicks(self):
        if (not self.nhorizons > 0):
            return
        interp = self.interpType.get()
        if interp == "linear":
            for _i in range(self.nhorizons):
                if len(self.rePick_idx[_i]) >= 2:
                    # get indices where picks exist for pick seg
                    rePick_idx = self.rePick_idx[_i]
                    # add cubic spline output interpolation to pick dictionary
                    interp_idx = np.arange(rePick_idx[0],rePick_idx[-1] + 1)
                    # get indeces of repicked traces
                    xp = self.rePick_idx[_i]
                    # get twtt values at repicked indicesself.pick_dict1
                    fp = self.rdata.pick.current_subsurfOpt[_i][xp]
                    # interpolate repicked values for seg
                    self.rdata.pick.current_subsurfOpt[_i][interp_idx] = np.interp(interp_idx, xp, fp)            


        elif interp == "cubic":
            for _i in range(self.nhorizons):
                if len(self.rePick_idx[_i]) >= 2:
                    # cubic spline between picks
                    rePick_idx = self.rePick_idx[_i]
                    cs = CubicSpline(rePick_idx, self.rdata.pick.current_subsurfOpt[_i][rePick_idx])
                    # generate array of indices between first and last optimized pick
                    interp_idx = np.arange(rePick_idx[0],rePick_idx[-1] + 1)
                    # add cubic spline output interpolation to pick dictionary
                    self.rdata.pick.current_subsurfOpt[_i][interp_idx] = cs([interp_idx]).astype(int)


    # set tkinter menu font colors to match color name
    def set_menu_color(self, menu=None, *args):
        horizon = self.horVar.get()
        if not horizon:
            return
        c = self.ln_colors[horizon]
        menu.config(foreground=c, activeforeground=c, highlightcolor=c)


    # update the horizon menu
    def update_hor_opt_menu(self):
        self.horizons = list(self.horizon_paths_opt.keys())
        self.horMenu["menu"].delete(0, "end")
        for i, horizon in enumerate(self.horizons):
            c = self.ln_colors[horizon]
            self.horMenu["menu"].add_command(label=horizon, foreground=c, activeforeground=c, command=tk._setit(self.horVar, horizon))


    # update the horizon seg menu based on how many segments exist for given seg
    def update_seg_opt_menu(self, last=False, *args):
        horizon = self.horVar.get()
        self.segMenu["menu"].delete(0, "end")
        if horizon:
            for seg in sorted(self.horizon_paths_opt[horizon].keys()):
                self.segMenu["menu"].add_command(label=seg, command=tk._setit(self.segVar, seg))
            # set seg selection to last
            if last:
                self.segVar.set(seg)


    # onpress gets the time of the button_press_event
    def onpress(self,event):
        self.time_onclick = time.time()


    # onrelease calls addseg() if the time between the button press and release events
    # is below a threshold so that segments aren't drawn while trying to zoom or pan
    def onrelease(self,event):
        if event.inaxes == self.ax:
            if event.button == 1 and ((time.time() - self.time_onclick) < 0.25):
                self.manualPick(event)


    # update_figsettings
    def update_figsettings(self, figsettings):
        self.figsettings = figsettings

        plt.rcParams.update({'font.size': self.figsettings["fontsize"].get()})

        for item in ([self.ax.title, self.ax.xaxis.label, self.ax.yaxis.label] +
                    self.ax.get_xticklabels() + self.ax.get_yticklabels()):
            item.set_fontsize(self.figsettings["fontsize"].get())

        self.ax.title.set_visible(self.figsettings["figtitle"].get())

        self.fig.canvas.draw()


    # clear is a method to clear the wavePick tab and stored data when a new track is loaded
    def clear(self):
        self.ax.clear()
        self.dataCanvas.draw()
        self.set_vars()


class bounds():
    # initialize a bounds object to hold first,last trace for interpretation segments - list or array like
    def __init__(self, first=None, last=None):
        self.first = first      # x array/list
        self.last = last      # y array/list