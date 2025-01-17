import numpy as np


class GPSFilters (object):
    """Class to generate time series plots of the selected filter data.

    Attributes
    ----------
    canvas: MplCanvas
        Object of MplCanvas a FigureCanvas
    fig: Object
        Figure object of the canvas
    units: dict
        Dictionary of units conversions
    qual: object
        Axis of figure for number of beams
    alt: object
        Axis of figure for error velocity
    hdop: object
        Axis of figure for vertical velocity
    other: object
        Axis of figure for other filters
    sats: object
        Axis of figure for number of satellites
    source: object
        Axis of figure for navigation reference source
    hover_connection: int
        Index to data cursor connection
    annot: Annotation
        Annotation object for data cursor
    """

    def __init__(self, canvas):
        """Initialize object using the specified canvas.

        Parameters
        ----------
        canvas: MplCanvas
            Object of MplCanvas
        """

        # Initialize attributes
        self.canvas = canvas
        self.fig = canvas.fig
        self.units = None
        self.qual = None
        self.alt = None
        self.hdop = None
        self.other = None
        self. sats = None
        self.source = None
        self.hover_connection = None
        self.annot = None

    def create(self, transect, units, selected):
        """Create the axes and lines for the figure.

        Parameters
        ----------
        transect: TransectData
            Object of TransectData containing boat speeds to be plotted
        units: dict
            Dictionary of units conversions
        selected: str
            String identifying the type of plot
        """

        # Assign and save parameters
        self.units = units

        # Clear the plot
        self.fig.clear()

        # Configure axis
        self.fig.ax = self.fig.add_subplot(1, 1, 1)

        # Set margins and padding for figure
        self.fig.subplots_adjust(left=0.1, bottom=0.2, right=0.98, top=0.98, wspace=0.1, hspace=0)
        self.fig.ax.set_xlabel(self.canvas.tr('Ensembles'))
        self.fig.ax.grid()
        self.fig.ax.xaxis.label.set_fontsize(12)
        self.fig.ax.yaxis.label.set_fontsize(12)
        self.fig.ax.tick_params(axis='both', direction='in', bottom=True, top=True, left=True, right=True)

        if transect.boat_vel.gga_vel is not None:
            ensembles = np.arange(1, len(transect.boat_vel.gga_vel.u_mps) + 1)
        elif transect.boat_vel.vtg_vel is not None:
            ensembles = np.arange(1, len(transect.boat_vel.vtg_vel.u_mps) + 1)
        else:
            ensembles = np.arange(1, len(transect.boat_vel.bt_vel.u_mps) + 1)

        if selected == 'quality' and transect.boat_vel.gga_vel is not None:
            # GPS Quality
            self.qual = self.fig.ax.plot(ensembles, transect.gps.diff_qual_ens, 'b.')

            # Circle invalid data
            invalid_gps = np.logical_not(transect.boat_vel.gga_vel.valid_data[2, :])
            self.qual.append(self.fig.ax.plot(ensembles[invalid_gps],
                                              transect.gps.diff_qual_ens[invalid_gps], 'ro', markerfacecolor='none')[0])

            # Format axis
            self.fig.ax.set_ylabel(self.canvas.tr('GPS Quality'))
            yint = range(0, int(np.ceil(np.nanmax(transect.gps.diff_qual_ens)) + 1))
            self.fig.ax.set_ylim(top=np.nanmax(yint) + 0.5, bottom=np.nanmin(yint) - 0.5)
            self.fig.ax.set_yticks(yint)

        elif selected == 'altitude' and transect.boat_vel.gga_vel is not None:
            # Plot altitude
            invalid_altitude = np.logical_not(transect.boat_vel.gga_vel.valid_data[3, :])
            self.alt = self.fig.ax.plot(ensembles, transect.gps.altitude_ens_m * units['L'], 'b.')
            self.alt.append(self.fig.ax.plot(ensembles[invalid_altitude],
                                             transect.gps.altitude_ens_m[invalid_altitude] * units['L'],
                                             'ro', markerfacecolor='none')[0])
            self.fig.ax.set_ylabel(self.canvas.tr('Altitude' + self.units['label_L']))

        elif selected == 'hdop' and transect.boat_vel.gga_vel is not None:
            # Plot HDOP
            max_y = np.nanmax(transect.gps.hdop_ens) + 0.5
            min_y = np.nanmin(transect.gps.hdop_ens) - 0.5
            invalid_hdop = np.logical_not(transect.boat_vel.gga_vel.valid_data[5, :])
            self.hdop = self.fig.ax.plot(ensembles, transect.gps.hdop_ens, 'b.')
            self.hdop.append(self.fig.ax.plot(ensembles[invalid_hdop],
                                              transect.gps.hdop_ens[invalid_hdop],
                                              'ro', markerfacecolor='none')[0])
            self.fig.ax.set_ylim(top=max_y, bottom=min_y)
            self.fig.ax.set_ylabel(self.canvas.tr('HDOP'))

        elif selected == 'sats' and transect.boat_vel.gga_vel is not None:
            # Plot number of satellites
            max_y = np.nanmax(transect.gps.num_sats_ens) + 0.5
            min_y = np.nanmin(transect.gps.num_sats_ens) - 0.5
            self.sats = self.fig.ax.plot(ensembles, transect.gps.num_sats_ens, 'b.')
            try:
                self.fig.ax.set_ylim(top=max_y, bottom=min_y)
                yint = range(int(min_y), int(max_y) + 1)
                self.fig.ax.set_yticks(yint)
            except ValueError:
                pass
            self.fig.ax.set_ylabel(self.canvas.tr('Number of Satellites'))

        elif selected == 'other':

            # Select an object to use for the smooth
            if transect.boat_vel.selected == 'gga_vel':
                boat_gps = transect.boat_vel.gga_vel
                data_color = ['b-', 'b.']
            elif transect.boat_vel.selected == 'vtg_vel':
                boat_gps = transect.boat_vel.vtg_vel
                data_color = ['g-', 'g.']
            elif transect.boat_vel.vtg_vel is not None:
                boat_gps = transect.boat_vel.vtg_vel
                data_color = ['g-', 'g.']
            else:
                boat_gps = transect.boat_vel.gga_vel
                data_color = ['b-', 'b.']

            if boat_gps is not None:
                # Plot smooth
                speed = np.sqrt(boat_gps.u_mps ** 2
                                + boat_gps.v_mps ** 2)

                if boat_gps.smooth_filter == 'On':
                    invalid_other_vel = np.logical_not(boat_gps.valid_data[4, :])
                    self.other = self.fig.ax.plot(ensembles,
                                                  boat_gps.smooth_lower_limit * self.units['V'],
                                                  color='#d5dce6')
                    self.other.append(self.fig.ax.plot(ensembles,
                                                       boat_gps.smooth_upper_limit * self.units['V'],
                                                       color='#d5dce6')[0])
                    self.other.append(self.fig.ax.fill_between(ensembles,
                                                               boat_gps.smooth_lower_limit
                                                               * self.units['V'],
                                                               boat_gps.smooth_upper_limit
                                                               * self.units['V'],
                                                               facecolor='#d5dce6'))

                    self.other.append(self.fig.ax.plot(ensembles, speed * units['V'], data_color[0])[0])
                    self.other.append(self.fig.ax.plot(ensembles,
                                                       boat_gps.smooth_speed * self.units['V'])[0])
                    self.other.append(self.fig.ax.plot(ensembles[invalid_other_vel],
                                                       speed[invalid_other_vel] * units['V'],
                                                       'ko', linestyle='')[0])
                else:
                    self.other = self.fig.ax.plot(ensembles, speed * units['V'], data_color[1])
                self.fig.ax.set_ylabel(self.canvas.tr('Speed' + units['label_V']))

        elif selected == 'source':
            # Plot boat velocity source
            if transect.boat_vel.selected == 'gga_vel':
                boat_selected = transect.boat_vel.gga_vel
            elif transect.boat_vel.selected == 'vtg_vel':
                boat_selected = transect.boat_vel.vtg_vel
            else:
                boat_selected = transect.boat_vel.bt_vel

            # Handle situation where transect does not contain the selected source
            if boat_selected is None:
                source = np.tile('INV', len(ensembles))
            else:
                source = boat_selected.processed_source

            # Plot dummy data to establish consistent order of y axis
            self.source = self.fig.ax.plot([-10, -10, -10, -10, -10], ['INV', 'INT', 'BT', 'GGA', 'VTG'], 'w-')
            self.source = self.fig.ax.plot(ensembles, source, 'b.')
            self.fig.ax.set_ylabel(self.canvas.tr('Boat Velocity Source'))
            self.fig.ax.set_yticks(['INV', 'INT', 'BT', 'GGA', 'VTG'])

        self.fig.ax.set_xlim(left=-1 * ensembles[-1] * 0.02, right=ensembles[-1] * 1.02)

        if transect.start_edge == 'Right':
            self.fig.ax.invert_xaxis()
            self.fig.ax.set_xlim(right=-1 * ensembles[-1] * 0.02, left=ensembles[-1] * 1.02)

        # Initialize annotation for data cursor
        self.annot = self.fig.ax.annotate("", xy=(0, 0), xytext=(-20, 20), textcoords="offset points",
                                          bbox=dict(boxstyle="round", fc="w"),
                                          arrowprops=dict(arrowstyle="->"))

        self.annot.set_visible(False)

        self.canvas.draw()

    def update_annot(self, ind, plt_ref):
        """Updates the location and text and makes visible the previously initialized and hidden annotation.

        Parameters
        ----------
        ind: dict
            Contains data selected.
        plt_ref: Line2D
            Reference containing plotted data
        """

        pos = plt_ref._xy[ind["ind"][0]]

        # Shift annotation box left or right depending on which half of the axis the pos x is located and the
        # direction of x increasing.
        if plt_ref.axes.viewLim.intervalx[0] < plt_ref.axes.viewLim.intervalx[1]:
            if pos[0] < (plt_ref.axes.viewLim.intervalx[0] + plt_ref.axes.viewLim.intervalx[1]) / 2:
                self.annot._x = -20
            else:
                self.annot._x = -80
        else:
            if pos[0] < (plt_ref.axes.viewLim.intervalx[0] + plt_ref.axes.viewLim.intervalx[1]) / 2:
                self.annot._x = -80
            else:
                self.annot._x = -20

        # Shift annotation box up or down depending on which half of the axis the pos y is located and the
        # direction of y increasing.
        if plt_ref.axes.viewLim.intervaly[0] < plt_ref.axes.viewLim.intervaly[1]:
            if pos[1] > (plt_ref.axes.viewLim.intervaly[0] + plt_ref.axes.viewLim.intervaly[1]) / 2:
                self.annot._y = -40
            else:
                self.annot._y = 20
        else:
            if pos[1] > (plt_ref.axes.viewLim.intervaly[0] + plt_ref.axes.viewLim.intervaly[1]) / 2:
                self.annot._y = 20
            else:
                self.annot._y = -40

        # Format and display text
        self.annot.xy = pos
        text = 'x: {:.2f}, y: {:.2f}'.format(pos[0], pos[1])
        self.annot.set_text(text)

    def hover(self, event):
        """Determines if the user has selected a location with data and makes
        annotation visible and calls method to update the text of the annotation. If the
        location is not valid the existing annotation is hidden.

        Parameters
        ----------
        event: MouseEvent
            Triggered when mouse button is pressed.
        """

        # Set annotation to visible
        vis = self.annot.get_visible()

        # Determine if mouse location references a data point in the plot and update the annotation.
        if event.inaxes == self.fig.ax:
            cont_qual = False
            cont_hdop = False
            cont_alt = False
            cont_sats = False
            cont_other = False
            ind_qual = None
            ind_hdop = None
            ind_alt = None
            ind_sats = None
            ind_other = None
            if self.qual is not None:
                cont_qual, ind_qual = self.qual[0].contains(event)
            elif self.hdop is not None:
                cont_hdop, ind_hdop = self.hdop[0].contains(event)
            elif self.alt is not None:
                cont_alt, ind_alt = self.alt[0].contains(event)
            elif self.sats is not None:
                cont_sats, ind_sats = self.sats[0].contains(event)
            elif self.other is not None:
                cont_other, ind_other = self.other[0].contains(event)

            if cont_qual:
                self.update_annot(ind_qual, self.qual[0])
                self.annot.set_visible(True)
                self.canvas.draw_idle()
            elif cont_hdop:
                self.update_annot(ind_hdop, self.hdop[0])
                self.annot.set_visible(True)
                self.canvas.draw_idle()
            elif cont_alt:
                self.update_annot(ind_alt, self.alt[0])
                self.annot.set_visible(True)
                self.canvas.draw_idle()
            elif cont_sats:
                self.update_annot(ind_sats, self.sats[0])
                self.annot.set_visible(True)
                self.canvas.draw_idle()
            elif cont_other:
                self.update_annot(ind_other, self.other[0])
                self.annot.set_visible(True)
                self.canvas.draw_idle()
            else:
                # If the cursor location is not associated with the plotted data hide the annotation.
                if vis:
                    self.annot.set_visible(False)
                    self.canvas.draw_idle()

    def set_hover_connection(self, setting):
        """Turns the connection to the mouse event on or off.

        Parameters
        ----------
        setting: bool
            Boolean to specify whether the connection for the mouse event is active or not.
        """

        if setting and self.hover_connection is None:
            self.hover_connection = self.canvas.mpl_connect('button_press_event', self.hover)
        elif not setting:
            self.canvas.mpl_disconnect(self.hover_connection)
            self.hover_connection = None
            self.annot.set_visible(False)
            self.canvas.draw_idle()
