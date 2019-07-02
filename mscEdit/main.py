# NOSEpick - currently in development stages
# created by: Brandon S. Tober and Michael S. Christoffersen
# date: 25 JUN 19
# dependencies in requirements.txt

### IMPORTS ###
import sys, scipy, matplotlib
import Ingester
import numpy as np

matplotlib.use("TkAgg")
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

import tkinter as tk
from tkinter import Button, Frame, messagebox, Canvas, filedialog

### USER SPECIFIED VARS ###
in_path = '/home/mchristo/proj/NOSEpick/20180819-215243.mat'

### CODE ###
name = in_path.split('/')[-1].rstrip('.mat')

class NosepickGUI(tk.Tk):
  def __init__(self, master):
    self.master = master
    master.title("NOSEpick")
    self.setup()

  def setup(self):
    # Frames for data display and UI
    self.controls = Frame(self.master)
    self.controls.pack(side="top")
    self.display = Frame(self.master)
    self.display.pack(side="bottom")
    # Button for help message
    self.instButton = Button(self.master, text = "Instructions", command = self.insMsg)
    self.instButton.pack(in_=self.controls, side="left")
    # Button for loading data
    self.loadButton = Button(self.master, text = "Load", command = self.load)
    self.loadButton.pack(in_=self.controls, side="left")
    # Button for exit
    self.exitButton = Button(text = "Exit", fg = "red", command = self.close_window)
    self.exitButton.pack(in_=self.controls, side="left")
    # Blank data canvas
    self.fig = mpl.figure.Figure()
    self.ax = self.fig.add_subplot(111)
    self.dataCanvas = FigureCanvasTkAgg(self.fig, self.master)
    self.dataCanvas.get_tk_widget().pack(in_=self.display, side="bottom", fill="both", expand=1)
    self.dataCanvas.draw()
    # Empty fields for pick
    self.xln = []
    self.yln = []
    self.pick, = self.ax.plot([],[],'r')  # empty line
    # Register click and key events
    self.keye = self.fig.canvas.mpl_connect('key_press_event', self.onkey)
    self.clicke = self.fig.canvas.mpl_connect('button_press_event', self.addseg)

  def load(self):
    # Can be made fancier in the future
    igst = Ingester.Ingester("h5py")
    self.fname = filedialog.askopenfilename(initialdir = "./",title = "Select file",filetypes = (("mat files","*.mat"),("all files","*.*")))
    self.data = igst.read(self.fname)
    self.matplotCanvas()

  def matplotCanvas(self):
    # create matplotlib figure and use imshow to display radargram
    self.ax.imshow(np.log(np.power(self.data['amp'],2)), cmap='gray', aspect='auto', extent=[self.data['dist'][0], self.data['dist'][-1], self.data['amp'].shape[0] * self.data['dt'] * 1e6, 0])
    self.ax.set_title(name)
    self.ax.set(xlabel = 'along-track distance [km]', ylabel = 'two-way travel time [microsec.]')
    # add matplotlib figure nav toolbar
    toolbar = NavigationToolbar2Tk(self.dataCanvas, self.master)
    toolbar.update()
    self.dataCanvas._tkcanvas.pack(side="top", fill="both", expand=1)
    self.dataCanvas.draw()

  def addseg(self, event):
    # add line segments with user input
    if (event.inaxes != self.ax):
      return
    self.xln.append(event.xdata)
    self.yln.append(event.ydata)
    self.pick.set_data(self.xln, self.yln)
    self.fig.canvas.draw()

  def onkey(self, event):
    # on-key commands
    if event.key =='c':
      # clear the drawing of line segments
      if len(self.xln) and len(self.yln) > 0:
        del self.xln[:]
        del self.yln[:]
        self.pick.set_data(self.xln, self.yln)
        self.fig.canvas.draw()
    
    elif event.key =='backspace':
      # remove last segment
      if len(self.xln) and len(self.yln) > 0:
        del self.xln[-1:]
        del self.yln[-1:]
        self.pick.set_data(self.xln, self.yln)
        self.fig.canvas.draw()
    
  def insMsg(self):
    # instructions button message box
    messagebox.showinfo("NOSEpick Instructions", """Nearly Optimal Subsurface Extractor:
    \n\n\u2022Click along reflector surface
    \n\u2022<spacebar> to remove the last pick
    \n\u2022<c> to remove all picks""")

  def close_window(self):
    # destroy canvas upon Exit button click
    self.master.destroy()


root = tk.Tk()
gui = NosepickGUI(root)
root.mainloop()