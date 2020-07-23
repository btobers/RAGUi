### IMPORTS ###
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

        # set up frames
        infoFrame = tk.Frame(self.parent)
        infoFrame.pack(side="top",fill="both",anchor="center")
        toolbarFrame = tk.Frame(infoFrame)
        toolbarFrame.pack(side="bottom",fill="both")
        interpFrame = tk.Frame(toolbarFrame)
        interpFrame.pack(side="right",fill="both")
        subsurf_interpFrame = tk.Frame(interpFrame)
        subsurf_interpFrame.pack(side="right",fill="both")    
        tk.ttk.Separator(interpFrame,orient="vertical").pack(side="right", fill="both", padx=10, pady=4)
        surf_interpFrame = tk.Frame(interpFrame)
        surf_interpFrame.pack(side="right",fill="both")
        tk.ttk.Separator(interpFrame,orient="vertical").pack(side="right", fill="both", padx=10, pady=4)
        self.dataFrame = tk.Frame(self.parent)
        self.dataFrame.pack(side="bottom", fill="both", expand=1)

        self.winSize = tk.IntVar(value=100)
        self.stepSize = tk.IntVar(value=10)
        self.segmentVar = tk.IntVar()
        self.segmentVar.trace('w', self.plot_wv)

        self.subsurf_interpType = tk.StringVar()

        # infoFrame exists for options to be added based on optimization needs
        tk.Label(infoFrame, text = "window size [#samples]: ").pack(side="left")
        tk.Entry(infoFrame, textvariable=self.winSize, width = 5).pack(side="left")
        tk.Label(infoFrame, text = "\tstep size [#traces]: ").pack(side="left")
        tk.Entry(infoFrame, textvariable=self.stepSize, width = 5).pack(side="left")
        tk.Label(infoFrame, text="\t").pack(side="left")
        tk.Button(infoFrame, text="←", command = self.stepBackward, pady=0).pack(side="left")
        tk.Button(infoFrame, text="→", command = self.stepForward, pady=0).pack(side="left")
        tk.Label(infoFrame, text="\t").pack(side="left")
        
        self.segments=[0]
        self.segmentMenu = tk.OptionMenu(infoFrame, self.segmentVar, *self.segments)
        self.segmentMenu.pack(side="right",pady=0)
        tk.Label(infoFrame, text = "subsurface pick segment: ").pack(side="right")

        # create figure object and datacanvas from it
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

        label = tk.Label(surf_interpFrame, text = "surface pick optimization")
        label.pack(side="top")
        f = tk.font.Font(label, label.cget("font"))
        f.configure(underline=True)
        label.configure(font=f)
        tk.Button(surf_interpFrame, text="auto-pick", command=self.surf_autoPick, pady=0).pack()

        label = tk.Label(subsurf_interpFrame, text = "subsurface pick optimization")
        label.pack(side="top")
        f = tk.font.Font(label, label.cget("font"))
        f.configure(underline=True)
        label.configure(font=f)
        tk.Button(subsurf_interpFrame, text="auto-pick", command=self.subsurf_autoPick, pady=0).pack(side="right")
        tk.Button(subsurf_interpFrame, text="interpolate", command=self.subsurf_interpPicks, pady=0).pack(side="right")
        tk.Radiobutton(subsurf_interpFrame, text="linear", variable=self.subsurf_interpType, value="linear").pack(side="right")
        tk.Radiobutton(subsurf_interpFrame,text="cubic spline", variable=self.subsurf_interpType, value="cubic").pack(side="right")

        # create the figure axes
        self.ax = self.fig.add_subplot(111)
        self.ax.set_visible(False)

        # update the canvas
        self.dataCanvas._tkcanvas.pack()
        self.dataCanvas.draw()
    

    def set_vars(self):
        # set up variables
        self.trace = 0.
        self.pick_dict0 = {}
        self.pick_dict1 = {}
        self.rePick = None
        self.surf_idx = None
        self.rePick_idx = {}        # dictionary of indeces of repicked traces for each segment
        self.subsurf_interpType.set("cubic")


    # set_data is a method to receive the radar data
    def set_data(self, data):
        # get data in dB
        self.data_dB = utils.amp2powdB(data["amp"])
        self.num_trace = data["trace"][-1] + 1
        self.surf_idx = data["surf_idx"]


    # set_surf is a method to set the surface index along in the case that a manual surface pick is made in the imPick tab after ingest
    def set_surf(self,surf_idx):
        self.surf_idx = surf_idx

    
    # get_surf is a method to return the optimized surface pick indices
    def get_surf(self):
        return self.surf_idx


    # get_pickDict is a method to return the pick dictionary
    def get_pickDict(self):
        return dict(self.pick_dict1)


    # set_pickDict is a method which holds the picked segment data for optimization
    def set_pickDict(self, pickDict):
        # create a copy of pick_dict passed from imPick as to not modify original values
        self.pick_dict0 = pickDict
        self.pick_dict1 = copy.deepcopy(pickDict)

        # determine number of pick segments
        self.num_pkLyrs = len(self.pick_dict0)
        self.ax.set_visible(True)
        self.update_option_menu()

        # create lists of first and last picked trace number for each segment
        self.segment_trace_first = []
        self.segment_trace_last = []
        # create list to hold current trace number for each layer
        self.traceNum = []
        for _i in range(self.num_pkLyrs):
            picked_traces = np.where(~np.isnan(self.pick_dict0[str(_i)]))[0]
            self.segment_trace_first.append(picked_traces[0])
            self.segment_trace_last.append(picked_traces[-1])
            self.traceNum.append(picked_traces[0])
        if not self.pick_dict0:
            self.traceNum.append(int(0))


    # plot_wv is a method to draw the waveform on the datacanvas
    def plot_wv(self, *args):
        segment = self.segmentVar.get()
        winSize = self.winSize.get()
        # if self.pick_dict1:
        self.ax.clear()
        self.ax.set(xlabel = "sample", ylabel = "power [dB]")

        surf = self.surf_idx[self.traceNum[segment]]

        self.ax.plot(self.data_dB[:,self.traceNum[segment]], label="trace: " + str(int(self.traceNum[segment] + 1)) + "/" + str(int(self.num_trace)))

        if not np.isnan(surf):
            self.ax.axvline(x = surf, c='c', label="surface")

        if self.pick_dict0:
            # get sample index of pick for given trace
            pick_idx0 = self.pick_dict0[str(segment)][self.traceNum[segment]]
            pick_idx1 = self.pick_dict1[str(segment)][self.traceNum[segment]]

            self.ax.axvline(x = pick_idx0, c="k", label="initial subsurface pick")

            if pick_idx0 != pick_idx1:
                self.ax.axvline(x = pick_idx1, c="g", ls = "--", label="updated pick")
        
            # # save un-zoomed view to toolbar10*np.log10(np.power(data["amp"][mask],2))
            # self.toolbar.push_current()

            # # zoom in
            # self.ax.set(xlim=(int(pick_idx0-(winSize/2)),int(pick_idx0+(winSize/2))))

        self.ax.legend()

        self.dataCanvas.draw()


    # stepBackward is a method to move backwards by the number of traces entered to stepSize
    def stepBackward(self):
        segment = self.segmentVar.get()
        step = self.stepSize.get()
        newTrace = self.traceNum[segment] - step
        if self.pick_dict0:
            firstTrace_seg = self.segment_trace_first[segment]
            if newTrace >= firstTrace_seg:
                self.traceNum[segment] -= step
            elif newTrace < firstTrace_seg:
                self.traceNum[segment] = firstTrace_seg

        else:
            if newTrace >= 0:
                self.traceNum[0] -= step
            elif newTrace < 0:
                self.traceNum[0] = 0
            
        self.plot_wv()


    # stepForward is a method to move forward by the number of traces entered to stepSize
    def stepForward(self):
        segment = self.segmentVar.get()
        step = self.stepSize.get()
        newTrace = self.traceNum[segment] + step
        if self.pick_dict0:
            lastTrace_seg = self.segment_trace_last[segment]
            if newTrace <= lastTrace_seg:
                self.traceNum[segment] += step
            # if there are less traces left in the pick segment than the step size, move to the last trace in the segment
            elif newTrace > lastTrace_seg:
                if self.traceNum[segment] == lastTrace_seg:
                    if segment + 2 <= self.num_pkLyrs and tk.messagebox.askokcancel("Next Sement","Finished optimization of current pick segment\n\tProceed to next segment?") == True:
                        self.segmentVar.set(segment + 1) 
                else:
                    self.traceNum[segment] = self.segment_trace_last[segment]
        
        else:
            numTraces = self.num_trace
            if newTrace <= numTraces:
                self.traceNum[0] += step
            elif newTrace > numTraces:
                if self.traceNum[0] == numTraces - 1:
                    return
                else:
                    self.traceNum[0] = numTraces - 1

        self.plot_wv()


    # update_option_menu is a method to update the pick segment menu based on how many segments exist
    def update_option_menu(self):
            menu = self.segmentMenu["menu"]
            menu.delete(0, "end")
            for _i in range(self.num_pkLyrs):
                menu.add_command(label=_i, command=tk._setit(self.segmentVar,_i))
                self.rePick_idx[str(_i)] = []


    # surf_autoPick is a method to automatically optimize surface picks by selecting the maximul amplitude sample within the specified window around existing surf_idx
    def surf_autoPick(self):
        if np.all(np.isnan(self.surf_idx)):
            # if surf idx array is all nans, take max power to define surface 
            max_idx = np.nanargmax(self.data_dB[10:,:], axis = 0) + 10
            # remove outliers
            not_outlier = utils.remove_outliers(max_idx)
            # interpolate over outliers
            x = np.arange(self.num_trace)
            self.surf_idx = np.interp(x, x[not_outlier], max_idx[not_outlier])

        else:
            # if existing surface pick, find max within specified window form existing pick
            winSize = self.winSize.get()
            x = np.argwhere(~np.isnan(self.surf_idx))
            y = self.surf_idx[x]
            for _i in range(len(x)):
                # find argmax for window for given data trace in pick
                max_idx = np.argmax(self.data_dB[int(y[_i] - (winSize/2)):int(y[_i] + (winSize/2)), x[_i]])
                # add argmax index to pick_dict1 - account for window index shift
                self.surf_idx[x[_i]] = max_idx + int(y[_i] - (winSize/2))
        self.plot_wv()


    # subsurf_autoPick is a method to automatically optimize subsurface picks by selecting the maximul amplitude sample within the specified window around existing picks
    def subsurf_autoPick(self):
        if (not self.pick_dict0):
            return
        winSize = self.winSize.get()
        for _i in range(self.num_pkLyrs):
            x = np.where(~np.isnan(self.pick_dict0[str(_i)]))[0]
            y = self.pick_dict0[str(_i)][x]
            for _j in range(len(x)):
                # find argmax for window for given data trace in pick
                max_idx = np.argmax(self.data_dB[int(y[_j] - (winSize/2)):int(y[_j] + (winSize/2)), x[_j]])
                # add argmax index to pick_dict1 - account for window index shift
                self.pick_dict1[str(_i)][x[_j]] = max_idx + int(y[_j] - (winSize/2))
        self.plot_wv()


    # manualPick is a method to manually adjust existing picks by clicking along the displayed waveform
    def manualPick(self, event):
        if (not self.pick_dict0) or (event.inaxes != self.ax):
            return
        segment = self.segmentVar.get()
        # append trace number to rePick_idx list to keep track of indeces for interpolation
        if (len(self.rePick_idx[str(segment)]) == 0) or (self.rePick_idx[str(segment)][-1] != self.traceNum[segment]):
            self.rePick_idx[str(segment)].append(self.traceNum[segment])
        
        self.pick_dict1[str(segment)][self.traceNum[segment]] = int(event.xdata)
        
        self.plot_wv()


    # interpPicks is a method to interpolate between manually refined subsurface picks
    def subsurf_interpPicks(self):
        if (not self.pick_dict0):
            return
        interp = self.subsurf_interpType.get()
        if interp == "linear":
            for _i in range(self.num_pkLyrs):
                if len(self.rePick_idx[str(_i)]) >= 2:
                    # get indices where picks exist for pick segment
                    rePick_idx = self.rePick_idx[str(_i)]
                    # add cubic spline output interpolation to pick dictionary
                    interp_idx = np.arange(rePick_idx[0],rePick_idx[-1] + 1)
                    # get indeces of repicked traces
                    xp = self.rePick_idx[str(_i)]
                    # get twtt values at repicked indices
                    fp = self.pick_dict1[str(_i)][xp]
                    # interpolate repicked values for segment
                    self.pick_dict1[str(_i)][interp_idx] = np.interp(interp_idx, xp, fp)            


        elif interp == "cubic":
            for _i in range(self.num_pkLyrs):
                if len(self.rePick_idx[str(_i)]) >= 2:
                    # cubic spline between picks
                    rePick_idx = self.rePick_idx[str(_i)]
                    cs = CubicSpline(rePick_idx, self.pick_dict1[str(_i)][rePick_idx])
                    # generate array of indices between first and last optimized pick
                    interp_idx = np.arange(rePick_idx[0],rePick_idx[-1] + 1)
                    # add cubic spline output interpolation to pick dictionary
                    self.pick_dict1[str(_i)][interp_idx] = cs([interp_idx]).astype(int)


    # onpress gets the time of the button_press_event
    def onpress(self,event):
        self.time_onclick = time.time()


    # onrelease calls addseg() if the time between the button press and release events
    # is below a threshold so that segments aren't drawn while trying to zoom or pan
    def onrelease(self,event):
        if event.inaxes == self.ax:
            if event.button == 1 and ((time.time() - self.time_onclick) < 0.25):
                self.manualPick(event)


    # clear is a method to clear the wavePick tab and stored data when a new track is loaded
    def clear(self):
        self.ax.clear()
        self.dataCanvas.draw()
        self.set_vars()