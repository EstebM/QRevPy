import os
import datetime as datetime
from PyQt5 import QtWidgets
from Classes.stickysettings import StickySettings as SSet
from UI import wSelectFile


class OpenMeasurementDialog(QtWidgets.QDialog, wSelectFile.Ui_selectFile):
    """Dialog to allow users to select measurement files for processing.

    Parameters
    ----------
    wSelectFile.Ui_selectFile : QDialog
        Dialog window with options for users

    Attributes
    ----------
    settings: dict
        Dictionary used to store user defined settings.
    fullName: list
        Full name of files including path.
    fileName: list
        List of one or more fileNames to be processed.
    pathName: str
        Path to folder containing files.
    type: str
        Type of file (SonTek, TRDI, QRev).
    checked: bool
        Switch for TRDI files (True: load only checked, False: load all).
    """

    def __init__(self, parent=None):
        """Initializes settings and connections.

        Parameters
        ----------
        parent
            Identifies parent GUI.
        """

        super(OpenMeasurementDialog, self).__init__(parent)
        self.setupUi(self)

        # Create settings object which contains the default folder
        self.settings = SSet(parent.settingsFile)

        # Create connections for buttons
        self.pbSonTek.clicked.connect(self.select_sontek)
        self.pbTRDI.clicked.connect(self.select_trdi)
        self.pbQRev.clicked.connect(self.select_qrev)
        self.pbCancel.clicked.connect(self.cancel)

        # Initialize parameters
        self.fullName = []
        self.fileName = []
        self.pathName = []
        self.type = ''
        self.checked = False

    def default_folder(self):
        """Returns default folder.

        Returns the folder stored in settings or if no folder is stored, then the current
        working folder is returned.
        """
        try:
            folder = self.settings.get('Folder')
            if not folder:
                folder = os.getcwd()
        except KeyError:
            self.settings.new('Folder', os.getcwd())
            folder = self.settings.get('Folder')
        return folder

    def process_names(self):
        """Parses fullnames into filenames and pathnames and sets default folder.
        """
        # Parse filenames and pathname from fullName
        if isinstance(self.fullName, str):
            self.pathName, self.fileName = os.path.split(self.fullName)
        else:
            self.fileName = []
            for file in self.fullName:
                self.pathName, fileTemp = os.path.split(file)
                self.fileName.append(fileTemp)

        # Update the folder setting
        self.settings.set('Folder', self.pathName)

    def select_sontek(self):
        """Get filenames and pathname for SonTek Matlab transect files

        Allows the user to select one or more SonTek Matlab transect files for
        processing. The selected folder becomes the default folder for subsequent
        selectFile requests.
        """

        # Get the current folder setting.
        folder = self.default_folder()

        # Get the full names (path + file) of the selected files
        self.fullName = QtWidgets.QFileDialog.getOpenFileNames(
                    self, self.tr('Open File'), folder,
                    self.tr('SonTek Matlab File (*.mat)'))[0]

        # Initialize parameters
        self.type = ''
        self.checked = False

        # Process fullName if selection was made
        if self.fullName:
            self.process_names()
            self.type = 'SonTek'
        self.close()

    def select_trdi(self):
        """Get filenames and pathname for TRDI mmt file

        Allows the user to select a TRDI mmt file for processing.
        The selected folder becomes the default folder for subsequent
        selectFile requests.
        """

        # Get the current folder setting.
        folder = self.default_folder()

        # Get the full names (path + file) of the selected files
        self.fullName = QtWidgets.QFileDialog.getOpenFileNames(
                    self, self.tr('Open File'), folder,
                    self.tr('TRDI mmt File (*.mmt)'))[0]

        # Initialize parameters
        self.type = ''
        self.checked = self.cbTRDI.isChecked()

        # Process fullName if selection was made
        if self.fullName:
            self.type = 'TRDI'
            self.process_names()
        self.close()

    def select_qrev(self):
        """Get filename and pathname of QRev file.

                Allows the user to select a QRev file for viewing or reprocessing.
                The selected folder becomes the default folder for subsequent
                selectFile requests.
                """

        # Get the current folder setting.
        folder = self.default_folder()

        # Get the full names (path + file) of the selected file
        self.fullName = QtWidgets.QFileDialog.getOpenFileName(
            self, self.tr('Open File'), folder,
            self.tr('QRev File (*_QRev.mat)'))[0]

        # Initialize parameters
        self.type = ''
        self.checked = False

        # Process fullName if selection was made
        if self.fullName:
            self.type = 'QRev'
            self.process_names()
        self.close()

    def cancel(self):
        """Close dialog.
        """
        self.type = ''
        self.close()


class SaveMeasurementDialog(QtWidgets.QDialog):
    """Dialog to allow users to select measurement files for processing.

        Parameters
        ----------
        wSelectFile.Ui_selectFile : QDialog
            Dialog window with options for users

        Attributes
        ----------
        full_Name: str
            Filename with path to save file.
    """

    def __init__(self, parent=None):
        """Initializes settings and connections.

        Parameters
        ----------
        parent
            Identifies parent GUI.
        """
        super(SaveMeasurementDialog, self).__init__(parent)
        # self.setupUi(self)

        # Create settings object which contains the default folder
        settings = SSet(parent.settingsFile)

        # Get the current folder setting.
        folder = self.default_folder(settings)
        version = str(int(round(float(parent.QRev_version[-4:]) * 100)))
        # Create default file name
        file_name = os.path.join(folder, datetime.datetime.today().strftime('%Y%m%d_%H%M%S_' + version + '_QRev.mat'))
        # Get the full names (path + file) of the selected file
        self.full_Name = QtWidgets.QFileDialog.getSaveFileName(
            self, self.tr('Save File'), file_name,
            self.tr('QRev File (*_QRev.mat)'))[0]
        if len(self.full_Name) > 0:
            if self.full_Name[-4:] != '.mat':
                self.full_Name = self.full_Name + '.mat'

    @staticmethod
    def default_folder(settings):
        """Returns default folder.

        Returns the folder stored in settings or if no folder is stored, then the current
        working folder is returned.
        """
        try:
            folder = settings.get('Folder')
            if not folder:
                folder = os.getcwd()
        except KeyError:
            settings.new('Folder', os.getcwd())
            folder = settings.get('Folder')
        return folder
