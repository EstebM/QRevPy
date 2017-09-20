import numpy as np
from numpy.matlib import repmat
import os
from Classes.Pd0TRDI import Pd0TRDI
from Classes.DepthStructure import DepthStructure
from Classes.DepthData import DepthData
from MiscLibs.convenience import cosd, arctand, tand
from Classes.WaterData import WaterData
from Classes.BoatStructure import BoatStructure
from Classes.GPSData import GPSData
from Classes.Edges import Edges
from Classes.ExtrapData import ExtrapData
from Classes.Sensors import Sensors
from bokeh.plotting.tests.test_figure import source

class TransectData(object):
    """Class to hold Transect properties (may be removed on a refactor)
        Analogous to matlab class: clsTransectData
    """

    def __init__(self):
        self.adcp = None            # object of clsInstrument
        self.file_name = None      # filename of transect data file
        self.w_vel = None           # object of clsWaterData
        self.boat_vel = None        # class for various boat velocity references
                                    # (btVel, ggaVel, vtgVel)
        self.gps = None             # object of clsGPSData
        self.sensors = None         # object of clsSensorData
        self.depths = None      # object of clsDepthStructure for depth data including cell depths & ref depths
                                    # (btDepths, vbDepths, dsDepths)
        self.edges = None           # object of clsEdges
                                    # (left and right object of clsEdgeData)
        self.extrap = None          # object of clsExtrapData
        self.start_edge = None      # starting edge of transect looking downstream (Left or Right)
        self.datetime = None
        self.checked = None         #transect was checked for use in mmt file assumed checked for SonTek
        self.in_transect_idx = None # index of ensemble data associated with the moving-boat portion of the transect
        self.active_config = None
        self.transects = None
        self.cells_above_sl = None

    def get_data(self, source, in_file, pd0_data, file_idx):
        
        if source == 'TRDI':
            self.TRDI(in_file, pd0_data, file_idx)
            
                                #files2load idx
    def TRDI(self, mmt_transect, pd0_data, file_idx, args=None):
       
       
        pd0 = pd0_data
        
        #get the configuration prooperty of the mmt_transect
        mmt_config = getattr(mmt_transect, self.active_config)
        if pd0_data.Wt is not None:
            
            #Get and compute ensemble beam depths
            temp_depth = np.array(pd0.Bt.depth_m)
            #Screen out invalid depths
            temp_depth[temp_depth<0.01] = np.nan
            #Add draft
            temp_depth += mmt_config['Offsets_Transducer_Depth']
            
            #Get instrument cell data
            cell_size_all_m, cell_depth_m, sl_cutoff_per, sl_lag_effect = self.compute_instrument_cell_data(pd0)
            
            #Adjust cell depth of draft 
            cell_depth_m = np.add(mmt_config['Offsets_Transducer_Depth'], cell_depth_m)
            
            #create depth data object for BT
            self.depths = DepthStructure()
            self.depths.add_depth_object(temp_depth, 'BT', pd0.Inst.freq, 
                                   mmt_config['Offsets_Transducer_Depth'], 
                                   kargs = [cell_depth_m, cell_size_all_m])
            
            #compute cells above side lobe
            self.side_lobe_cutoff(self.depths.bt_depths.depth_orig_m, 
                                                     self.depths.bt_depths.draft_orig_m, 
                                                     self.depths.bt_depths.depth_cell_depth_m,
                                                     sl_lag_effect,
                                                    kargs = ['Percent', 
                                                    1-sl_cutoff_per / 100])
            
            #Check for the presence of vertical beam data
            if np.nanmax(np.nanmax(pd0.Sensor.vert_beam_status)) > 0:
                
                temp_depth = pd0.Sensor.vert_beam_range_m
                
                #Screen out invalid depths
                temp_depth[temp_depth<0.01] = np.nan
                
                #Add draft
                temp_depth = temp_depth + mmt_config['Offsets_Transducer_Depth']
                
                #Create depth data object for vertical beam
                self.depths.add_depth_object(temp_depth, 'VB', pd0.Inst.freq, 
                                   mmt_config['Offsets_Transducer_Depth'],
                                   kargs = [cell_depth_m, cell_size_all_m])
                                   
            #check for the presence of depth sounder
            if np.nansum(np.nansum(pd0.Gps2.depth_m)) > 1e-5:
                temp_depth = pd0.Gps2.depth_m
                
                #Screen out invalid data
                temp_depth[temp_depth < 0.01] = np.nan
                
                #Use the last valid depth for each ensemble
                last_depth_col_idx = np.sum(np.isnan(temp_depth) == False, axis=1)-1
                last_depth_col_idx[last_depth_col_idx == -1] = 0               
                row_index = np.arange(len(temp_depth))
                last_depth=np.empty(row_index.size)
                #? DEBUG to check correctness
                for row in row_index:
                    last_depth[row]=temp_depth[row,last_depth_col_idx[row]]               
#                    idx = np.ravel_multi_index(temp_depth, dims=(temp_depth.shape[0], temp_depth.shape[1], last_depth_col_idx), order='C')
#                last_depth = temp_depth[idx]
                
                #Determine if mmt file has a scale factor and offset for the depth sounder
                if mmt_config['DS_Cor_Spd_Sound'] == 0:
                    scale_factor = mmt_config['DS_Scale_Factor']
                else:
                    scale_factor = pd0.sensors.sos_mps /  1500
                    
                #Apply scvale factor, offset. and draft
                #Note: Only the ADCP draft is stored.  The transducer
                # draft or scaling for depth sounder data cannot be changed in QRev
                ds_depth = (last_depth * scale_factor) 
                + mmt_config['DS_Transducer_Depth']
                + mmt_config['DS_Transducer_Offset']
                
                self.depths.add_depth_object(ds_depth, 'DS', pd0.Inst.freq, 
                                   mmt_config['Offsets_Transducer_Depth'],
                                   kargs = [cell_depth_m, cell_size_all_m])
                
            #Set depth reference to value from mmt file
            if 'Proc_River_Depth_Source' in mmt_config:
                if mmt_config['Proc_River_Depth_Source'] == 0:
                    self.depths.set_depth_reference('BT')
                elif mmt_config['Proc_River_Depth_Source'] == 1:
                    if self.depths.ds_depths is not None:
                        self.depths.set_depth_reference('DS')
                    else:
                        self.depths.set_depth_reference('BT')
                elif mmt_config['Proc_River_Depth_Source'] == 2:
                    self.depths.set_depth_reference('VB')
                elif mmt_config['Proc_River_Depth_Source'] == 3:
                    if self.depths.vb_depths is None:
                        self.depths.set_depth_reference('BT')
                    else:
                        self.depths.set_depth_reference('VB')
                    self.depths.composite_depths(self, kargs=['On'])
                elif mmt_config['Proc_River_Depth_Source'] == 4:
                    if self.depth.bt_depths is None:
                        self.depths.set_depth_reference('VB')
                    else:
                        self.depths.set_depth_reference('BT')
                    self.depths.composite_depths(self, kargs=['On'])
                else:
                    self.depths.set_depth_reference('BT')
                    self.depths.composite_depths(self, kargs=['On'])  
            else:
                if mmt_config['DS_Use_Process'] > 0:
                    if self.depth.ds_depths  is not None:
                        self.depths.set_depth_reference('DS')
                    else:
                        self.depths.set_depth_reference('BT')
                else:
                    self.depths.set_depth_reference('BT')
                self.depths.composite_depths(self, kargs = ['Off'])
                
            #Create water_data object -----------------------------
            
            # Check for RiverRay and RiverPro data
            firmware = str(pd0.Inst.firm_ver[0])
            excluded_dist = 0
            if firmware[:2] == '56' and np.nanmean(pd0.Inst.beams) < 5:
                excluded_dist = 0.25
                
            if firmware[:2] == '44' or firmware[:2] == '56':
                
                #Process water velocities for RiverRay and RiverPro
                self.w_vel = WaterData()
                self.w_vel.populate_data(pd0.Wt.vel_mps, 
                                         pd0.Inst.freq.T, 
                                         pd0.Cfg.coord_sys, 
                                         'None', 
                                         pd0.Wt.rssi, 
                                         'Counts', 
                                         excluded_dist, 
                                         self.cells_above_sl, 
                                         sl_cutoff_per, 
                                         0,
                                         'Percent', 
                                         sl_lag_effect, 
                                         pd0.Cfg.wm[0], 
                                         pd0.Cfg.wf_cm[0] / 100, 
                                         kargs=[pd0.Wt.corr,
                                                pd0.Surface.vel_mps,
                                                pd0.Surface.rssi,
                                                pd0.Surface.corr,
                                                pd0.Surface.no_cells])
                
            else:
                #Process water velocities for non-RiverRay ADCPs
                self.w_vel = WaterData()
                self.w_vel.populate_data(pd0.Wt.vel_mps, 
                                         pd0.Inst.freq.T, 
                                         pd0.Cfg.coord_sys, 
                                         'None', 
                                         pd0.Wt.rssi, 
                                         'Counts', 
                                         excluded_dist, 
                                         self.cells_above_sl, 
                                         sl_cutoff_per, 
                                         0,
                                         'Percent', 
                                         sl_lag_effect, 
                                         pd0.Cfg.wm[0], 
                                         pd0.Cfg.wf_cm[0] / 100, 
                                         kargs=[pd0.Wt.corr])
                
            #Initialize boat vel
            self.boat_vel = BoatStructure()
            
            self.boat_vel.add_boat_object('TRDI', pd0.Bt.vel_mps, pd0.Inst.freq.T, 
                                            pd0.Cfg.coord_sys[0], mmt_config['Proc_Use_3_Beam_Solution_For_BT'],
                                            pd0.Cfg.bm[0])
            
            self.boat_vel.set_nav_reference('BT')
            
            #Compute velocities from GPS Data
            #------------------------------------
            
            #Raw Data
            raw_GGA_utc = pd0.Gps2.utc
            raw_GGA_lat = pd0.Gps2.lat_deg
            
            #Determine correct sign for latitude
            idx = np.where(pd0.Gps2.lat_ref == 'S')
            if len(idx) > 0:
                raw_GGA_lat[idx] = raw_GGA_lat[idx]  * -1
            raw_GGA_lon = pd0.Gps2.lon_deg
            
            #Determine correct sign for longitude
            idx = np.where(pd0.Gps2.lon_ref=='W')
            if len(idx) > 0:
                raw_GGA_lon[idx] = raw_GGA_lon[idx] * -1
            
            #Assign data to local variables
            raw_GGA_alt = pd0.Gps2.alt
            raw_GGA_diff = pd0.Gps2.corr_qual
            raw_GGA_hdop = pd0.Gps2.hdop
            raw_GGA_num_sats = pd0.Gps2.num_sats
            raw_VTG_course = pd0.Gps2.course_true
            raw_VTG_speed = pd0.Gps2.speed_k_mph * 0.2777778
            raw_VTG_delta_time = pd0.Gps2.vtg_delta_time
            raw_VTG_mode_indicator = pd0.Gps2.mode_indicator
            raw_GGA_delta_time = pd0.Gps2.gga_delta_time
            
            # RSL provided ensemble values, not supported for TRDI data
            ext_GGA_utc=[];
            ext_GGA_lat=[];
            ext_GGA_lon=[];
            ext_GGA_alt=[];
            ext_GGA_diff=[];
            ext_GGA_hdop=[];
            ext_GGA_num_sats=[];
            ext_VTG_course=[];
            ext_VTG_speed=[];
             
            #QRev methods GPS processing methods
            GGA_p_method = 'Mindt'
            GGA_v_method = 'Mindt'
            VTG_method = 'Mindt'
            
            #If valid gps data exist, process the data
            if np.sum(np.sum(np.isnan(raw_GGA_lat)==False)) > 0 or np.sum(np.sum(np.isnan(raw_VTG_speed) == False)) > 0:
                
                #Process raw GPS data
                self.gps = GPSData()
                self.gps.populate_data(raw_GGA_utc, raw_GGA_lat, raw_GGA_lon, raw_GGA_alt, raw_GGA_diff, raw_GGA_hdop, 
                                       raw_GGA_num_sats, raw_GGA_delta_time, raw_VTG_course, raw_VTG_speed, 
                                       raw_VTG_delta_time, raw_VTG_mode_indicator, ext_GGA_utc, ext_GGA_lat, ext_GGA_lon, 
                                       ext_GGA_alt, ext_GGA_diff, ext_GGA_hdop, ext_GGA_num_sats, ext_VTG_course, 
                                       ext_VTG_speed, GGA_p_method, GGA_v_method, VTG_method)
                
                #If valid GGA data exists create GGA boat velocity object
                if np.sum(np.sum(np.isnan(raw_GGA_lat) == False)) > 0:
                    self.boat_vel.add_boat_object('TRDI', self.gps.gga_velocity_ens_mps, np.nan, 'Earth', 'GGA')
                    
                    
                #If valid vtg data exist create VTG boat velocity object
                if np.sum(np.sum(np.isnan(raw_VTG_speed) == False)) > 0:
                    self.boat_vel.add_boat_object('TRDI', self.gps.gga_velocity_ens_mps, np.nan, 'Earth', 'GGA' 
                                                  ,[np.nan,np.nan])
                    
                    
            #Create Edges Object
            self.edges = Edges()
            self.edges.populate_data('Fixed','MeasMag')
                
            #Determine number of ensembles to average
            nens_L = mmt_config['Q_Shore_Pings_Avg']
            #TRDI uses same number on left and right edges
            nens_R = nens_L
            
            #Set indices for ensembles in the moving-boat
            #portion of the transect
            self.in_transect_idx = np.arange(0,pd0.Bt.vel_mps.shape[1])
            
            #Determine left and right edge distances
            if mmt_config['Edge_Begin_Left_Bank'] == True:
                dist_L = mmt_config['Edge_Begin_Shore_Distance']
                dist_R = mmt_config['Edge_End_Shore_Distance']
                self.start_edge = 'Left'
            else:
                dist_L = mmt_config['Edge_End_Shore_Distance']
                dist_R = mmt_config['Edge_Begin_Shore_Distance']
                self.start_edge = 'Right'
                
            #Create edge
            if mmt_config['Q_Left_Edge_Type'] == 0:
                self.edges.create_edge('left', 'Triangular', dist_L, kargs=[nens_L])
            elif mmt_config['Q_Left_Edge_Type'] == 1:
                self.edges.create_edge('left', 'Rectangular', dist_L, kargs=[nens_L])
            elif mmt_config['Q_Left_Edge_Type'] == 2:
                coefficient = mmt_config['Q_Left_Edge_Coeff']
                self.edges.create_edge('left', 'custom', dist_L, kargs=[coefficient, nens_L])
                
            #Create edge
            if mmt_config['Q_Right_Edge_Type'] == 0:
                self.edges.create_edge('right', 'Triangular', dist_R, kargs=[nens_R])
            elif mmt_config['Q_Right_Edge_Type'] == 1:
                self.edges.create_edge('right', 'Rectangular', dist_L, kargs=[nens_L])
            elif mmt_config['Q_Right_Edge_Type'] == 2:
                coefficient = mmt_config['Q_Right_Edge_Coeff']
                self.edges.create_edge('right', 'custom', dist_L, kargs=[coefficient, nens_L])
                
            #Create extrap object
            if mmt_config['Q_Top_Method'] == 0:
                top = 'Power'
            elif mmt_config['Q_Top_Method'] == 1:
                top = 'Constant'
            elif mmt_config['Q_Top_Method'] == 2:
                top = '3-Point'
                
            #Determine bottom method
            if mmt_config['Q_Bottom_Method'] == 0:
                bot = 'Power'
            elif mmt_config['Q_Bottom_Method'] == 2:
                bot = 'No Slip'
                
            self.extrap = ExtrapData()
            self.extrap.populate_data(top, bot, mmt_config['Q_Power_Curve_Coeff']) 
            
            #Sensor Data
            
            self.sensors = Sensors() 
            
            #Heading
            
            #Internal Heading
            heading = pd0.Sensor.heading_deg.T
            heading_src = pd0.Cfg.head_src[0]
            
            #WR2 only has one set of magvar and heading offset
            magvar = mmt_config['Offsets_Magnetic_Variation']
            heading_offset = mmt_config['Ext_Heading_Offset']
            
            #Create internal heading sensor
            self.sensors.add_sensor_data('heading_deg', 'internal', heading, heading_src, kargs=[magvar, heading_offset])
            
            #External Heading
            ext_heading_check = np.where(np.isnan(pd0.Gps2.heading_deg))
            if len(ext_heading_check[0]) <= 0:
                
                self.sensors.set_selected('heading_deg', 'internal')
            else:
                #Determine external heading for each ensemble
                #Using the minimum time difference
                d_time = np.abs(pd0.Gps2.hdt_delta_time)
                d_time_min = np.nanmin(d_time.T, 0).T
                use = np.tile([np.nan], d_time.shape)
                for nd_time in range(len(d_time_min)):
                    use[nd_time,:] = np.abs(d_time[nd_time,:]) == d_time_min[nd_time]
                    
                ext_heading_deg = np.tile([np.nan], (1, len(d_time_min)))
                for nh in range(len(d_time_min)):
                    idx = np.where(use[nh:]) 
                    if len(idx[0]) > 0:
                        ext_heading_deg[nh] = pd0.Gps2.heading_deg[nh, idx]
                        
                #Create external heading sensor
                self.sensors.add_sensor_data('heading_deg', 'external', ext_heading_deg, magvar, kargs=[heading_offset])
            
                #Determine heading source to use from mmt setting
                source_used = mmt_config['Ext_Heading_Use']
                if source_used == True:
                    self.sensors.set_selected('heading_deg', 'external')
                else:
                    self.sensors.set_selected('heading_deg', 'internal')
                
            
            #Pitch
            pitch = arctand(tand(pd0.Sensor.pitch_deg) * cosd(pd0.Sensor.roll_deg))
            pitch_src = pd0.Cfg.pitch_src[0]
            
            #Create pitch sensor
            self.sensors.add_sensor_data('pitch_deg', 'internal', pitch, pitch_src)
            self.sensors.set_selected('pitch_deg', 'internal')
            
            #Roll
            roll = pd0.Sensor.roll_deg.T
            roll_src = pd0.Cfg.roll_src[0]
            
            #Create Roll sensor
            self.sensors.add_sensor_data('roll_deg', 'internal', roll, roll_src)
            self.sensors.set_selected('roll_deg', 'internal')
            
            #Temperature
            temperature = pd0.Sensor.temperature_deg_c.T
            temperature_src = pd0.Cfg.temp_src[0]
            
            #Create temperature sensor
            self.sensors.add_sensor_data('temperature_deg_c', 'internal', temperature, temperature_src)
            self.sensors.set_selected('temperature_deg_c', 'internal')
            
            #Salinity
            pd0_salinity = pd0.Sensor.salinity_ppt.T
            pd0_salinity_src = pd0.Cfg.sal_src[0]
            
            #Create salinity sensor
            self.sensors.add_sensor_data('salinity_ppt', 'internal', pd0_salinity, pd0_salinity_src)
            mmt_salinity = mmt_config['Proc_Salinity']
            
            
            
                             
            
            
            
                

    def compute_instrument_cell_data(self, pd0):
        
        #Number of ensembles
        num_ens = np.array(pd0.Wt.vel_mps).shape[-1]
        #Retrieve and compute cell information
        reg_cell_size = pd0.Cfg.ws_cm / 100
        reg_cell_size[reg_cell_size == 0] = np.nan
        dist_cell_m = pd0.Cfg.dist_bin1_cm / 100
        num_reg_cells = pd0.Wt.vel_mps.shape[1]
        
        #surf data are to accommodate RiverRay and RiverPro.  pd0_read sets these
        #values to nan when reading Rio Grande or StreamPro data
        
        no_surf_cells = pd0.Surface.no_cells
        no_surf_cells[np.isnan(no_surf_cells)] = 0
        max_surf_cells = np.nanmax(no_surf_cells)
        surf_cell_size = pd0.Surface.cell_size_cm / 100
        surf_cell_dist = pd0.Surface.dist_bin1_cm / 100
        
        # Compute maximum number of cells
        max_cells = int(max_surf_cells+num_reg_cells)
        
        # Combine cell size and cell range from transducer for both
        # surface and regular cells
        
        cell_depth = repmat([np.nan], max_cells, num_ens)
        cell_size_all = repmat([np.nan], max_cells, num_ens)
        
        for i in range(num_ens):
            
            #Determine number of cells to be treated as regular cells
            if np.nanmax(no_surf_cells) > 0:
                
                num_reg_cells = max_cells - no_surf_cells[i]
            else:
                num_reg_cells = max_cells
                
                
            #Surface cell are present
            if no_surf_cells[i] > 1e-5:
                cell_depth[:int(no_surf_cells[i]),i] = surf_cell_dist[i] + np.arange(0,(no_surf_cells[i] - 1)*surf_cell_size[i]+.001,surf_cell_size[i])
                cell_depth[int(no_surf_cells[i]):,i] = cell_depth[int(no_surf_cells[i]),i] \
                + (.5*surf_cell_size[i]+0.5*reg_cell_size[i]) \
                + np.arange(0, (num_reg_cells-1)*reg_cell_size[i]+0.001, reg_cell_size[i])
                cell_size_all[0:int(no_surf_cells[i]),i] = np.repeat(surf_cell_size[i],int(no_surf_cells[i]))
                cell_size_all[int(no_surf_cells[i]):,i] = np.repeat(reg_cell_size[i],int(num_reg_cells))
            else:
                
                cell_depth[:int(num_reg_cells),i] = dist_cell_m[i] + np.arange(0,(num_reg_cells)*reg_cell_size[i],reg_cell_size[i])
                cell_size_all[:,i] = np.repeat(reg_cell_size[i], num_reg_cells)
                
                
            #Firmware is used to ID RiverRay data with variable modes and lags
            firmware = str(pd0.Inst.firm_ver[0])
            
        #Compute sl_lag_effect
        lag = pd0.Cfg.lag_cm / 100
        if firmware[0:2] == '44' or firmware[0:2] == '56':
            lag_near_bottom = np.array(pd0.Cfg.lag_near_bottom)
            lag_near_bottom[lag_near_bottom == np.nan] = 0
            lag[lag_near_bottom != 0] = 0
            
        pulse_len = pd0.Cfg.xmit_pulse_cm / 100
        sl_lag_effect_m = (lag + pulse_len + reg_cell_size) / 2
        sl_cutoff_per = (1-(cosd(pd0.Inst.beam_ang[0]))) * 100
            
        return (cell_size_all, cell_depth, sl_cutoff_per, sl_lag_effect_m)
        
        
    def side_lobe_cutoff(self, depths, draft, cell_depth, sl_lag_effect, kargs):
        '''Computes side lobe vutoff based on beam angle with no allowance for lag'''
        
        #Compute minimum depths for each ensemble
        min_depths = np.nanmin(depths,0)
        
        #Compute range from transducer
        range_from_xducer = min_depths - draft
        
        #Adjust fro transducter angle
        if kargs[0] == 'Percent':
            coeff = kargs[1]
        elif kargs[0] == 'Angle':
            coeff = cosd(kargs[1])
        
        #Compute sidelobe cutoff to centerline    
        cutoff = np.array(range_from_xducer * coeff - sl_lag_effect+draft)
        
        #Compute logical side lobe cutoff matrix
        self.cells_above_sl = (cell_depth - cutoff) < 0
        
        
        
                
    
            
            
          
           
                
            
        
            
            
        
        
            
        
                
        


