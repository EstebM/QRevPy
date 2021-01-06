# import datetime
import os
import json
import logging


class RTTtransect(object):
    """
    RTT transect information.  This data is
    retreived from the RTT project file.  The
    transect contains a configuration and a
    file name for the ensembles stored for the
    transect.  The Transect is stored in RTB format.
    """

    VERSION = 1.0

    def __init__(self):
        # Set if this transect is checked to be used or unchecked
        self.Checked = 1

        # List of all files in the transect
        # A transect can contain more than 1 file based on max file size
        """
        {
            'Path': '',             # Full filename of transect including path
            'File': '',             # Filename of transect
            'Number': 0,            # Transect number assigned
        }
        """
        self.Files = []

        # Create Note classes for each file associated with transect
        """
        {
            'NoteFileNo': 0,        # Transect number associated with the note
            'NoteDate': '',         # Date note was entered
            'NoteText': '',         # Text of note
        }
        """
        self.Notes = []

        self.field_config = {
            'Fixed_Commands': [],
            'Wizard_Commands': [],
            'User_Commands': [],
            'Fixed_Commands_RiverQ': [],
            'DS_Use_Process': 0,                # Use Depth Sounder In Processing
            'DS_Transducer_Depth': 0.0,
            'DS_Transducer_Offset': 0.0,
            'DS_Cor_Spd_Sound': 0,              # Depth Sounder Correct Speed of Sound
            'DS_Scale_Factor': 0.0,
            'Ext_Heading_Offset': 0.0,          # External Heading Configuration
            'Ext_Heading_Use': False,           # Use External Heading
            'GPS_Time_Delay': '',
            'Q_Top_Method': 0.0,                # Top Discharge Estimate
            'Q_Bottom_Method': 0.0,             # Bottom Discharge Estimate
            'Q_Power_Curve_Coeff': 0.0,         # Power Curve Coef
            'Q_Cut_Top_Bins': 0.0,              # Cut Top Bins
            'Q_Bins_Above_Sidelobe': 0.0,       # Cut Bins Above Sidelobe
            'Q_Left_Edge_Type': 0.0,            # River Left Edge Type
            'Q_Left_Edge_Coeff': 0.0,           # Left Edge Slope Coeff
            'Q_Right_Edge_Type': 0.0,           # River Right Edge Type
            'Q_Right_Edge_Coeff': 0.0,          # Right Edge Slope Coeff
            'Q_Shore_Pings_Avg': 0.0,           # Shore Pings Avg
            'Edge_Begin_Shore_Distance': 0.0,
            'Edge_Begin_Left_Bank': 1,
            'Edge_End_Shore_Distance': 0.0,
            'Offsets_Transducer_Depth': 0.0,
            'Offsets_Magnetic_Variation': 0.0,
            'Offsets_Heading_Offset': 0.0,
            'Proc_Speed_of_Sound_Correction': 0,
            'Proc_Salinity': 0.0,
            'Proc_Fixed_Speed_Of_Sound': 1500,
            'Proc_Mark_Below_Bottom_Bad': 1,
            'Proc_Screen_Depth': 0,
            'Proc_Use_Weighted_Mean': 0,
            'Proc_Use_Weighted_Mean_Depth': 0,
            'Proc_Absorption': 0.139,
            'Proc_River_Depth_Source': 4,
            'Proc_Use_3_Beam_BT': 1,
            'Proc_Use_3_Beam_WT': 1,
            'Proc_BT_Error_Vel_Threshold': 0.1,
            'Proc_WT_Error_Velocity_Threshold': 10.0,
            'Proc_BT_Up_Vel_Threshold': 10.0,
            'Proc_WT_Up_Vel_Threshold': 10.0,
            'Wiz_Firmware': "",
        }

        self.active_config = {
            'Fixed_Commands': [],
            'Wizard_Commands': [],
            'User_Commands': [],
            'Fixed_Commands_RiverQ': [],
            'DS_Use_Process': 0,                # Use Depth Sounder In Processing
            'DS_Transducer_Depth': 0.0,
            'DS_Transducer_Offset': 0.0,
            'DS_Cor_Spd_Sound': 0,              # Depth Sounder Correct Speed of Sound
            'DS_Scale_Factor': 0.0,
            'Ext_Heading_Offset': 0.0,          # External Heading Configuration
            'Ext_Heading_Use': False,           # Use External Heading
            'GPS_Time_Delay': '',
            'Q_Top_Method': 0.0,                # Top Discharge Estimate
            'Q_Bottom_Method': 0.0,             # Bottom Discharge Estimate
            'Q_Power_Curve_Coeff': 0.0,         # Power Curve Coef
            'Q_Cut_Top_Bins': 0.0,              # Cut Top Bins
            'Q_Bins_Above_Sidelobe': 0.0,       # Cut Bins Above Sidelobe
            'Q_Left_Edge_Type': 0.0,            # River Left Edge Type
            'Q_Left_Edge_Coeff': 0.0,           # Left Edge Slope Coeff
            'Q_Right_Edge_Type': 0.0,           # River Right Edge Type
            'Q_Right_Edge_Coeff': 0.0,          # Right Edge Slope Coeff
            'Q_Shore_Pings_Avg': 0.0,           # Shore Pings Avg
            'Edge_Begin_Shore_Distance': 0.0,
            'Edge_Begin_Left_Bank': 1,
            'Edge_End_Shore_Distance': 0.0,
            'Offsets_Transducer_Depth': 0.0,
            'Offsets_Magnetic_Variation': 0.0,
            'Offsets_Heading_Offset': 0.0,
            'Proc_Speed_of_Sound_Correction': 0,
            'Proc_Salinity': 0.0,
            'Proc_Fixed_Speed_Of_Sound': 1500,
            'Proc_Mark_Below_Bottom_Bad': 1,
            'Proc_Screen_Depth': 0,
            'Proc_Use_Weighted_Mean': 0,
            'Proc_Use_Weighted_Mean_Depth': 0,
            'Proc_Absorption': 0.139,
            'Proc_River_Depth_Source': 4,
            'Proc_Use_3_Beam_BT': 1,
            'Proc_Use_3_Beam_WT': 1,
            'Proc_BT_Error_Vel_Threshold': 0.1,
            'Proc_WT_Error_Velocity_Threshold': 10.0,
            'Proc_BT_Up_Vel_Threshold': 10.0,
            'Proc_WT_Up_Vel_Threshold': 10.0,
            'Wiz_Firmware': "",
        }

        self.moving_bed_type = None

    def add_transect_file(self, file_name: str):
        """
        Add transect files to the list.
        Each transect can contain more than 1 file, based on the file size limit, so the file names is a list.

        :param file_name for the transect.
        """
        # Create a transect dict
        # transect = {
        #    'Path': file_path,
        #    'File': file_name,
        #    'Number': index,
        # }

        # Add the transect to the file
        self.Files.append(file_name)

    def to_dict(self):
        """
        Convert this object to a dictionary.
        This is used to write the data to a
        JSON file.
        """
        transect_json = {
            "Checked": self.Checked,
            "Files": self.Files,
            "Notes": self.Notes,
            "field_config": self.field_config,
            "active_config": self.active_config,
            "moving_bed_type": self.moving_bed_type,
        }

        return transect_json

    def parse_config(self, json_dict):
        """
        Convert the JSON dictionary read from the
        JSON to create a Transect object
        """
        self.Checked = json_dict['Checked']
        self.Files = json_dict['Files']
        self.Notes = json_dict['Notes']
        # self.field_config = json_dict['field_config']
        self.active_config = json_dict['active_config']
        self.moving_bed_type = json_dict['moving_bed_type']


class RTTrowe(object):
    """
    Project file to hold all the configurations, settings and transect information
    for a River project.  The file is in JSON format.  The file extension is RTT
    (Rowe Technologies Transects).

    All the transect files will be stored in the same folder as the project
    file.
    """

    VERSION = 1.0
    FILE_EXTENSION = ".rtt"  # Rowe Technologies Transects

    def __init__(self, project_name: str = ""):
        # QRev Variables
        self.project = {
            'Name': project_name,
            'Version': RTTrowe.VERSION,
            'Locked': None,
        }

        # Site Information
        self.site_info = {
            'ADCPSerialNmb': '',
            'Number': '',
            'Name': '',
            'Description': 1,
            'MeasurementNmb': '',
            'Remarks': '',
            'Water_Temperature': 0.0,
            'Reference': 'BT',
        }

        # Transects
        self.transects = []

        # Moving Bed Transect Tests
        self.mbt_transects = []

        # Discharge Summary
        """
        self.summary = {
            'NONE': {
                'Use': [],
                'Begin_Left': [],
                'FileName': [],
                'LeftEdgeSlopeCoeff': [],
                'RightEdgeSlopeCoeff': [],
                'IsSubSectioned': [],
                'TransectNmb': [],
                'TotalNmbEnsembles': [],
                'TotalBadEnsembles': [],
                'TotalLostEnsembles': [],
                'LargestGapInSecondsLostOrBad': [],
                'StartEnsemble': [],
                'EndEnsemble': [],
                'StartTime': [],
                'EndTime': [],
                'TotalQ': [],
                'TopQ': [],
                'MeasuredQ': [],
                'BottomQ': [],
                'LeftQ': [],
                'RightQ': [],
                'LeftDistance': [],
                'RightDistance': [],
                'Width': [],
                'TotalArea': [],
                'QperArea': [],
                'FlowDirection': [],
                'MaxWaterDepth': [],
                'MeanWaterDepth': [],
                'MaxWaterSpeed': [],
                'MeanRiverVel': [],
                'MeanBoatSpeed': [],
                'MeanBoatCourse': [],
                'PercentGoodBins': [],
                'STDPitch': [],
                'STDRoll': [],
                'MeanAbsPitch': [],
                'MeanAbsRoll': [],
                'MeanGoodLeftEdgeBins': [],
                'MeanGoodRightEdgeBins': [],
                'PowerCurveCoeff': [],
                'DepthRef': [],
                'ADCPTemperature': [],
                'BlankingDistance': [],
                'BinSize': [],
                'BTMode': [],
                'WTMode': [],
                'BTPings': [],
                'WTPings': [],
                'MinNmbSats': [],
                'MaxNmbSats': [],
                'MinHDOP': [],
                'MaxHDOP': [],
            },
            'BT': {
                'Use': [],
                'Begin_Left': [],
                'FileName': [],
                'LeftEdgeSlopeCoeff': [],
                'RightEdgeSlopeCoeff': [],
                'IsSubSectioned': [],
                'TransectNmb': [],
                'TotalNmbEnsembles': [],
                'TotalBadEnsembles': [],
                'TotalLostEnsembles': [],
                'LargestGapInSecondsLostOrBad': [],
                'StartEnsemble': [],
                'EndEnsemble': [],
                'StartTime': [],
                'EndTime': [],
                'TotalQ': [],
                'TopQ': [],
                'MeasuredQ': [],
                'BottomQ': [],
                'LeftQ': [],
                'RightQ': [],
                'LeftDistance': [],
                'RightDistance': [],
                'Width': [],
                'TotalArea': [],
                'QperArea': [],
                'FlowDirection': [],
                'MaxWaterDepth': [],
                'MeanWaterDepth': [],
                'MaxWaterSpeed': [],
                'MeanRiverVel': [],
                'MeanBoatSpeed': [],
                'MeanBoatCourse': [],
                'PercentGoodBins': [],
                'STDPitch': [],
                'STDRoll': [],
                'MeanAbsPitch': [],
                'MeanAbsRoll': [],
                'MeanGoodLeftEdgeBins': [],
                'MeanGoodRightEdgeBins': [],
                'PowerCurveCoeff': [],
                'DepthRef': [],
                'ADCPTemperature': [],
                'BlankingDistance': [],
                'BinSize': [],
                'BTMode': [],
                'WTMode': [],
                'BTPings': [],
                'WTPings': [],
                'MinNmbSats': [],
                'MaxNmbSats': [],
                'MinHDOP': [],
                'MaxHDOP': [],
            },
            'GGA': {
                'Use': [],
                'Begin_Left': [],
                'FileName': [],
                'LeftEdgeSlopeCoeff': [],
                'RightEdgeSlopeCoeff': [],
                'IsSubSectioned': [],
                'TransectNmb': [],
                'TotalNmbEnsembles': [],
                'TotalBadEnsembles': [],
                'TotalLostEnsembles': [],
                'LargestGapInSecondsLostOrBad': [],
                'StartEnsemble': [],
                'EndEnsemble': [],
                'StartTime': [],
                'EndTime': [],
                'TotalQ': [],
                'TopQ': [],
                'MeasuredQ': [],
                'BottomQ': [],
                'LeftQ': [],
                'RightQ': [],
                'LeftDistance': [],
                'RightDistance': [],
                'Width': [],
                'TotalArea': [],
                'QperArea': [],
                'FlowDirection': [],
                'MaxWaterDepth': [],
                'MeanWaterDepth': [],
                'MaxWaterSpeed': [],
                'MeanRiverVel': [],
                'MeanBoatSpeed': [],
                'MeanBoatCourse': [],
                'PercentGoodBins': [],
                'STDPitch': [],
                'STDRoll': [],
                'MeanAbsPitch': [],
                'MeanAbsRoll': [],
                'MeanGoodLeftEdgeBins': [],
                'MeanGoodRightEdgeBins': [],
                'PowerCurveCoeff': [],
                'DepthRef': [],
                'ADCPTemperature': [],
                'BlankingDistance': [],
                'BinSize': [],
                'BTMode': [],
                'WTMode': [],
                'BTPings': [],
                'WTPings': [],
                'MinNmbSats': [],
                'MaxNmbSats': [],
                'MinHDOP': [],
                'MaxHDOP': [],
            },
            'VTG': {
                'Use': [],
                'Begin_Left': [],
                'FileName': [],
                'LeftEdgeSlopeCoeff': [],
                'RightEdgeSlopeCoeff': [],
                'IsSubSectioned': [],
                'TransectNmb': [],
                'TotalNmbEnsembles': [],
                'TotalBadEnsembles': [],
                'TotalLostEnsembles': [],
                'LargestGapInSecondsLostOrBad': [],
                'StartEnsemble': [],
                'EndEnsemble': [],
                'StartTime': [],
                'EndTime': [],
                'TotalQ': [],
                'TopQ': [],
                'MeasuredQ': [],
                'BottomQ': [],
                'LeftQ': [],
                'RightQ': [],
                'LeftDistance': [],
                'RightDistance': [],
                'Width': [],
                'TotalArea': [],
                'QperArea': [],
                'FlowDirection': [],
                'MaxWaterDepth': [],
                'MeanWaterDepth': [],
                'MaxWaterSpeed': [],
                'MeanRiverVel': [],
                'MeanBoatSpeed': [],
                'MeanBoatCourse': [],
                'PercentGoodBins': [],
                'STDPitch': [],
                'STDRoll': [],
                'MeanAbsPitch': [],
                'MeanAbsRoll': [],
                'MeanGoodLeftEdgeBins': [],
                'MeanGoodRightEdgeBins': [],
                'PowerCurveCoeff': [],
                'DepthRef': [],
                'ADCPTemperature': [],
                'BlankingDistance': [],
                'BinSize': [],
                'BTMode': [],
                'WTMode': [],
                'BTPings': [],
                'WTPings': [],
                'MinNmbSats': [],
                'MaxNmbSats': [],
                'MinHDOP': [],
                'MaxHDOP': [],
            }
        }
        """
        # QA_QC
        self.qaqc = {}

        # Folder Path for the project and all the transect files
        self.path = None

    def add_transect(self, transect: RTTtransect):
        """
        Add a transect to the project.
        :param transect Transect object.
        """
        self.transects.append(transect)

    def transect_to_json(self):
        """
        Convert the list of transects to a dictionary
        so the data can be stored in the JSON file.
        """
        transect_json_list = []
        for transect in self.transects:
            transect_json_list.append(transect.to_dict())

        return transect_json_list

    def write_json_file(self):
        """
        Export the data to a JSON file.
        This will create a top level RTI, then put all the
        dictionaries in to the top level.

        :return The file path to file created.
        """
        file_path = os.path.join(self.path, self.project["Name"] + RTTrowe.FILE_EXTENSION)
        project_dict = {
            'RTI': {
                'project': self.project,
                'site_info': self.site_info,
                'transects': self.transect_to_json(),
                # 'summary': self.summary,
                'qaqc': self.qaqc,
            }
        }

        # Create the project path
        if not os.path.exists(self.path):
            os.mkdir(self.path)

        # Create a project file
        with open(file_path, 'w') as outfile:
            json_object = json.dumps(project_dict, indent=4)
            outfile.write(json_object)
            logging.info(json_object)

        return file_path

    def parse_project(self, file_path: str):
        """
        Read in the project file.  The project is a JSON file.
        Read and populate all the dictionaries with the values.
        :param file_path File path to the project file.
        """

        if os.path.exists(file_path):

            # Set just the folder path for the project
            self.path = os.path.dirname(file_path)

            with open(file_path) as infile:
                # Read in the JSON data
                project_json = json.load(infile)

                # Store the JSON data
                self.project = project_json['RTI']['project']
                self.site_info = project_json['RTI']['site_info']
                # self.summary = project_json['RTI']['summary']
                self.qaqc = project_json['RTI']['qaqc']

                # Add all the transects
                for json_transect in project_json['RTI']['transects']:
                    transect = RTTtransect()
                    transect.parse_config(json_transect)
                    self.transects.append(transect)


"""
USE ACTIVE CONFIG

## TransectData ##
Offsets_Transducer_Depth
Proc_River_Depth_Source 0 - 4  DEFAULT: 4
Proc_Use_3_Beam_BT < 0.5

Q_Shore_Pings_Avg       Number of ensembles for left and right bank Q mesaurement

Proc_Salinity

Edge_Begin_Left_Bank
Edge_Begin_Shore_Distance
Edge_End_Shore_Distance
Edge_Begin_Manual_Discharge
Edge_End_Manual_Discharge
Edge_Begin_Method_Distance = No or YES
Edge_End_Method_Distance = NO or YES
Q_Left_Edge_Type - 0 = Triangular, 1 = Rectangular, 2 = Custom
Q_Right_Edge_Type - 0 = Triangular, 1 = Rectangular, 2 = Custom
Q_Top_Method - 0 = Power, 1 = Constant, 2 = 3-Point
Q_Bottom_Method - 0 = Power, 2 = No Slip
Q_Power_Curve_Coeff

Q_Shore_Left_Ens_Count              Meausre Q for edges
Q_Shore_Right_Ens_Count

Offsets_Magnetic_Variation
Ext_Heading_Offset
Ext_Heading_Use

ADCPSerialNmb

Fixed_Commands 
or
Wizard_Commands
or
User_Commands

## InstrumentData ##
site_info
active_config

ADCPSerialNmb
Fixed
Fixed_Commands
Wizard
Wizard_Commands
User
User_Commands


## Transect ##
Notes
NoteFileNo
NoteText
NoteDate

## QAQC ##
RG_Test
RG_Test_TimeStamp
Compass_Calibration
Compass_Calibration_TimeStamp
Compass_Evaluation
Compass_Evaluation_TimeStamp


[DS_Use_Process]
# Set depth reference to value from mmt file
if 'Proc_River_Depth_Source' in mmt_config:
 ...
else:
    if mmt_config['DS_Use_Process'] > 0:
        if self.depths.ds_depths is not None:
            self.depths.selected = 'ds_depths'
        else:
            self.depths.selected = 'bt_depths'
    else:
        self.depths.selected = 'bt_depths'
        
        


"""