import os
import re
import logging
import numpy as np
import struct
import binascii
import math
from MiscLibs.common_functions import nans


class RtbRowe(object):
    """
    Class to read data from RTB files

    Single file to read in RTB data, then create an list of objects.  The lists will contain all the
    data from the file.

    This file was specifically created to work in QRevPy to decode RTI data and follow QRevPy's data format.
    """

    # Prevent Magic Numbers
    HEADER_SIZE = 32                    # Header size in bytes
    CHECKSUM_SIZE = 4                   # Checksum size in bytes
    MAX_DATASETS = 20                   # Maximum number of datasets in an ensemble
    BYTES_INT32 = 4                  # Bytes in Int32
    BYTES_FLOAT = 4                  # Bytes in Float
    NUM_DATASET_HEADER_ELEMENTS = 6     # Number of elements in dataset header
    BAD_VEL = 88.888                    # RTB Bad Velocity

    def __init__(self, file_path: str):
        """
        Constructor initializing instance variables.

        :param file_path: Full Path of RTB file to be read

        """

        # File path
        self.file_name = file_path

        # Count the number of ensembles in the file to initialize the np.array
        self.num_ens, self.num_beams, self.num_bins = self.get_file_info(file_path=file_path)

        # List of all the ensemble data decoded
        # Instrument Specific data
        self.Inst = Inst(num_ens=self.num_ens)

        # ADCP Configuration values
        self.Cfg = Cfg(num_ens=self.num_ens)

        # ADCP Sensors like temp and compass
        self.Sensor = Sensor(num_ens=self.num_ens)

        # Water velocity data and quality
        self.Wt = Wt(num_ens=self.num_ens,
                     num_beams=self.num_beams,
                     num_bins=self.num_bins)

        # Range Tracking Data
        self.Rt = RT(num_ens=self.num_ens,
                     num_beams=self.num_beams)

        # Bottom Track Data
        self.Bt = BT(num_ens=self.num_ens,
                     num_beams=self.num_beams)

        # NMEA data
        self.Nmea = Nmea(num_ens=self.num_ens)

        # Water Gage Data
        self.Gage = Gage(num_ens=self.num_ens)

        self.Gps = Gps(num_ens=self.num_ens)

        self.Gps2 = Gps2(num_ens=self.num_ens)

        # Surface velocity data
        self.Surface = Surface(num_ens=self.num_ens,
                               num_beams=self.num_beams,
                               max_surface_bins=0)          # TODO: NOT USED RIGHT NOW
        self.AutoMode = []

        # River Bottom Track data
        self.River_BT = RiverBT(num_ens=self.num_ens,
                                num_subsystems=10)          # TODO: NOT SET CORRECTLY, NEED TO READ IN IN CHECK

        # Keep track of ensemble index
        # This is used only for 3 or 4 beam ensembles
        # Vertical beams are merged with 3 or 4 beam ensemble
        self.ens_index = 0

        # Read in the given file path
        self.rtb_read(file_path=file_path)

    @staticmethod
    def count_ensembles(file_path: str):
        """
        Get the file information like the number of ensembles in the file.
        """
        # RTB ensemble delimiter
        delimiter = b'\x80' * 16

        # Block size to read in data
        # BLOCK_SIZE = 4096
        block_size = 4096

        # Keep count of the number of ensembles found
        ens_count = 0

        # Search for the number of ensembles by looking for the delimiter
        # Check to ensure file exists
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                data = f.read(block_size)  # Read in data

                # Verify data was found
                while data:
                    # Check for the delimiter
                    if delimiter in data:
                        ens_count += 1

                    # Read the next batch of data
                    data = f.read(block_size)

        return ens_count

    def get_file_info(self, file_path: str):
        """
        Get the file information like the number of ensembles,
        number of beams and number of bins.
        This only counts 3 or 4 beam ensembles.  Vertical beams
        will be merged with 4 beam ensembles.

        :param file_path File path to inspect.
        :return NumEnsembles, NumBeams, NumBins
        """
        # RTB ensemble delimiter
        delimiter = b'\x80' * 16

        # Block size to read in data
        block_size = 4096

        # Create a buffer
        buff = bytes()

        # Keep count of the number of ensembles found
        ens_count = 0
        num_beams = 0
        num_bins = 0

        # Search for the number of ensembles by looking for the delimiter
        # Check to ensure file exists
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                data = f.read(block_size)  # Read in data

                # Verify data was found
                while data:
                    # Accumulate the buffer
                    buff += data

                    # Check for the delimiter
                    if delimiter in buff:
                        # If delimiter found, split at the delimiter to get the remaining buffer data
                        chunks = buff.split(delimiter)

                        # Put the remaining data back in the buffer
                        buff = chunks.pop()

                        # Take out the ens data
                        for chunk in chunks:
                            # Process the binary ensemble data
                            # Verify the ENS data is good
                            # This will check that all the data is there and the checksum is good
                            if self.verify_ens_data(delimiter + chunk):
                                # Get the ensemble info
                                bin_count, beams_count = self.get_ens_info(delimiter + chunk)

                                # Verify we have 3 or 4 beam data ensemble
                                # Vertical beam is not counted and is merged with 4 beam ensembles
                                if beams_count > 2:
                                    ens_count += 1

                                    # Set the largest beam and bin number
                                    num_beams = max(beams_count, num_beams)
                                    num_bins = max(bin_count, num_bins)

                    # Read the next batch of data
                    data = f.read(block_size)

            # Process whatever is remaining in the buffer
            # Verify the ENS data is good
            # This will check that all the data is there and the checksum is good
            if self.verify_ens_data(delimiter + buff):
                # Get the ensemble info
                bin_count, beams_count = self.get_ens_info(delimiter + buff)

                # Verify we have 3 or 4 beam data ensemble
                # Vertical beam is not counted and is merged with 4 beam ensembles
                if beams_count > 2:
                    ens_count += 1

                    # Set the largest beam and bin number
                    num_beams = max(beams_count, num_beams)
                    num_bins = max(bin_count, num_bins)

        return ens_count, num_beams, num_bins

    def get_ens_info(self, ens_bytes: list):
        """
        Decode the datasets to an ensemble to get the general information about the ensemble.
        This includes the number of beams and bins.
        Use verify_ens_data if you are using this
        as a static method to verify the data is correct.
        :param ens_bytes: Ensemble binary data.  Decode the dataset.
        :return: Return number of beam and number of bins.
        """

        packet_pointer = self.HEADER_SIZE
        ens_len = len(ens_bytes)

        num_elements = 0
        element_multiplier = 0

        # Decode the ensemble datasets
        # Limit the number of attempts to look for new datasets
        for x in range(self.MAX_DATASETS):
            # Check if we are at the end of the payload
            if packet_pointer >= ens_len - RtbRowe.CHECKSUM_SIZE - RtbRowe.HEADER_SIZE:
                break

            # Get the dataset info
            # ds_type = RtbRowe.get_int32(packet_pointer + (RtbRowe.BYTES_INT32 * 0), RtbRowe.BYTES_INT32, ens_bytes)
            num_elements = RtbRowe.get_int32(packet_pointer + (RtbRowe.BYTES_INT32 * 1), RtbRowe.BYTES_INT32, ens_bytes)
            element_multiplier = RtbRowe.get_int32(packet_pointer + (RtbRowe.BYTES_INT32 * 2), RtbRowe.BYTES_INT32,
                                                   ens_bytes)
            # image = RtbRowe.get_int32(packet_pointer + (RtbRowe.BYTES_INT32 * 3), RtbRowe.BYTES_INT32, ens_bytes)
            # name_len = RtbRowe.get_int32(packet_pointer + (RtbRowe.BYTES_INT32 * 4), RtbRowe.BYTES_INT32, ens_bytes)
            name = str(ens_bytes[packet_pointer +
                                 (RtbRowe.BYTES_INT32 * 5):packet_pointer + (RtbRowe.BYTES_INT32 * 5) + 8], 'UTF-8')

            # Beam velocity will contain all the information we need
            if "E000001" in name:
                # Ensure this is not vertical beam data
                if element_multiplier > 1:
                    # Return the number bins and number of beams
                    return num_elements, element_multiplier

        return num_elements, element_multiplier

    def rtb_read(self, file_path: str):
        """
        Reads the binary RTB file and assigns values to object instance variables.
        :param file_path: Full file path

        """

        # RTB ensemble delimiter
        # DELIMITER = b'\x80' * 16
        delimiter = b'\x80' * 16

        # Block size to read in data
        block_size = 4096

        # Get the total file size to keep track of total bytes read and show progress
        # file_size = os.path.getsize(file_path)
        bytes_read = 0

        # Create a buffer
        buff = bytes()

        # Assign default values
        # n_velocities = 4
        # max_surface_bins = 5

        # Check to ensure file exists
        if os.path.exists(file_path):
            # file_info = os.path.getsize(file_path)

            with open(file_path, "rb") as f:
                data = f.read(block_size)  # Read in data

                # Keep track of bytes read
                # bytes_read += block_size
                # self.file_progress(bytes_read, file_size, fullname)

                # Verify data was found
                while data:
                    # Accumulate the buffer
                    buff += data

                    # Check for the delimiter
                    if delimiter in buff:
                        # If delimiter found, split at the delimiter to get the remaining buffer data
                        chunks = buff.split(delimiter)

                        # Put the remaining data back in the buffer
                        buff = chunks.pop()

                        # Take out the ens data
                        for chunk in chunks:
                            # Process the binary ensemble data
                            self.decode_ens(delimiter + chunk)

                    # Read the next batch of data
                    data = f.read(block_size)

                    # Keep track of bytes read
                    bytes_read += block_size
                    # self.file_progress(bytes_read, file_size, ens_file_path)
                    # self.file_progress(block_size, file_size, fullname)

            # Process whatever is remaining in the buffer
            self.decode_ens(delimiter + buff)

        # self.Gps2.corr_qual = np.array(self.Gps2.corr_qual)
        # self.Gps2.lat_deg = np.array(self.Gps2.lat_deg)

    def decode_ens(self, ens_bytes: list):
        """
        Attempt to decode the ensemble.  This will verify the checksum passes.
        If the checksum is good, then decode the data.
        When the data is decoded, automatically add it to list of ensembles.
        :param ens_bytes: Ensemble byte array to decode.
        :return
        """

        # Verify the ENS data is good
        # This will check that all the data is there and the checksum is good
        if self.verify_ens_data(ens_bytes):
            # Decode the ens binary data
            logging.debug("Decoding binary data to ensemble: " + str(len(ens_bytes)))

            # Decode the data
            self.decode_data_sets(ens_bytes)

    def verify_ens_data(self, ens_bytes: list, ens_start: int = 0):
        """
        Get the ensemble number and the ensemble size.  Verify
        we have all the ensemble bytes in the buffer by comparing aginst
        the ensemble size.  Then check the checksum and verify it is correct.
        :param ens_bytes: Ensemble binary data.
        :param ens_start: Start location in the ens_data
        :return True if the ensemble is good and checksum passes.
        """
        try:
            # Ensemble Length
            ens_len = len(ens_bytes)

            # Verify at least the minimum number of bytes are available to verify the ensemble
            if ens_len <= self.HEADER_SIZE + self.CHECKSUM_SIZE:
                return False

            # Check Ensemble number
            ens_num = struct.unpack("I", ens_bytes[ens_start + 16:ens_start + 20])

            # Check ensemble size
            payload_size = struct.unpack("I", ens_bytes[ens_start + 24:ens_start + 28])

            # Ensure the entire ensemble is in the buffer
            if ens_len >= ens_start + self.HEADER_SIZE + payload_size[0] + self.CHECKSUM_SIZE:

                # Check checksum
                checksum_loc = ens_start + self.HEADER_SIZE + payload_size[0]
                checksum = struct.unpack("I", ens_bytes[checksum_loc:checksum_loc + self.CHECKSUM_SIZE])

                # Calculate Checksum
                # Use only the payload for the checksum
                ens = ens_bytes[ens_start + self.HEADER_SIZE:ens_start + self.HEADER_SIZE + payload_size[0]]
                calc_checksum = binascii.crc_hqx(ens, 0)

                # Verify checksum
                if checksum[0] == calc_checksum:
                    logging.debug(ens_num[0])
                    return True
                else:
                    logging.warning("Ensemble fails checksum. {:#04x} {:#04x}".format(checksum[0], calc_checksum))
                    return False
            else:
                logging.warning("Incomplete ensemble.")
                return False

        except Exception as e:
            logging.error("Error verifying Ensemble.  " + str(e))
            return False

        # return False

    def decode_data_sets(self, ens_bytes: list):
        """
        Decode the datasets to an ensemble.
        Use verify_ens_data if you are using this
        as a static method to verify the data is correct.
        :param ens_bytes: Ensemble binary data.  Decode the dataset.
        :return: Return the decoded ensemble.
        """
        packet_pointer = self.HEADER_SIZE
        ens_len = len(ens_bytes)

        # Flag if BT data found
        # bt_data_found = False
        # bt_adcp3_data_found = False
        # ancillary_adcp3_found = False

        # Flag if this ensemble is vertical beam ensemble
        is_vert_ens = False

        # Decode the ensemble datasets
        # Limit the number of attempts to look for new datasets
        for x in range(self.MAX_DATASETS):
            # Check if we are at the end of the payload
            if packet_pointer >= ens_len - RtbRowe.CHECKSUM_SIZE - RtbRowe.HEADER_SIZE:
                break

            # Get the dataset info
            ds_type = RtbRowe.get_int32(packet_pointer + (RtbRowe.BYTES_INT32 * 0), RtbRowe.BYTES_INT32, ens_bytes)
            num_elements = RtbRowe.get_int32(packet_pointer + (RtbRowe.BYTES_INT32 * 1), RtbRowe.BYTES_INT32, ens_bytes)
            element_multiplier = RtbRowe.get_int32(packet_pointer + (RtbRowe.BYTES_INT32 * 2), RtbRowe.BYTES_INT32,
                                                   ens_bytes)
            # image = RtbRowe.get_int32(packet_pointer + (RtbRowe.BYTES_INT32 * 3), RtbRowe.BYTES_INT32, ens_bytes)
            name_len = RtbRowe.get_int32(packet_pointer + (RtbRowe.BYTES_INT32 * 4), RtbRowe.BYTES_INT32, ens_bytes)
            name = str(ens_bytes[packet_pointer
                                 + (RtbRowe.BYTES_INT32 * 5):packet_pointer + (RtbRowe.BYTES_INT32 * 5) + 8], 'UTF-8')

            # Calculate the dataset size
            data_set_size = RtbRowe.get_data_set_size(ds_type, name_len, num_elements, element_multiplier)

            # Beam Velocity
            if "E000001" in name:
                logging.debug(name)

                # Test if this ensemble is a vertical beam
                if element_multiplier == 1:
                    is_vert_ens = True
                    # Do nothing else for vertical beam
                else:
                    self.Wt.decode_vel(ens_bytes=ens_bytes[packet_pointer:packet_pointer + data_set_size],
                                       ens_index=self.ens_index,
                                       num_elements=num_elements,
                                       element_multiplier=element_multiplier,
                                       name_len=name_len)

            # Instrument Velocity
            if "E000002" in name:
                logging.debug(name)
                # Test if this ensemble is a vertical beam
                if element_multiplier == 1:
                    is_vert_ens = True
                    # Do nothing else for vertical beam
                else:
                    self.Wt.decode_instr_vel(ens_bytes=ens_bytes[packet_pointer:packet_pointer + data_set_size],
                                             ens_index=self.ens_index,
                                             num_elements=num_elements,
                                             element_multiplier=element_multiplier,
                                             name_len=name_len)

            # Earth Velocity
            if "E000003" in name:
                logging.debug(name)
                # Test if this ensemble is a vertical beam
                if element_multiplier == 1:
                    is_vert_ens = True
                    # Do nothing else for vertical beam
                else:
                    self.Wt.decode_earth_vel(ens_bytes=ens_bytes[packet_pointer:packet_pointer + data_set_size],
                                             ens_index=self.ens_index,
                                             num_elements=num_elements,
                                             element_multiplier=element_multiplier,
                                             name_len=name_len)

            # Amplitude
            if "E000004" in name:
                logging.debug(name)

                # Check for vertical beam data
                if element_multiplier == 1:
                    is_vert_ens = True
                    # Do nothing else for vertical beam
                else:
                    self.Wt.decode_rssi(ens_bytes=ens_bytes[packet_pointer:packet_pointer+data_set_size],
                                        ens_index=self.ens_index,
                                        num_elements=num_elements,
                                        element_multiplier=element_multiplier,
                                        name_len=name_len)

            # Correlation
            if "E000005" in name:
                logging.debug(name)

                # num_repeats = None
                # if (len(self.Cfg.wp_repeat_n) > self.ens_index-1 > 0 and
                #         not np.isnan(self.Cfg.wp_repeat_n[self.ens_index-1])):
                #    num_repeats = self.Cfg.wp_repeat_n[self.ens_index-1]

                # Check for vertical beam data
                if element_multiplier < 2:
                    is_vert_ens = True
                    # Do nothing else for vertical beam
                else:
                    self.Wt.decode_corr(ens_bytes=ens_bytes[packet_pointer:packet_pointer+data_set_size],
                                        ens_index=self.ens_index,
                                        num_elements=num_elements,
                                        element_multiplier=element_multiplier,
                                        # num_repeats=num_repeats,
                                        name_len=name_len)

            # Good Beam
            if "E000006" in name:
                logging.debug(name)

                # Get the number of pings used in the ensemble
                # pings_per_ens = 1
                # if len(self.Cfg.wp) > self.ens_index-1 > 0 and not np.isnan(self.Cfg.wp[self.ens_index-1]):
                #    pings_per_ens = self.Cfg.wp[self.ens_index-1]

                # Check if vertical beam data
                if element_multiplier < 2:
                    is_vert_ens = True
                    # Do nothing else for vertical beam
                else:
                    self.Wt.decode_pgb(ens_bytes=ens_bytes[packet_pointer:packet_pointer+data_set_size],
                                       ens_index=self.ens_index,
                                       num_elements=num_elements,
                                       element_multiplier=element_multiplier,
                                       # pings_per_ens=pings_per_ens,
                                       name_len=name_len)

            # Good Earth
            if "E000007" in name:
                logging.debug(name)

                # Get the number of pings used in the ensemble
                # pings_per_ens = 1
                # if len(self.Cfg.wp) > self.ens_index-1 > 0 and not np.isnan(self.Cfg.wp[self.ens_index-1]):
                #    pings_per_ens = self.Cfg.wp[self.ens_index-1]

                # Test if this ensemble is a vertical beam
                if element_multiplier < 2:
                    is_vert_ens = True
                    # Do nothing else for vertical beam
                else:
                    self.Wt.decode_pg_earth(ens_bytes=ens_bytes[packet_pointer:packet_pointer+data_set_size],
                                            ens_index=self.ens_index,
                                            num_elements=num_elements,
                                            element_multiplier=element_multiplier,
                                            # pings_per_ens=pings_per_ens,
                                            name_len=name_len)

            # Ensemble Data
            if "E000008" in name:
                logging.debug(name)

                # This should have already been flagged if the data is vertical
                # from the velocity, amplitude or correlation data
                # If it is vertical beam data, do not add the data
                if not is_vert_ens:
                    self.Cfg.decode_ensemble_data(ens_bytes=ens_bytes[packet_pointer:packet_pointer+data_set_size],
                                                  ens_index=self.ens_index,
                                                  name_len=name_len)

                    self.Inst.decode_ensemble_data(ens_bytes=ens_bytes[packet_pointer:packet_pointer+data_set_size],
                                                   ens_index=self.ens_index,
                                                   name_len=name_len)

                    self.Sensor.decode_ensemble_data(ens_bytes=ens_bytes[packet_pointer:packet_pointer+data_set_size],
                                                     ens_index=self.ens_index,
                                                     name_len=name_len)

            # Ancillary Data
            if "E000009" in name:
                logging.debug(name)

                # This should have already been flagged if the data is vertical
                # from the velocity, amplitude or correlation data
                # If it is vertical beam data, do not add the data
                if not is_vert_ens:

                    # Configuration data
                    self.Cfg.decode_ancillary_data(ens_bytes=ens_bytes[packet_pointer:packet_pointer+data_set_size],
                                                   ens_index=self.ens_index,
                                                   name_len=name_len)

                    # Sensor data
                    self.Sensor.decode_ancillary_data(ens_bytes=ens_bytes[packet_pointer:packet_pointer+data_set_size],
                                                      ens_index=self.ens_index,
                                                      name_len=name_len)

                    # New ADCP3 Hardware includes this data
                    # There are additional values at the end
                    if num_elements > 19:
                        self.Sensor.decode_ancillary_adcp3_data(
                                            ens_bytes=ens_bytes[packet_pointer:packet_pointer+data_set_size],
                                            ens_index=self.ens_index,
                                            name_len=name_len)

                        self.Cfg.decode_ancillary_adcp3_data(
                                            ens_bytes=ens_bytes[packet_pointer:packet_pointer+data_set_size],
                                            ens_index=self.ens_index,
                                            name_len=name_len)

            # Bottom Track
            if "E000010" in name:
                logging.debug(name)

                # This should have already been flagged if the data is vertical
                # from the velocity, amplitude or correlation data
                # If it is vertical beam data, do not add the data
                if not is_vert_ens:
                    # Populate Bottom Track data
                    self.Bt.decode(ens_bytes=ens_bytes[packet_pointer:packet_pointer+data_set_size],
                                   ens_index=self.ens_index,
                                   name_len=name_len)

                    # Populate Config data
                    self.Cfg.decode_bottom_track_data(ens_bytes=ens_bytes[packet_pointer:packet_pointer+data_set_size],
                                                      ens_index=self.ens_index,
                                                      name_len=name_len)

                    # Populate Sensor data
                    self.Sensor.decode_bottom_track_data(
                        ens_bytes=ens_bytes[packet_pointer:packet_pointer+data_set_size],
                        ens_index=self.ens_index,
                        name_len=name_len)

                    # Check if ADCP 3 data is available
                    # Number of elements.  74 for 4 Beam system, 59 for 3 beam, 29 for 1 beam
                    if num_elements > 74:
                        self.Sensor.decode_bottom_track_adcp3_data(
                            ens_bytes=ens_bytes[packet_pointer:packet_pointer+data_set_size],
                            ens_index=self.ens_index,
                            name_len=name_len)

            # NMEA data
            if "E000011" in name:
                logging.debug(name)

                # This should have already been flagged if the data is vertical
                # from the velocity, amplitude or correlation data
                # If it is vertical beam data, do not add the data
                if not is_vert_ens:
                    self.Nmea.decode(ens_bytes=ens_bytes[packet_pointer:packet_pointer+data_set_size],
                                     ens_index=self.ens_index,
                                     name_len=name_len)

                    self.Gps2.decode(ens_bytes=ens_bytes[packet_pointer:packet_pointer + data_set_size],
                                     ens_index=self.ens_index,
                                     # num_ens=self.num_ens,
                                     name_len=name_len)

                    self.Gps.decode(ens_bytes=ens_bytes[packet_pointer:packet_pointer + data_set_size],
                                    ens_index=self.ens_index,
                                    # num_ens=self.num_ens,
                                    name_len=name_len)

            # System Setup
            if "E000014" in name:
                logging.debug(name)

                # This should have already been flagged if the data is vertical
                # from the velocity, amplitude or correlation data
                # If it is vertical beam data, do not add the data
                if not is_vert_ens:
                    # Configuration data
                    # Check if the Cfg is already created from other dataset
                    self.Cfg.decode_systemsetup_data(ens_bytes=ens_bytes[packet_pointer:packet_pointer + data_set_size],
                                                     ens_index=self.ens_index,
                                                     name_len=name_len)

                    self.Sensor.decode_systemsetup_data(
                        ens_bytes=ens_bytes[packet_pointer:packet_pointer + data_set_size],
                        ens_index=self.ens_index,
                        name_len=name_len)

                    self.Inst.decode_systemsetup_data(
                        ens_bytes=ens_bytes[packet_pointer:packet_pointer + data_set_size],
                        ens_index=self.ens_index,
                        name_len=name_len)

            # Range Tracking
            if "E000015" in name:
                logging.debug(name)

                # This should have already been flagged if the data is vertical
                # from the velocity, amplitude or correlation data
                # If it is vertical beam data, do not add the data
                if is_vert_ens:
                    # Vertical beam data
                    # Add the vertical beam data to the previous ensemble
                    if self.ens_index-1 >= 0:
                        self.Sensor.decode_vert_rt(ens_bytes=ens_bytes[packet_pointer:packet_pointer + data_set_size],
                                                   ens_index=self.ens_index-1,
                                                   name_len=name_len)
                else:
                    self.Rt.decode(ens_bytes=ens_bytes[packet_pointer:packet_pointer + data_set_size],
                                   ens_index=self.ens_index,
                                   name_len=name_len)

            if "E000016" in name:
                logging.debug(name)
                # This should have already been flagged if the data is vertical
                # from the velocity, amplitude or correlation data
                # If it is vertical beam data, do not add the data
                if not is_vert_ens:
                    self.Gage.decode_data(ens_bytes=ens_bytes[packet_pointer:packet_pointer + data_set_size],
                                          ens_index=self.ens_index,
                                          name_len=name_len)

            if "R000001" in name:
                logging.debug(name)
                # This should have already been flagged if the data is vertical
                # from the velocity, amplitude or correlation data
                # If it is vertical beam data, do not add the data
                if not is_vert_ens:
                    self.River_BT.decode_data(ens_bytes=ens_bytes[packet_pointer:packet_pointer + data_set_size],
                                              ens_index=self.ens_index,
                                              name_len=name_len)

            if "R000002" in name:
                logging.debug(name)
                # RiverTimeStamp

            if "R000003" in name:
                logging.debug(name)
                # RiverNmea

            if "R000004" in name:
                logging.debug(name)
                # RiverBThump

            if "R000005" in name:
                logging.debug(name)
                # RiverStationID

            if "R000006" in name:
                logging.debug(name)
                # RiverTransectID

            # Move to the next dataset
            packet_pointer += data_set_size

        # Increment the ensemble index if not a vertical beam
        if not is_vert_ens:
            self.ens_index += 1

    @staticmethod
    def get_data_set_size(ds_type: int, name_len: int, num_elements: int, element_multiplier: int):
        """
        Get the dataset size.
        :param ds_type: Dataset type. (Int, float, ...)
        :param name_len: Length of the name.
        :param num_elements: Number of elements.
        :param element_multiplier: Element element multiplier.
        :return: Size of the dataset in bytes.
        """

        # Number of bytes in the data type
        datatype_size = 4
        if ds_type == 50:      # Byte Datatype
            datatype_size = 1
        elif ds_type == 20:    # Int Datatype
            datatype_size = 4
        elif ds_type == 10:    # Float Datatype
            datatype_size = 4

        return ((num_elements * element_multiplier) * datatype_size) + RtbRowe.get_base_data_size(name_len)

    @staticmethod
    def get_base_data_size(name_len: int):
        """
        Get the size of the header for a dataset.
        :param name_len: Length of the name.
        :return: Dataset header size in bytes.
        """
        return name_len + (RtbRowe.BYTES_INT32 * (RtbRowe.NUM_DATASET_HEADER_ELEMENTS - 1))

    @staticmethod
    def is_float_close(a, b, rel_tol=1e-06, abs_tol=0.0):
        """
        Check if the float values are the same.
        :param a: First float value
        :param b: Second float value
        :param rel_tol: Value within this
        :param abs_tol: Absolute value within this
        :return:
        """
        return abs(a - b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)

    @staticmethod
    def is_bad_velocity(vel):
        """
        Check if the velocity given is good or bad.
        :param vel: Velocity value to check.
        :return: True if Bad Velocity.
        """
        if vel >= RtbRowe.BAD_VEL:
            return True
        if RtbRowe.is_float_close(vel, RtbRowe.BAD_VEL):
            return True
        if vel is None:
            return True

        return False

    @staticmethod
    def get_int32(start: int, num_bytes: int, ens_bytes: list):
        """
        Convert the bytes given into an Int32.
        This will look in the ens given.
        :param start: Start location in the ens_bytes.
        :param num_bytes: Number of bytes in the int32.
        :param ens_bytes: Buffer containing the bytearray data.
        :return: Int32 of the data in the buffer.
        """
        try:
            return struct.unpack("i", ens_bytes[start:start + num_bytes])[0]
        except Exception as e:
            logging.error("Error creating a Int32 from bytes. " + str(e))
            return 0

    @staticmethod
    def get_float(start: int, num_bytes: int, ens: list):
        """
        Convert the bytes given into an int32.
        This will look in the ens given.
        :param start: Start location.
        :param num_bytes: Number of bytes in the float.
        :param ens: Buffer containing the bytearray data.
        :return: Float of the data in the buffer.
        """
        try:
            return struct.unpack("f", ens[start:start + num_bytes])[0]
        except Exception as e:
            logging.debug("Error creating a float from bytes. " + str(e))
            return 0.0

    @staticmethod
    # def nans(num_ens: int, dtype=float):
    def nans(shape, dtype=float):
        """
        Create a numpy array filled with NaN
        @param shape: tuple
            Shape of array to be filled with nans
        @param dtype: Data Type
            Type of array
        """
        empty_arr = np.empty(shape, dtype=dtype)
        empty_arr.fill(np.nan)
        return empty_arr


class Wt:
    """
    Water Profile data.
    Beam Velocity.
    Velocity data in the Beam Coordinate Transform. (Raw Velocity Data)
    Correlation, Amplitude and Good Beam data for data quality.
    """
    def __init__(self, num_beams: int, num_bins: int, num_ens: int):
        """
        :param num_beams Number of beams on the system.  Not including vertical beam
        :param num_bins Number of bins/cells.
        :param num_ens Number of ensembles in file.
        """
        self.corr = nans([num_beams, num_bins, num_ens])            # Correlation in fraction
        self.pergd = nans([num_beams, num_bins, num_ens])           # Percent Good in percentage
        self.rssi = nans([num_beams, num_bins, num_ens])            # RSSI/Amplitude in dB
        self.vel_beam_mps = nans([num_beams, num_bins, num_ens])    # Beam Velocity in m/s.

        self.vel_mps = nans([num_beams, num_bins, num_ens])         # Velocity in m/s for Qrev use

        self.vel_earth_mps = nans([num_beams, num_bins, num_ens])   # Earth Velocity in m/s
        self.pergd_earth = nans([num_beams, num_bins, num_ens])     # Percent Good in Earth data
        self.vel_instr_mps = nans([num_beams, num_bins, num_ens])   # Instrument Velocity in m/s

    def decode_vel(self, ens_bytes: list, ens_index: int, num_elements:
                   int, element_multiplier: int, name_len: int = 8):
        """
        Decode the ensemble data for the Beam velocity.

        Initialize the list of velocity data.  [beam][bin]
        RTB is m/s
        RTB Bad Value is 88.888

        :param ens_bytes: Byte array containing the ensemble data.
        :param ens_index: Ensemble Index.
        :param element_multiplier: Number of beams.
        :param num_elements; Number of bins.
        :param name_len: Length of the name of the dataset.
        """
        # Determine where to start in the ensemble data
        packet_pointer = RtbRowe.get_base_data_size(name_len)

        # Initialize the array

        vel = np.empty(shape=[element_multiplier, num_elements])

        # Create a 2D list of velocities
        # [beam][bin]
        for beam in range(element_multiplier):
            for bin_num in range(num_elements):
                vel[beam][bin_num] = RtbRowe.get_float(packet_pointer, RtbRowe.BYTES_FLOAT, ens_bytes)
                # Move the pointer
                packet_pointer += RtbRowe.BYTES_FLOAT

        self.vel_beam_mps[:element_multiplier, :num_elements, ens_index] = vel

    def decode_rssi(self, ens_bytes: list, ens_index: int, num_elements: int, element_multiplier:
                    int, name_len: int = 8):
        """
        Decode the ensemble data for the Amplitude data.

        Amplitude data which reports signal strength.
        Amplitude values range from 0 dB - 140 dB.
        Values below 25dB is considered noise.  The noise floor
        with systems with high EMI can be as a 40dB.

        Initialize the list of amplitude data.  [beam][bin]

        :param ens_bytes: Byte array containing the ensemble data.
        :param ens_index: Ensemble index to store the data.
        :param element_multiplier: Number of beams.
        :param num_elements; Number of bins.
        :param name_len: Length of the name of the dataset.
        """
        # Determine where to start in the ensemble data
        packet_pointer = RtbRowe.get_base_data_size(name_len)

        # Initialize the array
        amp = np.empty(shape=[element_multiplier, num_elements], dtype=np.float)

        # Create a 2D list of velocities
        # [beam][bin]
        for beam in range(element_multiplier):
            for bin_num in range(num_elements):
                amp[beam][bin_num] = RtbRowe.get_float(packet_pointer, RtbRowe.BYTES_FLOAT, ens_bytes)
                # Move the pointer
                packet_pointer += RtbRowe.BYTES_FLOAT

        self.rssi[:element_multiplier, :num_elements, ens_index] = amp

    def decode_corr(self, ens_bytes: list, ens_index: int, num_elements: int, element_multiplier: int,
                    name_len: int = 8):

        # Determine where to start in the ensemble data
        packet_pointer = RtbRowe.get_base_data_size(name_len)

        # Initialize the array
        corr = np.empty(shape=[element_multiplier, num_elements], dtype=np.float)

        # Create a 2D list of velocities
        # [beam][bin]
        for beam in range(element_multiplier):
            for bin_num in range(num_elements):
                corr[beam][bin_num] = RtbRowe.get_float(packet_pointer, RtbRowe.BYTES_FLOAT, ens_bytes)

                # Move the pointer
                packet_pointer += RtbRowe.BYTES_FLOAT

        self.corr[:element_multiplier, :num_elements, ens_index] = corr

    def decode_pgb(self, ens_bytes: list, ens_index: int, num_elements: int, element_multiplier: int,
                   name_len: int = 8):  # , pings_per_ens: int = 1):
        """
        Decode the ensemble data for the Good Beam Ping data.

        Good Beam Pings.  This give a number of pings
        that were used when averaging pings together.
        This will give a number of pings, so you will
        need to look at the settings to know the actual number
        of pings attempted.

        Initialize the list of Good Beam data.  [beam][bin]

        :param ens_bytes: Byte array containing the ensemble data.
        :param ens_index: Ensemble Index to store the data.
        :param element_multiplier: Number of beams.
        :param num_elements; Number of bins.
        :param name_len: Length of the name of the dataset.
        # :param pings_per_ens: Number of pings in the ensemble
        """
        # Determine where to start in the ensemble data
        packet_pointer = RtbRowe.get_base_data_size(name_len)

        # Initialize the array
        pings = np.empty(shape=[element_multiplier, num_elements], dtype=np.int)

        # Create a 2D list
        # [beam][bin]
        for beam in range(element_multiplier):
            for bin_num in range(num_elements):
                pings[beam][bin_num] = RtbRowe.get_int32(packet_pointer, RtbRowe.BYTES_INT32, ens_bytes)
                # Move the pointer
                packet_pointer += RtbRowe.BYTES_INT32

        self.pergd[:element_multiplier, :num_elements, ens_index] = pings

    def decode_earth_vel(self, ens_bytes: list, ens_index: int, num_elements: int, element_multiplier: int,
                         name_len: int = 8):
        """
        Decode the ensemble data for the Earth velocity.

        Initialize the list of velocity data.  [beam][bin]

        :param ens_bytes: Byte array containing the ensemble data.
        :param ens_index: Ensemble index in the file.
        :param element_multiplier: Number of beams.
        :param num_elements; Number of bins.
        :param name_len: Length of the name of the dataset.
        """
        # Determine where to start in the ensemble data
        packet_pointer = RtbRowe.get_base_data_size(name_len)

        # Initialize the array
        vel = np.empty(shape=[element_multiplier, num_elements])

        # Create a 2D list of velocities
        # [beam][bin]
        for beam in range(element_multiplier):
            for bin_num in range(num_elements):
                vel[beam][bin_num] = RtbRowe.get_float(packet_pointer, RtbRowe.BYTES_FLOAT, ens_bytes)
                # Move the pointer
                packet_pointer += RtbRowe.BYTES_FLOAT

        self.vel_earth_mps[:element_multiplier, :num_elements, ens_index] = vel
        self.vel_mps[:element_multiplier, :num_elements, ens_index] = vel

    def decode_pg_earth(self, ens_bytes: list, ens_index: int, num_elements: int, element_multiplier: int,
                        name_len: int = 8):  # , pings_per_ens: int = 1):
        """
        Decode the ensemble data for the Good Earth Ping data.

        Initialize the list of Good Beam data.  [beam][bin]

        :param ens_bytes: Byte array containing the ensemble data.
        :param ens_index: Ensemble index in the file.
        :param element_multiplier: Number of beams.
        :param num_elements; Number of bins.
        :param name_len: Length of the name of the dataset.
        # :param pings_per_ens: Number of pings in the ensemble
        """
        # Determine where to start in the ensemble data
        packet_pointer = RtbRowe.get_base_data_size(name_len)

        # Initialize the array
        pings = np.empty(shape=[element_multiplier, num_elements], dtype=np.int)

        # Create a 2D list
        # [beam][bin]
        for beam in range(element_multiplier):
            for bin_num in range(num_elements):
                pings[beam][bin_num] = RtbRowe.get_int32(packet_pointer, RtbRowe.BYTES_INT32, ens_bytes)

                # Move the pointer
                packet_pointer += RtbRowe.BYTES_INT32

        # Reshape the data from [beam, bin] to [bin, beam]
        # pings = np.reshape(pings, [num_elements, element_multiplier])
        # Add the data the numpy array [:num_beams, :num_bins, ens_index]
        # self.pergd_earth[:element_multiplier, :num_elements, ens_index] = pings.T
        self.pergd_earth[:element_multiplier, :num_elements, ens_index] = pings

    def decode_instr_vel(self, ens_bytes: list, ens_index: int, num_elements: int, element_multiplier: int,
                         name_len: int = 8):
        """
        Decode the ensemble data for the Instrument velocity.

        Initialize the list of velocity data.  [beam][bin]

        :param ens_bytes: Byte array containing the ensemble data.
        :param ens_index: Ensemble index in the file.
        :param element_multiplier: Number of beams.
        :param num_elements; Number of bins.
        :param name_len: Length of the name of the dataset.
        """
        # Determine where to start in the ensemble data
        packet_pointer = RtbRowe.get_base_data_size(name_len)

        # Initialize the array
        vel = np.empty(shape=[element_multiplier, num_elements])

        # Create a 2D list of velocities
        # [beam][bin]
        for beam in range(element_multiplier):
            for bin_num in range(num_elements):

                vel[beam][bin_num] = RtbRowe.get_float(packet_pointer, RtbRowe.BYTES_FLOAT, ens_bytes)

                # Move the pointer
                packet_pointer += RtbRowe.BYTES_FLOAT

        # Reshape the data from [beam, bin] to [bin, beam]
        # vel = np.reshape(vel, [num_elements, element_multiplier])
        # Add the data the numpy array [:num_beams, :num_bins, ens_index]
        # self.vel_instr_mps[:element_multiplier, :num_elements, ens_index] = vel.T
        self.vel_instr_mps[:element_multiplier, :num_elements, ens_index] = vel


class Inst:
    """
    Instrument specific values.
    """
    def __init__(self, num_ens: int):
        """
        Initialize the values.
        """
        self.firm_major = RtbRowe.nans(num_ens)                 # Firmware Major Number
        self.firm_minor = RtbRowe.nans(num_ens)                 # Firmware Minor Number
        self.firm_rev = RtbRowe.nans(num_ens)                   # Firmware Revision
        self.data_type = [''] * num_ens                         # Data type "Real" or "Simu"
        self.firm_ver = RtbRowe.nans(num_ens)                   # Firmware version as a string
        self.beam_ang = RtbRowe.nans(num_ens)                   # Beam Angle in degrees
        self.beams = RtbRowe.nans(num_ens)                      # Number of beams used in velocity measurement
        self.freq = RtbRowe.nans(num_ens)                       # System frequency in Khz
        self.pat = [''] * num_ens                               # Beam Pattern: Concave, Convex or n/a
        self.res_RDI = 0                                        # Reserved
        self.sensor_CFG = RtbRowe.nans(num_ens)                 # Sensor Configuration
        self.xducer = [''] * num_ens                            # Indicates if transducer is attached: 'Not Attached',
        # Attached, n/a
        self.t_matrix = np.tile([np.nan], [4, 4])               # Transformation matrix
        self.demod = RtbRowe.nans(num_ens)                      # Demodulation code

    def decode_ensemble_data(self, ens_bytes: list, ens_index: int, name_len: int = 8):
        """
        Decode the ensemble data for the Instrument data.

        :param ens_bytes: Byte array containing the ensemble data.
        :param ens_index: Ensemble index.
        :param name_len: Length of the name of the dataset.
        """
        # Determine where to start in the ensemble data
        packet_pointer = RtbRowe.get_base_data_size(name_len)

        self.beams[ens_index] = RtbRowe.get_int32(packet_pointer + RtbRowe.BYTES_INT32 * 2, RtbRowe.BYTES_INT32,
                                                  ens_bytes)

        firm_rev = struct.unpack("B", ens_bytes[packet_pointer + RtbRowe.BYTES_INT32 * 21 + 0:
                                                packet_pointer + RtbRowe.BYTES_INT32 * 21 + 1])[0]
        firm_minor = struct.unpack("B", ens_bytes[packet_pointer + RtbRowe.BYTES_INT32 * 21 + 1:
                                                  packet_pointer + RtbRowe.BYTES_INT32 * 21 + 2])[0]
        firm_major = struct.unpack("B", ens_bytes[packet_pointer + RtbRowe.BYTES_INT32 * 21 + 2:
                                                  packet_pointer + RtbRowe.BYTES_INT32 * 21 + 3])[0]

        self.firm_rev[ens_index] = firm_rev
        self.firm_minor[ens_index] = firm_minor
        self.firm_major[ens_index] = firm_major
        self.firm_ver[ens_index] = round(firm_minor + (firm_rev/100.0), 2)

        # Determine the beam angle based on the subsystem type
        ss_code = str(ens_bytes[packet_pointer + RtbRowe.BYTES_INT32 * 21 + 3:
                                packet_pointer + RtbRowe.BYTES_INT32 * 21 + 4], "UTF-8")
        if ss_code == "A" or ss_code == "B" or ss_code == "C":
            self.beam_ang[ens_index] = 0
        else:
            self.beam_ang[ens_index] = 20

    def decode_systemsetup_data(self, ens_bytes: list, ens_index: int, name_len: int = 8):
        """
        Decode the system setup data for the Configuration data.

        :param ens_bytes: Byte array containing the ensemble data.
        :param ens_index: Ensemble Index.
        :param name_len: Length of the name of the dataset.
        """
        # Determine where to start in the ensemble data
        packet_pointer = RtbRowe.get_base_data_size(name_len)

        # Get the frequency and convert from Hz to kHz
        freq = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 6, RtbRowe.BYTES_FLOAT, ens_bytes)

        freq_khz = freq / 1000
        if 60 < freq_khz < 80:
            freq_khz = 75
        elif 130 < freq_khz < 160:
            freq_khz = 150
        elif 200 < freq_khz < 400:
            freq_khz = 300
        elif 400 < freq_khz < 800:
            freq_khz = 600
        elif 1000 < freq_khz < 1300:
            freq_khz = 1200
        elif 1800 < freq_khz < 2500:
            freq_khz = 2400
        # else:
        #    freq_khz = np.nan

        # Set the value
        self.freq[ens_index] = freq_khz

        # Options are Concave, Convex or n/a
        self.pat[ens_index] = 'Concave'

        # Options are 'Not Attached', Attached or n/a
        self.xducer[ens_index] = 'Attached'

        # Options are 'Simu' or 'Real'
        self.data_type = 'Real'

        # Transformation matrix
        self.t_matrix[0] = [-1.4619, 1.4619, 0, 0]
        self.t_matrix[1] = [0, 0, -1.4619, 1.4619]
        self.t_matrix[2] = [-0.2660, -0.2660, -0.2660, -0.2660]
        self.t_matrix[3] = [0.25, 0.25, -0.25, -0.25]


class Cfg:
    """
    System configuration data is all the data that describes the ADCP configuration and date and time.
    This includes the bin size, blank and number of bins, the ensemble number, date and time.
    """

    def __init__(self, num_ens: int):
        """
        Initialize all the values

        :param num_ens: Number of ensembles.

        """

        self.ens_num = RtbRowe.nans(num_ens)                    # Ensemble number
        # self.num_bins = RtbRowe.nans(num_ens)                 # Replaced with wn Number of bins
        self.desired_ping_count = RtbRowe.nans(num_ens)         # Avg Ping Count configured in seconds
        # self.actual_ping_count = RtbRowe.nans(num_ens)        # Replaced with wp. Avg Ping Count actually
        # output in seconds
        # self.serial_num_index = RtbRowe.nans(num_ens)  # np.empty(num_ens, dtype=str)          # Serial Number Index
        # self.serial_num_index = RtbRowe.nans(num_ens, dtype=str)
        # self.subsystem_code = RtbRowe.nans(num_ens, dtype=str)# SubsystemCode(Identifier of frequency and orientation)
        # self.subsystem_config = RtbRowe.nans(num_ens)           # Subsystem Config.  System allows multiple configures
        # of the same frequency.  This identifies each configuration
        self.status = RtbRowe.nans(num_ens)                     # Status code
        # self.year = RtbRowe.nans(num_ens)                       # Year
        # self.month = RtbRowe.nans(num_ens)                      # Month
        # self.day = RtbRowe.nans(num_ens)                        # Day
        # self.hour = RtbRowe.nans(num_ens)                       # Hour
        # self.minute = RtbRowe.nans(num_ens)                     # Minute
        # self.second = RtbRowe.nans(num_ens)                     # Second
        # self.hsec = RtbRowe.nans(num_ens)                       # Hundredth Second

        # ADCP 3 values
        self.current_system = RtbRowe.nans(num_ens)
        self.status_2 = RtbRowe.nans(num_ens)
        self.burst_index = RtbRowe.nans(num_ens)

        self.first_ping_time = RtbRowe.nans(num_ens)          # First Ping Time in seconds.
        self.last_ping_time = RtbRowe.nans(num_ens)           # Last Ping Time in seconds. (If averaging pings,
        # this will be the last ping)
        self.salinity = RtbRowe.nans(num_ens)                 # Water Salinity set by the user in PPT
        self.speed_of_sound = RtbRowe.nans(num_ens)           # Speed of Sound in m/s.

        self.bt_first_ping_time = RtbRowe.nans(num_ens)
        self.bt_last_ping_time = RtbRowe.nans(num_ens)
        self.bt_speed_of_sound = RtbRowe.nans(num_ens)
        self.bt_status = RtbRowe.nans(num_ens)
        self.bt_num_beams = RtbRowe.nans(num_ens)
        self.bt_actual_ping_count = RtbRowe.nans(num_ens)

        self.bt_samples_per_second = RtbRowe.nans(num_ens)    # Bottom Track Samples Per Second
        self.bt_system_freq_hz = RtbRowe.nans(num_ens)        # Bottom Track System Frequency (Hz)
        self.bt_cpce = RtbRowe.nans(num_ens)                  # Bottom Track Carrier cycles per Code Elements
        self.bt_nce = RtbRowe.nans(num_ens)                   # Bottom Track Number of Code Elements contained in a lag
        self.bt_repeat_n = RtbRowe.nans(num_ens)              # Bottom Track Number of times the NCE is repeated in the
        # transmit signal
        self.wp_samples_per_second = RtbRowe.nans(num_ens)    # Water Profile Samples per Second
        # self.wp_system_freq_hz = []        # Water Profile System Frequency (Hz)
        self.wp_cpce = RtbRowe.nans(num_ens)                  # Water Profile Carrier cycles per Code Elements
        self.wp_nce = RtbRowe.nans(num_ens)                   # Water Profile Number of Code Elements contained in a lag
        self.wp_repeat_n = RtbRowe.nans(num_ens)              # Water Profile Number of times the NCE is repeated in the
        # transmit signal
        self.wp_lag_samples = RtbRowe.nans(num_ens)           # Water Profile Lag Samples
        # self.bt_broadband = RtbRowe.nans(num_ens)             # Bottom Track Broadband
        self.bt_lag_length = RtbRowe.nans(num_ens)            # Bottom Track Pulse to Pulse Lag (m)
        self.bt_narrowband = RtbRowe.nans(num_ens)            # Bottom Track Long Range Switch Depth (m)
        self.bt_beam_mux = RtbRowe.nans(num_ens)              # Bottom Track Beam Multiplex
        # self.wp_broadband = RtbRowe.nans(num_ens)             # Water Profile Mode
        self.lag_cm = RtbRowe.nans(num_ens)                   # Water Profile Lag Length
        self.lag_near_bottom = RtbRowe.nans(num_ens)          # Water Profile Lag Near Bottom
        self.wp_transmit_bandwidth = RtbRowe.nans(num_ens)    # Water Profile Transmit Bandwidth
        self.wp_receive_bandwidth = RtbRowe.nans(num_ens)     # Water Profile Receive Bandwidth
        self.wp_beam_mux = RtbRowe.nans(num_ens)              # WP Beam Mux

        self.ba = RtbRowe.nans(num_ens)                         # Bottom Track Amplitude Threshold
        self.bc = RtbRowe.nans(num_ens)                         # Bottom Track Correlation Threshold
        self.be_mmps = RtbRowe.nans(num_ens)                    # Bottom Track Error Velocity Threshold
        self.bg = RtbRowe.nans(num_ens)                         # Bottom Track Percent Good Threshold
        self.bm = RtbRowe.nans(num_ens)                         # * Bottom Track Mode
        self.bp = RtbRowe.nans(num_ens)                         # Bottom Track Number of Pings
        self.bx_dm = RtbRowe.nans(num_ens)                      # Maximum Tracking depth in decimeters
        self.code_reps = RtbRowe.nans(num_ens)                  # Number of code repetitions
        self.coord_sys = ['Earth'] * num_ens                         # Coordinate System
        self.cpu_ser_no = RtbRowe.nans([num_ens, 8])            # CPU Serial Number
        self.cq = RtbRowe.nans(num_ens)                         # Transmit Power
        self.cx = RtbRowe.nans(num_ens)                         # Low Latency Trigger
        self.dist_bin1_cm = RtbRowe.nans(num_ens)               # * Distance to center of bin 1 from transducer
        self.ea_deg = RtbRowe.nans(num_ens)                     # Heading alignment
        self.eb_deg = RtbRowe.nans(num_ens)                     # Heading bias
        self.sensor_avail = [''] * num_ens                      # Sensor availability code
        self.ex = [''] * num_ens                                # Coordinate transformation codes
        self.ez = [''] * num_ens                                # Sensor codes
        self.head_src = [''] * num_ens                          # Heading sources
        self.lag_cm = RtbRowe.nans(num_ens)                     # * Lag Length in centimeter
        self.map_bins = [''] * num_ens                          # * Bin Mapping
        self.n_beams = RtbRowe.nans(num_ens)                    # * Number of velocity beams
        self.pitch_src = [''] * num_ens                         # Source of pitch data
        self.ref_lay_end_cell = RtbRowe.nans(num_ens)           # Reference Layer end cell
        self.ref_lay_str_cell = RtbRowe.nans(num_ens)           # Reference Layer start cell
        self.roll_src = [''] * num_ens                          # Source of roll data
        self.sal_src = [''] * num_ens                           # Salinity Source
        self.wm = RtbRowe.nans(num_ens)                         # * Water Mode
        self.sos_src = [''] * num_ens                           # Speed of Sound source
        self.temp_src = [''] * num_ens                          # Temperature Source
        self.tp_sec = RtbRowe.nans(num_ens)                     # * Time between Pings
        self.use_3beam = [''] * num_ens                         # Setting to use 3-Beam solution or not
        self.use_pr = [''] * num_ens                            # Setting to use pitch and roll or not
        self.wa = RtbRowe.nans(num_ens)                         # Water Track amplitude threshold
        self.wb = RtbRowe.nans(num_ens)                         # Water Track bandwidth threshold
        self.wc = RtbRowe.nans(num_ens)                         # Water Track correlation threshold
        self.we_mmps = RtbRowe.nans(num_ens)                    # Water Track error velocity threshold
        self.wf_cm = RtbRowe.nans(num_ens)                      # * Blank after Transmit in cm
        self.wg_per = RtbRowe.nans(num_ens)                     # Water Track percent good threshold
        self.wj = RtbRowe.nans(num_ens)                         # Receiver Gain setting
        self.wn = RtbRowe.nans(num_ens)                         # * Number of depth cells (bins)
        self.wp = RtbRowe.nans(num_ens)                         # * Number of water pings
        self.ws_cm = RtbRowe.nans(num_ens)                      # * Bin size in cm
        self.xdcr_dep_srs = [''] * num_ens                      # Salinity Source
        self.xmit_pulse_cm = RtbRowe.nans(num_ens)              # Transmit Pulse length
        self.lag_near_bottom = RtbRowe.nans(num_ens)            # Lag near bottom setting

    def decode_ensemble_data(self, ens_bytes: list, ens_index: int, name_len: int = 8):
        """
        Decode the ensemble data for the configuration data.

        :param ens_bytes: Byte array containing the ensemble data.
        :param ens_index: Ensemble index to store the data.
        :param name_len: Length of the name of the dataset.
        """
        # Determine where to start in the ensemble data
        packet_pointer = RtbRowe.get_base_data_size(name_len)

        self.ens_num[ens_index] = RtbRowe.get_int32(packet_pointer + RtbRowe.BYTES_INT32 * 0, RtbRowe.BYTES_INT32,
                                                    ens_bytes)
        self.wn[ens_index] = RtbRowe.get_int32(packet_pointer + RtbRowe.BYTES_INT32 * 1, RtbRowe.BYTES_INT32, ens_bytes)
        self.n_beams[ens_index] = RtbRowe.get_int32(packet_pointer + RtbRowe.BYTES_INT32 * 2, RtbRowe.BYTES_INT32,
                                                    ens_bytes)
        self.desired_ping_count[ens_index] = RtbRowe.get_int32(packet_pointer + RtbRowe.BYTES_INT32 * 3,
                                                               RtbRowe.BYTES_INT32, ens_bytes)
        self.wp[ens_index] = RtbRowe.get_int32(packet_pointer + RtbRowe.BYTES_INT32 * 4, RtbRowe.BYTES_INT32, ens_bytes)
        self.status[ens_index] = RtbRowe.get_int32(packet_pointer + RtbRowe.BYTES_INT32 * 5, RtbRowe.BYTES_INT32,
                                                   ens_bytes)
        # self.year.append(RtbRowe.get_int32(packet_pointer + RtbRowe.BYTES_INT32 * 6, RtbRowe.BYTES_INT32, ens_bytes))
        # self.month[ens_index] = RtbRowe.get_int32(packet_pointer + RtbRowe.BYTES_INT32 * 7, RtbRowe.BYTES_INT32,
        # ens_bytes)
        # self.day[ens_index] = RtbRowe.get_int32(packet_pointer + RtbRowe.BYTES_INT32 * 8, RtbRowe.BYTES_INT32,
        # ens_bytes)
        # self.hour[ens_index] = RtbRowe.get_int32(packet_pointer + RtbRowe.BYTES_INT32 * 9, RtbRowe.BYTES_INT32,
        # ens_bytes)
        # self.minute[ens_index] = RtbRowe.get_int32(packet_pointer + RtbRowe.BYTES_INT32 * 10, RtbRowe.BYTES_INT32,
        # ens_bytes)
        # self.second[ens_index] = RtbRowe.get_int32(packet_pointer + RtbRowe.BYTES_INT32 * 11, RtbRowe.BYTES_INT32,
        # ens_bytes)
        # self.hsec[ens_index] = RtbRowe.get_int32(packet_pointer + RtbRowe.BYTES_INT32 * 12, RtbRowe.BYTES_INT32,
        # ens_bytes)

        # self.serial_num_index[ens_index] = str(
        #    ens_bytes[packet_pointer + RtbRowe.BYTES_INT32 * 13:packet_pointer + RtbRowe.BYTES_INT32 * 21], "UTF-8")

        # self.subsystem_code[ens_index] = str(ens_bytes[packet_pointer +
        #                                               RtbRowe.BYTES_INT32 * 21 + 3:
        #                                               packet_pointer + RtbRowe.BYTES_INT32 * 21 + 4], "UTF-8")

        # self.subsystem_config[ens_index] = struct.unpack("B", ens_bytes[packet_pointer +
        #                                                                 RtbRowe.BYTES_INT32 * 22 + 3:packet_pointer +
        #                                                                 RtbRowe.BYTES_INT32 * 22 + 4])[0]

        # With our data format, Beam, Instrument and Earth
        # Are always available.  The Data stored in vel_mps
        # will always be Earth data.
        self.coord_sys[ens_index] = 'Earth'

    def decode_ancillary_data(self, ens_bytes: list, ens_index: int, name_len: int = 8):
        """
        Decode the ancillary data for the Configuration data.

        :param ens_bytes: Byte array containing the ensemble data.
        :param ens_index: Ensemble index to store the data.
        :param name_len: Length of the name of the dataset.
        """
        # Determine where to start in the ensemble data
        packet_pointer = RtbRowe.get_base_data_size(name_len)

        self.wf_cm[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 0, RtbRowe.BYTES_FLOAT,
                                                  ens_bytes) * 100.0
        self.ws_cm[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 1, RtbRowe.BYTES_FLOAT,
                                                  ens_bytes) * 100.0
        first_ping_time = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 2, RtbRowe.BYTES_FLOAT, ens_bytes)
        last_ping_time = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 3, RtbRowe.BYTES_FLOAT, ens_bytes)

        self.first_ping_time[ens_index] = first_ping_time
        self.last_ping_time[ens_index] = last_ping_time
        self.tp_sec[ens_index] = last_ping_time - first_ping_time

        # If there is any value other than 0
        # Then pressure sensor is available
        pressure = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 10, RtbRowe.BYTES_FLOAT, ens_bytes)
        if pressure > 0:
            self.use_pr = 'Yes'
        else:
            self.use_pr = 'No'

        # Our system will always perform bin mapping
        self.map_bins = 'Yes'

        # Calculate the Bin 1 Distance for now
        # TODO Speed of Sound not used in this calculation like documentation states
        self.dist_bin1_cm[ens_index] = self.wf_cm[ens_index] = (self.ws_cm[ens_index] / 2.0)

        # TODO Not sure the correct answer here
        self.use_3beam = 'N/a'

        # Based on the data, unable to determine
        # which source was used for the Speed of Sound source
        # Could be calculated or a fixed value.
        # Options: 'Manual EC', 'Calculated', 'SVSS Sensor', N/a'
        self.sos_src = 'Calculated'

        # Based on the data, unable to determine
        # which source was used for the heading source
        # Could be compass, fixed value or GPS
        # Options: "Manual EH", 'Int. Sensor', 'N/a'
        self.head_src = 'Int. Sensor'

        # Pitch source currently only internal sensor
        self.pitch_src = "Int. Sensor"
        self.roll_src = "Int. Sensor"

        # Based on the data, unable to determine
        # which source was used for depth source.
        # Could be RT or pressure
        # Options: "Manual ES", 'Int. Sensor', 'N/a'
        self.xdcr_dep_srs = "Manual ES"

        # Based on the data, unable to determine
        # which source was used for temperature
        # Could be internal sensor or fixed value
        # Options: 'Manual ET', 'Int. Sensor', 'N/a'
        self.temp_src = 'Int. Sensor'

        self.salinity[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 9, RtbRowe.BYTES_FLOAT,
                                                     ens_bytes)
        self.speed_of_sound[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 12,
                                                           RtbRowe.BYTES_FLOAT, ens_bytes)

    def decode_ancillary_adcp3_data(self, ens_bytes: list, ens_index: int, name_len: int = 8):
        """
        Decode the ancillary data for the Configuration data.

        :param ens_bytes: Byte array containing the ensemble data.
        :param ens_index: Ensemble index to store the data.
        :param name_len: Length of the name of the dataset.
        """
        # Determine where to start in the ensemble data
        packet_pointer = RtbRowe.get_base_data_size(name_len)

        self.current_system[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 0,
                                                           RtbRowe.BYTES_FLOAT, ens_bytes)
        self.status_2[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 1,
                                                     RtbRowe.BYTES_FLOAT, ens_bytes)
        self.burst_index[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 2,
                                                        RtbRowe.BYTES_FLOAT, ens_bytes)

    def decode_systemsetup_data(self, ens_bytes: list, ens_index: int, name_len: int = 8):
        """
        Decode the system setup data for the Configuration data.

        :param ens_bytes: Byte array containing the ensemble data.
        :param ens_index: Ensemble index to store the data.
        :param name_len: Length of the name of the dataset.
        """
        # Determine where to start in the ensemble data
        packet_pointer = RtbRowe.get_base_data_size(name_len)

        self.bt_samples_per_second[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 0,
                                                                  RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_system_freq_hz[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 1,
                                                              RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_cpce[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 2,
                                                    RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_nce[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 3,
                                                   RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_repeat_n[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 4,
                                                        RtbRowe.BYTES_FLOAT, ens_bytes)
        self.wp_samples_per_second[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 5,
                                                                  RtbRowe.BYTES_FLOAT, ens_bytes)
        # self.wp_system_freq_hz.append(RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 6, RtbRowe.BYTES_FLOAT,
        # ens_bytes))
        self.wp_cpce[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 7,
                                                    RtbRowe.BYTES_FLOAT, ens_bytes)
        self.wp_nce[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 8,
                                                   RtbRowe.BYTES_FLOAT, ens_bytes)
        self.wp_repeat_n[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 9,
                                                        RtbRowe.BYTES_FLOAT, ens_bytes)
        self.wp_lag_samples[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 10,
                                                           RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bm[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 13,
                                               RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_lag_length[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 14,
                                                          RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_narrowband[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 15,
                                                          RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_beam_mux[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 16,
                                                        RtbRowe.BYTES_FLOAT, ens_bytes)
        self.wm[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 17,
                                               RtbRowe.BYTES_FLOAT, ens_bytes)
        self.lag_cm[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 18,
                                                   RtbRowe.BYTES_FLOAT, ens_bytes) * 100.0
        self.wp_transmit_bandwidth[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 19,
                                                                  RtbRowe.BYTES_FLOAT, ens_bytes)
        self.wp_receive_bandwidth[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 20,
                                                                 RtbRowe.BYTES_FLOAT, ens_bytes)
        self.wp_beam_mux[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 22,
                                                        RtbRowe.BYTES_FLOAT, ens_bytes)

        # Use the same as lag
        self.lag_near_bottom[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 18,
                                                            RtbRowe.BYTES_FLOAT, ens_bytes) * 100.0

        # Assume always a 20 degree beam angle for now
        beam_angle = 20

        # Get the speed of sound from this ensemble or previous
        speed_of_sound = 1500
        if not np.isnan(self.speed_of_sound[ens_index]):
            speed_of_sound = self.speed_of_sound[ens_index]
        elif ens_index-1 >= 0 and not np.isnan(self.speed_of_sound[ens_index-1]):
            speed_of_sound = self.speed_of_sound[ens_index-1]

        # Calculate lag length
        # and Xmit Pulse Length
        # sample_rate = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 5, RtbRowe.BYTES_FLOAT, ens_bytes)
        # lag_samples = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 10, RtbRowe.BYTES_FLOAT, ens_bytes)
        cpce = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 7, RtbRowe.BYTES_FLOAT, ens_bytes)
        nce = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 8, RtbRowe.BYTES_FLOAT, ens_bytes)
        repeats_n = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 9, RtbRowe.BYTES_FLOAT, ens_bytes)
        sys_freq_hz = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 6, RtbRowe.BYTES_FLOAT, ens_bytes)
        # meters_per_sample = math.cos(math.pi * (beam_angle/180.0)) * speed_of_sound / 2 / sample_rate
        # lag_m = lag_samples * meters_per_sample
        meters_per_cycle = math.cos(math.pi * (beam_angle/180.0)) * speed_of_sound / 2 / sys_freq_hz
        xmt_m = cpce * nce * repeats_n * meters_per_cycle
        self.xmit_pulse_cm[ens_index] = xmt_m * 100.0

    def decode_bottom_track_data(self, ens_bytes: list, ens_index: int, name_len: int = 8):
        """
        Decode the system Bottom Track data for the Configuration data.

        :param ens_bytes: Byte array containing the ensemble data.
        :param ens_index: Ensemble index to store the data.
        :param name_len: Length of the name of the dataset.
        """
        # Determine where to start in the ensemble data
        packet_pointer = RtbRowe.get_base_data_size(name_len)

        self.bt_first_ping_time[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 0,
                                                               RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_last_ping_time[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 1,
                                                              RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_speed_of_sound[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 10,
                                                              RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_status[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 11,
                                                      RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_num_beams[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 12,
                                                         RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_actual_ping_count[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 13,
                                                                 RtbRowe.BYTES_FLOAT, ens_bytes)


class Sensor:
    """
    System sensor data is all the data from the sensors within the ADCP.  This includes compass and
    temperature sensor.
    """

    def __init__(self, num_ens: int):
        """
        Initialize all the values

        Set the flag if using PD0 format data.  This will change the scale of the pressure sensor and orientation
        of the roll value.

        :param num_ens: Number of ensembles in the file.

        """
        self.voltage = RtbRowe.nans(num_ens)                            # Voltage input to ADCP
        self.transmit_boost_neg_volt = RtbRowe.nans(num_ens)            # Transmitter Boost Negative Voltage
        self.raw_mag_field_strength = RtbRowe.nans(num_ens)             # Raw magnetic field strength (uT) (micro Tesla)
        self.raw_mag_field_strength2 = RtbRowe.nans(num_ens)            # Raw magnetic field strength (uT) (micro Tesla)
        self.raw_mag_field_strength3 = RtbRowe.nans(num_ens)            # Raw magnetic field strength (uT) (micro Tesla)
        self.pitch_gravity_vec = RtbRowe.nans(num_ens)                  # Pitch Gravity Vector
        self.roll_gravity_vec = RtbRowe.nans(num_ens)                   # Roll Gravity Vector
        self.vertical_gravity_vec = RtbRowe.nans(num_ens)               # Vertical Gravity Vector

        self.bt_heading = RtbRowe.nans(num_ens)
        self.bt_pitch = RtbRowe.nans(num_ens)
        self.bt_roll = RtbRowe.nans(num_ens)
        self.bt_water_temp = RtbRowe.nans(num_ens)
        self.bt_system_temp = RtbRowe.nans(num_ens)
        self.bt_salinity = RtbRowe.nans(num_ens)
        self.bt_pressure = RtbRowe.nans(num_ens)
        self.bt_transducer_depth = RtbRowe.nans(num_ens)

        # ADCP 3 Values
        self.hs1_temp = RtbRowe.nans(num_ens)
        self.hs2_temp = RtbRowe.nans(num_ens)
        self.rcv1_temp = RtbRowe.nans(num_ens)
        self.rcv2_temp = RtbRowe.nans(num_ens)
        self.vinf = RtbRowe.nans(num_ens)
        self.vg = RtbRowe.nans(num_ens)
        self.vt = RtbRowe.nans(num_ens)
        self.vtl = RtbRowe.nans(num_ens)
        self.d3v3 = RtbRowe.nans(num_ens)
        self.bt_hs1_temp = RtbRowe.nans(num_ens)
        self.bt_hs2_temp = RtbRowe.nans(num_ens)
        self.bt_rcv1_temp = RtbRowe.nans(num_ens)
        self.bt_rcv2_temp = RtbRowe.nans(num_ens)
        self.bt_vinf = RtbRowe.nans(num_ens)
        self.bt_vg = RtbRowe.nans(num_ens)
        self.bt_vt = RtbRowe.nans(num_ens)
        self.bt_vtl = RtbRowe.nans(num_ens)
        self.bt_d3v3 = RtbRowe.nans(num_ens)
        self.bt_sounder_range = RtbRowe.nans(num_ens)
        self.bt_sounder_snr = RtbRowe.nans(num_ens)
        self.bt_sounder_amp = RtbRowe.nans(num_ens)

        self.echo_sounder_depth = RtbRowe.nans(num_ens)

        self.ambient_temp = RtbRowe.nans(num_ens)                       # ADC ambient temperature
        self.attitude_temp = RtbRowe.nans(num_ens)                      # ADC attitude temperature
        self.attitude = RtbRowe.nans(num_ens)                           # ADC attitude
        self.bit_test = RtbRowe.nans(num_ens)                           # Bit Test Result
        self.contam_sensor = RtbRowe.nans(num_ens)                      # ADC contamination sensor
        self.date = RtbRowe.nans([num_ens, 3])                          # date as int
        self.date_y2k = RtbRowe.nans([num_ens, 4])                      # Date Y2K compatible
        self.date_not_y2k = RtbRowe.nans([num_ens, 3])                  # Date not Y2K compatible
        self.error_status_word = [''] * num_ens                         # Error Status codes
        self.heading_deg = RtbRowe.nans(num_ens)                        # Heading to magnetic north in degrees
        self.heading_std_dev_deg = RtbRowe.nans(num_ens)                # Standard deviation of headings for an ensemble
        self.mpt_msc = RtbRowe.nans([num_ens, 3])                       # Minimum time prior to ping
        self.num = RtbRowe.nans(num_ens)                                # Ensemble number
        self.num_fact = RtbRowe.nans(num_ens)                           # Number fraction
        self.num_tot = RtbRowe.nans(num_ens)                            # Number total
        self.orient = [''] * num_ens                                    # Orientation of ADCP
        self.pitch_std_dev_deg = RtbRowe.nans(num_ens)                  # Standard deviation of pitch for an ensemble
        self.pitch_deg = RtbRowe.nans(num_ens)                          # Pitch in degrees
        self.pressure_neg = RtbRowe.nans(num_ens)                       # ADC pressure negative
        self.pressure_pos = RtbRowe.nans(num_ens)                       # ADC pressure positive
        self.pressure_pascal = RtbRowe.nans(num_ens)                    # Pressure at transducer face in deca-pascals
        self.pressure_var_pascal = RtbRowe.nans(num_ens)                # Pressure variance in deca-pascals
        self.roll_std_dev_deg = RtbRowe.nans(num_ens)                   # Standard deviation of roll for an ensemble
        self.roll_deg = RtbRowe.nans(num_ens)                           # Roll in degrees
        self.salinity_ppt = RtbRowe.nans(num_ens)                       # Salinity in parts per thousand PPT
        self.sos_mps = RtbRowe.nans(num_ens)                            # Speed of Sound in m/s
        self.temperature_deg_c = RtbRowe.nans(num_ens)                  # Water Temperature in degrees C
        self.time = RtbRowe.nans([num_ens, 4])                          # Time
        self.time_y2k = RtbRowe.nans([num_ens, 4])                      # Y2K compatible time
        self.xdcr_depth_dm = RtbRowe.nans(num_ens)                      # Transducer depth in decimeters
        self.xmit_current = RtbRowe.nans(num_ens)                       # Transmit current
        self.xmit_voltage = RtbRowe.nans(num_ens)                       # Transmit voltage

        self.vert_beam_eval_amp = RtbRowe.nans(num_ens)                 # Vertical beam amplitude
        self.vert_beam_RSSI_amp = RtbRowe.nans(num_ens)                 # Vertical beam return signal strength indicator
        self.vert_beam_range_m = RtbRowe.nans(num_ens)                  # Vertical beam range in m
        self.vert_beam_gain = [''] * num_ens                            # Vertical beam gain setting
        self.vert_beam_status = np.zeros(num_ens)                       # Vertical beam status

    def decode_ensemble_data(self, ens_bytes: list, ens_index: int, name_len: int = 8):
        """
        Decode the system setup data for the Sensor data.

        :param ens_bytes: Byte array containing the ensemble data.
        :param ens_index: Ensemble index in the file.
        :param name_len: Length of the name of the dataset.
        """
        # Determine where to start in the ensemble data
        packet_pointer = RtbRowe.get_base_data_size(name_len)

        year = RtbRowe.get_int32(packet_pointer + RtbRowe.BYTES_INT32 * 6, RtbRowe.BYTES_INT32, ens_bytes)
        month = RtbRowe.get_int32(packet_pointer + RtbRowe.BYTES_INT32 * 7, RtbRowe.BYTES_INT32, ens_bytes)
        day = RtbRowe.get_int32(packet_pointer + RtbRowe.BYTES_INT32 * 8, RtbRowe.BYTES_INT32, ens_bytes)
        hour = RtbRowe.get_int32(packet_pointer + RtbRowe.BYTES_INT32 * 9, RtbRowe.BYTES_INT32, ens_bytes)
        minute = RtbRowe.get_int32(packet_pointer + RtbRowe.BYTES_INT32 * 10, RtbRowe.BYTES_INT32, ens_bytes)
        second = RtbRowe.get_int32(packet_pointer + RtbRowe.BYTES_INT32 * 11, RtbRowe.BYTES_INT32, ens_bytes)
        hsec = RtbRowe.get_int32(packet_pointer + RtbRowe.BYTES_INT32 * 12, RtbRowe.BYTES_INT32, ens_bytes)

        ens_date = [year, month, day]
        ens_date_y2k = [2000, year-2000, month, day]
        ens_date_not_y2k = [year - 2000, month, day]
        ens_time = [hour, minute, second, hsec]
        self.date[ens_index] = ens_date
        self.date_not_y2k[ens_index] = ens_date_not_y2k
        self.date_y2k[ens_index] = ens_date_y2k
        self.time_y2k[ens_index] = ens_time
        self.time[ens_index] = ens_time

    def decode_systemsetup_data(self, ens_bytes: list, ens_index: int, name_len: int = 8):
        """
        Decode the system setup data for the Sensor data.

        :param ens_bytes: Byte array containing the ensemble data.
        :param ens_index: Ensemble index in the file.
        :param name_len: Length of the name of the dataset.
        """
        # Determine where to start in the ensemble data
        packet_pointer = RtbRowe.get_base_data_size(name_len)

        self.voltage[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 11,
                                                    RtbRowe.BYTES_FLOAT, ens_bytes)
        self.xmit_voltage[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 12,
                                                         RtbRowe.BYTES_FLOAT, ens_bytes)
        self.transmit_boost_neg_volt[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 21,
                                                                    RtbRowe.BYTES_FLOAT, ens_bytes)

    def decode_ancillary_data(self, ens_bytes: list, ens_index: int, name_len: int = 8):
        """
        Decode the ancillary data for the Sensor data.

        :param ens_bytes: Byte array containing the ensemble data.
        :param ens_index: Ensemble index to store the data.
        :param name_len: Length of the name of the dataset.
        """
        # Determine where to start in the ensemble data
        packet_pointer = RtbRowe.get_base_data_size(name_len)

        self.heading_deg[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 4,
                                                        RtbRowe.BYTES_FLOAT, ens_bytes)
        self.pitch_deg[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 5,
                                                      RtbRowe.BYTES_FLOAT, ens_bytes)

        self.temperature_deg_c[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 7,
                                                              RtbRowe.BYTES_FLOAT, ens_bytes)
        self.ambient_temp[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 8,
                                                         RtbRowe.BYTES_FLOAT, ens_bytes)
        self.salinity_ppt[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 9,
                                                         RtbRowe.BYTES_FLOAT, ens_bytes)
        self.sos_mps[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 12,
                                                    RtbRowe.BYTES_FLOAT, ens_bytes)

        self.raw_mag_field_strength[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 13,
                                                                   RtbRowe.BYTES_FLOAT, ens_bytes)
        self.raw_mag_field_strength2[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 14,
                                                                    RtbRowe.BYTES_FLOAT, ens_bytes)
        self.raw_mag_field_strength3[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 15,
                                                                    RtbRowe.BYTES_FLOAT, ens_bytes)
        self.pitch_gravity_vec[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 16,
                                                              RtbRowe.BYTES_FLOAT, ens_bytes)
        self.roll_gravity_vec[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 17,
                                                             RtbRowe.BYTES_FLOAT, ens_bytes)
        self.vertical_gravity_vec[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 18,
                                                                 RtbRowe.BYTES_FLOAT, ens_bytes)

        self.roll_deg[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 6,
                                                     RtbRowe.BYTES_FLOAT, ens_bytes)
        self.pressure_pascal[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 10,
                                                            RtbRowe.BYTES_FLOAT, ens_bytes)
        self.xdcr_depth_dm[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 11,
                                                          RtbRowe.BYTES_FLOAT, ens_bytes)

    def decode_ancillary_adcp3_data(self, ens_bytes: list, ens_index: int, name_len: int = 8):
        """
        Decode the ancillary ADCP3 data for the Sensor data.

        :param ens_bytes: Byte array containing the ensemble data.
        :param ens_index: Ensemble index in the file.
        :param name_len: Length of the name of the dataset.
        """
        # Determine where to start in the ensemble data
        packet_pointer = RtbRowe.get_base_data_size(name_len)

        self.hs1_temp[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 13,
                                                     RtbRowe.BYTES_FLOAT, ens_bytes)
        self.hs2_temp[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 14,
                                                     RtbRowe.BYTES_FLOAT, ens_bytes)
        self.rcv1_temp[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 15,
                                                      RtbRowe.BYTES_FLOAT, ens_bytes)
        self.rcv2_temp[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 16,
                                                      RtbRowe.BYTES_FLOAT, ens_bytes)
        self.vinf[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 17,
                                                 RtbRowe.BYTES_FLOAT, ens_bytes)
        self.vg[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 18,
                                               RtbRowe.BYTES_FLOAT, ens_bytes)
        self.vt[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 16,
                                               RtbRowe.BYTES_FLOAT, ens_bytes)
        self.vtl[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 17,
                                                RtbRowe.BYTES_FLOAT, ens_bytes)
        self.d3v3[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 18,
                                                 RtbRowe.BYTES_FLOAT, ens_bytes)

    def decode_bottom_track_data(self, ens_bytes: list, ens_index: int, name_len: int = 8):
        """
        Decode the bottom track data for the Sensor data.

        :param ens_bytes: Byte array containing the ensemble data.
        :param ens_index: Ensemble index in the file.
        :param name_len: Length of the name of the dataset.
        """
        # Determine where to start in the ensemble data
        packet_pointer = RtbRowe.get_base_data_size(name_len)

        self.bt_heading[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 2,
                                                       RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_pitch[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 3,
                                                     RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_water_temp[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 5,
                                                          RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_system_temp[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 6,
                                                           RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_salinity[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 7,
                                                        RtbRowe.BYTES_FLOAT, ens_bytes)

        self.bt_roll[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 4,
                                                    RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_pressure[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 8,
                                                        RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_transducer_depth[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 9,
                                                                RtbRowe.BYTES_FLOAT, ens_bytes)

    def decode_bottom_track_adcp3_data(self, ens_bytes: list, ens_index: int, name_len: int = 8):
        """
        Decode the bottom track ADCP3 data for the Sensor data.

        :param ens_bytes: Byte array containing the ensemble data.
        :param ens_index: Ensemble index in the file.
        :param name_len: Length of the name of the dataset.
        """
        # Determine where to start in the ensemble data
        packet_pointer = RtbRowe.get_base_data_size(name_len)

        # Get the number of beams
        num_beams = int(RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 12, RtbRowe.BYTES_FLOAT, ens_bytes))

        # 14 raw values plus 15 values for each beam
        data_index = 14 + (15 * num_beams)

        self.bt_hs1_temp[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * (data_index + 1),
                                                        RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_hs2_temp[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * (data_index + 2),
                                                        RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_rcv1_temp[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * (data_index + 3),
                                                         RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_rcv2_temp[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * (data_index + 4),
                                                         RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_vinf[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * (data_index + 5),
                                                    RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_vg[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * (data_index + 6),
                                                  RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_vt[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * (data_index + 7),
                                                  RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_vtl[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * (data_index + 8),
                                                   RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_d3v3[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * (data_index + 9),
                                                    RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_sounder_range[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * (data_index + 11),
                                                             RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_sounder_snr[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * (data_index + 12),
                                                           RtbRowe.BYTES_FLOAT, ens_bytes)
        self.bt_sounder_amp[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * (data_index + 13),
                                                           RtbRowe.BYTES_FLOAT, ens_bytes)

    def decode_vert_rt(self, ens_bytes: list, ens_index: int, name_len: int = 8):

        # Determine where to start in the ensemble data
        packet_pointer = RtbRowe.get_base_data_size(name_len)

        # Get the number of beams
        num_beams = int(RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 0, RtbRowe.BYTES_FLOAT, ens_bytes))

        if num_beams == 1:
            self.vert_beam_RSSI_amp[ens_index] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 1,
                                                                    RtbRowe.BYTES_FLOAT, ens_bytes))
            self.vert_beam_range_m[ens_index] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 2,
                                                                   RtbRowe.BYTES_FLOAT, ens_bytes))
            self.vert_beam_eval_amp[ens_index] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 4,
                                                                    RtbRowe.BYTES_FLOAT, ens_bytes))
            self.vert_beam_gain[ens_index] = 'L'
            self.vert_beam_status[ens_index] = 1


class BT:
    """
    Bottom Tracking used to measure the depth and vessel speed (Speed over Ground).
    """
    def __init__(self, num_ens: int, num_beams: int):
        """
        Set the flag if using PD0 format data.
        If using PD0 format, then the beams will be rearranged to match PD0 beam order
        and the scale will change from percentage to counts.
        The value has to be converted from
        :param num_ens: Number of ensembles.
        :param num_beams: Number of velocity beams.

        """
        self.num_beams = 0

        self.corr = RtbRowe.nans([num_beams, num_ens])
        self.depth_m = RtbRowe.nans([num_beams, num_ens])
        self.eval_amp = RtbRowe.nans([num_beams, num_ens])
        self.ext_depth_cm = RtbRowe.nans(num_ens)
        self.pergd = RtbRowe.nans([num_beams, num_ens])
        self.rssi = RtbRowe.nans([num_beams, num_ens])
        self.snr = RtbRowe.nans([num_beams, num_ens])
        self.vel_mps = RtbRowe.nans([num_beams, num_ens])
        self.instr_vel = RtbRowe.nans([num_beams, num_ens])
        self.instr_good = RtbRowe.nans([num_beams, num_ens])
        self.earth_vel = RtbRowe.nans([num_beams, num_ens])
        self.earth_good = RtbRowe.nans([num_beams, num_ens])
        self.pulse_coh_snr = RtbRowe.nans([num_beams, num_ens])
        self.pulse_coh_amp = RtbRowe.nans([num_beams, num_ens])
        self.pulse_coh_vel = RtbRowe.nans([num_beams, num_ens])
        self.pulse_coh_noise = RtbRowe.nans([num_beams, num_ens])
        self.pulse_coh_corr = RtbRowe.nans([num_beams, num_ens])

    def decode(self, ens_bytes: list, ens_index: int, name_len: int = 8):
        """
        Decode the ensemble data for the Bottom Traack data.

        Initialize the list of Bottom Track data.  [beam]

        :param ens_bytes: Byte array containing the Bottom Track data.
        :param ens_index: Ensemble index to store the data.
        :param name_len: Length of the name of the dataset.
        """
        # Determine where to start in the ensemble data
        packet_pointer = RtbRowe.get_base_data_size(name_len)

        # Get the number of beams
        self.num_beams = int(RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 12,
                                               RtbRowe.BYTES_FLOAT, ens_bytes))

        # Get the ping count
        # Value stored in Cfg but needed for conversion to PD0
        # bt_actual_ping_count = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 13,
        #                                         RtbRowe.BYTES_FLOAT, ens_bytes)

        # Initialize the array
        snr = np.empty(shape=[self.num_beams])
        depth = np.empty(shape=[self.num_beams])
        amp = np.empty(shape=[self.num_beams])
        corr = np.empty(shape=[self.num_beams])
        beam_vel = np.empty(shape=[self.num_beams])
        beam_good = np.empty(shape=[self.num_beams])
        instr_vel = np.empty(shape=[self.num_beams])
        instr_good = np.empty(shape=[self.num_beams])
        earth_vel = np.empty(shape=[self.num_beams])
        earth_good = np.empty(shape=[self.num_beams])
        pulse_coh_snr = np.empty(shape=[self.num_beams])
        pulse_coh_amp = np.empty(shape=[self.num_beams])
        pulse_coh_vel = np.empty(shape=[self.num_beams])
        pulse_coh_noise = np.empty(shape=[self.num_beams])
        pulse_coh_corr = np.empty(shape=[self.num_beams])

        # Index to start at for the following data
        index = 14

        # Range Values
        for beam in range(self.num_beams):
            # Get the value
            value = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            # Store RTB data
            depth[beam] = value
            # Increment for the next beam
            index += 1

        # Add the data the numpy array [:num_beams, ens_index]
        self.depth_m[:self.num_beams, ens_index] = depth.T

        # SNR values
        for beam in range(self.num_beams):
            # Get the value
            value = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            snr[beam] = value

            # Increment for the next beam
            index += 1

        # Add the data the numpy array [:num_beams, ens_index]
        self.snr[:self.num_beams, ens_index] = snr.T

        # Amplitude values
        for beam in range(self.num_beams):
            # Get the value
            value = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            amp[beam] = value

            # Increment for the next beam
            index += 1

        # Add the data the numpy array [:num_beams, ens_index]
        self.rssi[:self.num_beams, ens_index] = amp.T

        # Correlation values
        for beam in range(self.num_beams):
            # Get the value
            value = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            corr[beam] = value

            # Increment for the next beam
            index += 1

        # Add the data the numpy array [:num_beams, ens_index]
        self.corr[:self.num_beams, ens_index] = corr.T

        # Beam Velocity values
        for beam in range(self.num_beams):
            # Get the value
            value = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)

            # Check for bad velocity and convert
            if RtbRowe.is_bad_velocity(value):
                value = np.nan

            beam_vel[beam] = value
            # Increment for the next beam
            index += 1

        # Add the data the numpy array [:num_beams, ens_index]
        self.vel_mps[:self.num_beams, ens_index] = beam_vel.T

        # Beam Good Pings values
        for beam in range(self.num_beams):
            # Get the value
            value = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            beam_good[beam] = int(value)

            # Increment for the next beam
            index += 1

        # Add the data the numpy array [:num_beams, ens_index]
        self.pergd[:self.num_beams, ens_index] = beam_good.T

        # Instrument Velocity values
        for beam in range(self.num_beams):
            # Get the value
            value = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)

            # Check for bad velocity and convert
            if RtbRowe.is_bad_velocity(value):
                value = np.nan

            instr_vel[beam] = value
            # Increment for the next beam
            index += 1

        # Add the data the numpy array [:num_beams, ens_index]
        self.instr_vel[:self.num_beams, ens_index] = instr_vel.T

        # Instrument Good Pings values
        for beam in range(self.num_beams):
            # Get the value
            value = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            instr_good[beam] = int(value)
            # Increment for the next beam
            index += 1

        # Add the data the numpy array [:num_beams, ens_index]
        self.instr_good[:self.num_beams, ens_index] = instr_good.T

        # Earth Velocity values
        for beam in range(self.num_beams):
            # Get the value
            value = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)

            # Check for bad velocity and convert
            if RtbRowe.is_bad_velocity(value):
                value = np.nan

            earth_vel[beam] = -value

            # Increment for the next beam
            index += 1

        # Add the data the numpy array [:num_beams, ens_index]
        self.earth_vel[:self.num_beams, ens_index] = earth_vel.T
        self.vel_mps[:self.num_beams, ens_index] = earth_vel.T

        # Earth Good Pings values
        for beam in range(self.num_beams):
            # Get the value
            value = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)

            earth_good[beam] = int(value)

            # Increment for the next beam
            index += 1

        # Add the data the numpy array [:num_beams, ens_index]
        self.earth_good[:self.num_beams, ens_index] = earth_good.T

        # Pulse Coherent SNR values
        for beam in range(self.num_beams):
            pulse_coh_snr[beam] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT,
                                                    ens_bytes)
            index += 1

        # Add the data the numpy array [:num_beams, ens_index]
        self.pulse_coh_snr[:self.num_beams, ens_index] = pulse_coh_snr.T

        # Pulse Coherent Amplitude values
        for beam in range(self.num_beams):
            pulse_coh_amp[beam] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT,
                                                    ens_bytes)
            index += 1

        # Add the data the numpy array [:num_beams, ens_index]
        self.pulse_coh_amp[:self.num_beams, ens_index] = pulse_coh_amp.T

        # Pulse Coherent Velocity values
        for beam in range(self.num_beams):
            pulse_coh_vel[beam] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT,
                                                    ens_bytes)
            index += 1

        # Add the data the numpy array [:num_beams, ens_index]
        self.pulse_coh_vel[:self.num_beams, ens_index] = pulse_coh_vel.T

        # Pulse Coherent Noise values
        for beam in range(self.num_beams):
            pulse_coh_noise[beam] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT,
                                                      ens_bytes)
            index += 1

        # Add the data the numpy array [:num_beams, ens_index]
        self.pulse_coh_noise[:self.num_beams, ens_index] = pulse_coh_noise.T

        # Pulse Coherent Correlation values
        for beam in range(self.num_beams):
            pulse_coh_corr[beam] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT,
                                                     ens_bytes)
            index += 1

        # Add the data the numpy array [:num_beams, ens_index]
        self.pulse_coh_corr[:self.num_beams, ens_index] = pulse_coh_corr.T


class RT:
    """
    Range Tracking values to measure the surface when upward looking.
    When downward looking, values are used as an echo sounder using
    the profile ping.
    """
    def __init__(self, num_ens: int, num_beams: int):
        """
        Set the flag if using PD0 format data.
        If using PD0 format, then the beams will be rearranged to match PD0 beam order
        and the scale will change from percentage to counts.
        The value has to be converted from

        :param num_ens: Number of ensembles.
        :param num_beams: Number of velocity beams.

        """
        self.num_beams = 0
        self.snr = RtbRowe.nans([num_beams, num_ens])
        self.depth = RtbRowe.nans([num_beams, num_ens])
        self.pings = RtbRowe.nans([num_beams, num_ens])
        self.amp = RtbRowe.nans([num_beams, num_ens])
        self.corr = RtbRowe.nans([num_beams, num_ens])
        self.beam_vel = RtbRowe.nans([num_beams, num_ens])
        self.instr_vel = RtbRowe.nans([num_beams, num_ens])
        self.earth_vel = RtbRowe.nans([num_beams, num_ens])

    def decode(self, ens_bytes: list, ens_index: int, name_len: int = 8):
        """
        Decode the ensemble data for the Range Tracking data.

        Initialize the list of Range Tracking data.  [beam]

        :param ens_bytes: Byte array containing the ensemble data.
        :param ens_index: Ensemble Index.
        :param name_len: Length of the name of the dataset.
        """
        # Determine where to start in the ensemble data
        packet_pointer = RtbRowe.get_base_data_size(name_len)

        # Get the number of beams
        self.num_beams = int(RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 0, RtbRowe.BYTES_FLOAT,
                                               ens_bytes))

        # Initialize the array
        snr = np.empty(shape=[self.num_beams], dtype=np.float)
        depth = np.empty(shape=[self.num_beams], dtype=np.float)
        pings = np.empty(shape=[self.num_beams], dtype=np.float)
        amp = np.empty(shape=[self.num_beams], dtype=np.float)
        corr = np.empty(shape=[self.num_beams], dtype=np.float)
        beam_vel = np.empty(shape=[self.num_beams], dtype=np.float)
        instr_vel = np.empty(shape=[self.num_beams], dtype=np.float)
        earth_vel = np.empty(shape=[self.num_beams], dtype=np.float)

        if self.num_beams == 4:
            snr[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 1, RtbRowe.BYTES_FLOAT, ens_bytes))
            snr[1] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 2, RtbRowe.BYTES_FLOAT, ens_bytes))
            snr[2] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 3, RtbRowe.BYTES_FLOAT, ens_bytes))
            snr[3] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 4, RtbRowe.BYTES_FLOAT, ens_bytes))

            depth[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 5, RtbRowe.BYTES_FLOAT, ens_bytes))
            depth[1] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 6, RtbRowe.BYTES_FLOAT, ens_bytes))
            depth[2] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 7, RtbRowe.BYTES_FLOAT, ens_bytes))
            depth[3] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 8, RtbRowe.BYTES_FLOAT, ens_bytes))

            pings[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 9, RtbRowe.BYTES_FLOAT, ens_bytes))
            pings[1] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 10, RtbRowe.BYTES_FLOAT, ens_bytes))
            pings[2] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 11, RtbRowe.BYTES_FLOAT, ens_bytes))
            pings[3] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 12, RtbRowe.BYTES_FLOAT, ens_bytes))

            amp[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 13, RtbRowe.BYTES_FLOAT, ens_bytes))
            amp[1] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 14, RtbRowe.BYTES_FLOAT, ens_bytes))
            amp[2] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 15, RtbRowe.BYTES_FLOAT, ens_bytes))
            amp[3] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 16, RtbRowe.BYTES_FLOAT, ens_bytes))

            corr[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 17, RtbRowe.BYTES_FLOAT, ens_bytes))
            corr[1] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 18, RtbRowe.BYTES_FLOAT, ens_bytes))
            corr[2] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 19, RtbRowe.BYTES_FLOAT, ens_bytes))
            corr[3] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 20, RtbRowe.BYTES_FLOAT, ens_bytes))

            beam_vel[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 21, RtbRowe.BYTES_FLOAT, ens_bytes))
            beam_vel[1] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 22, RtbRowe.BYTES_FLOAT, ens_bytes))
            beam_vel[2] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 23, RtbRowe.BYTES_FLOAT, ens_bytes))
            beam_vel[3] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 24, RtbRowe.BYTES_FLOAT, ens_bytes))

            instr_vel[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 25, RtbRowe.BYTES_FLOAT,
                                              ens_bytes))
            instr_vel[1] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 26, RtbRowe.BYTES_FLOAT,
                                              ens_bytes))
            instr_vel[2] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 27, RtbRowe.BYTES_FLOAT,
                                              ens_bytes))
            instr_vel[3] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 28, RtbRowe.BYTES_FLOAT,
                                              ens_bytes))

            earth_vel[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 29, RtbRowe.BYTES_FLOAT,
                                              ens_bytes))
            earth_vel[1] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 30, RtbRowe.BYTES_FLOAT,
                                              ens_bytes))
            earth_vel[2] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 31, RtbRowe.BYTES_FLOAT,
                                              ens_bytes))
            earth_vel[3] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 32, RtbRowe.BYTES_FLOAT,
                                              ens_bytes))
        elif self.num_beams == 3:
            snr[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 1, RtbRowe.BYTES_FLOAT, ens_bytes))
            snr[1] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 2, RtbRowe.BYTES_FLOAT, ens_bytes))
            snr[2] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 3, RtbRowe.BYTES_FLOAT, ens_bytes))

            depth[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 4, RtbRowe.BYTES_FLOAT, ens_bytes))
            depth[1] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 5, RtbRowe.BYTES_FLOAT, ens_bytes))
            depth[2] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 6, RtbRowe.BYTES_FLOAT, ens_bytes))

            pings[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 7, RtbRowe.BYTES_FLOAT, ens_bytes))
            pings[1] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 8, RtbRowe.BYTES_FLOAT, ens_bytes))
            pings[2] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 9, RtbRowe.BYTES_FLOAT, ens_bytes))

            amp[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 10, RtbRowe.BYTES_FLOAT, ens_bytes))
            amp[1] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 11, RtbRowe.BYTES_FLOAT, ens_bytes))
            amp[2] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 12, RtbRowe.BYTES_FLOAT, ens_bytes))

            corr[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 13, RtbRowe.BYTES_FLOAT, ens_bytes))
            corr[1] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 14, RtbRowe.BYTES_FLOAT, ens_bytes))
            corr[2] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 15, RtbRowe.BYTES_FLOAT, ens_bytes))

            beam_vel[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 16, RtbRowe.BYTES_FLOAT, ens_bytes))
            beam_vel[1] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 17, RtbRowe.BYTES_FLOAT, ens_bytes))
            beam_vel[2] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 18, RtbRowe.BYTES_FLOAT, ens_bytes))

            instr_vel[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 19, RtbRowe.BYTES_FLOAT,
                                              ens_bytes))
            instr_vel[1] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 20, RtbRowe.BYTES_FLOAT,
                                              ens_bytes))
            instr_vel[2] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 21, RtbRowe.BYTES_FLOAT,
                                              ens_bytes))

            earth_vel[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 22, RtbRowe.BYTES_FLOAT,
                                              ens_bytes))
            earth_vel[1] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 23, RtbRowe.BYTES_FLOAT,
                                              ens_bytes))
            earth_vel[2] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 24, RtbRowe.BYTES_FLOAT,
                                              ens_bytes))
        elif self.num_beams == 2:
            snr[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 1, RtbRowe.BYTES_FLOAT, ens_bytes))
            snr[1] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 2, RtbRowe.BYTES_FLOAT, ens_bytes))

            depth[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 3, RtbRowe.BYTES_FLOAT, ens_bytes))
            depth[1] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 4, RtbRowe.BYTES_FLOAT, ens_bytes))

            pings[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 5, RtbRowe.BYTES_FLOAT, ens_bytes))
            pings[1] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 6, RtbRowe.BYTES_FLOAT, ens_bytes))

            amp[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 7, RtbRowe.BYTES_FLOAT, ens_bytes))
            amp[1] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 8, RtbRowe.BYTES_FLOAT, ens_bytes))

            corr[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 9, RtbRowe.BYTES_FLOAT, ens_bytes))
            corr[1] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 10, RtbRowe.BYTES_FLOAT, ens_bytes))

            beam_vel[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 11, RtbRowe.BYTES_FLOAT, ens_bytes))
            beam_vel[1] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 12, RtbRowe.BYTES_FLOAT, ens_bytes))

            instr_vel[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 13, RtbRowe.BYTES_FLOAT,
                                              ens_bytes))
            instr_vel[1] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 14, RtbRowe.BYTES_FLOAT,
                                              ens_bytes))

            earth_vel[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 15, RtbRowe.BYTES_FLOAT,
                                              ens_bytes))
            earth_vel[1] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 16, RtbRowe.BYTES_FLOAT,
                                              ens_bytes))
        elif self.num_beams == 1:
            snr[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 1, RtbRowe.BYTES_FLOAT, ens_bytes))
            depth[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 2, RtbRowe.BYTES_FLOAT, ens_bytes))
            pings[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 3, RtbRowe.BYTES_FLOAT, ens_bytes))
            amp[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 4, RtbRowe.BYTES_FLOAT, ens_bytes))
            corr[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 5, RtbRowe.BYTES_FLOAT, ens_bytes))
            beam_vel[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 6, RtbRowe.BYTES_FLOAT, ens_bytes))
            instr_vel[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 7, RtbRowe.BYTES_FLOAT, ens_bytes))
            earth_vel[0] = (RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 8, RtbRowe.BYTES_FLOAT, ens_bytes))

        # Add the data the numpy array [:num_beams, ens_index]
        self.snr[:self.num_beams, ens_index] = snr.T
        self.depth[:self.num_beams, ens_index] = depth.T
        self.pings[:self.num_beams, ens_index] = pings.T
        self.amp[:self.num_beams, ens_index] = amp.T
        self.corr[:self.num_beams, ens_index] = corr.T
        self.beam_vel[:self.num_beams, ens_index] = beam_vel.T
        self.instr_vel[:self.num_beams, ens_index] = instr_vel.T
        self.earth_vel[:self.num_beams, ens_index] = earth_vel.T


class Gage:
    """
    Gage Height data from the ensemble dataset.
    """
    def __init__(self, num_ens: int):
        """
        Initialize all the values.

        Initializing the lists as list and converting
        to numpy array after data is decoded.
        :param num_ens: Number of ensembles in the file.
        """

        self.status = RtbRowe.nans(num_ens)
        self.avg_range = RtbRowe.nans(num_ens)
        self.sd = RtbRowe.nans(num_ens)
        self.avg_sn = RtbRowe.nans(num_ens)
        self.n = RtbRowe.nans(num_ens)
        self.salinity = RtbRowe.nans(num_ens)
        self.pressure = RtbRowe.nans(num_ens)
        self.depth = RtbRowe.nans(num_ens)
        self.water_temp = RtbRowe.nans(num_ens)
        self.backplane_temp = RtbRowe.nans(num_ens)
        self.speed_of_sound = RtbRowe.nans(num_ens)
        self.heading = RtbRowe.nans(num_ens)
        self.pitch = RtbRowe.nans(num_ens)
        self.roll = RtbRowe.nans(num_ens)
        self.avg_s = RtbRowe.nans(num_ens)
        self.avg_n1 = RtbRowe.nans(num_ens)
        self.avg_n2 = RtbRowe.nans(num_ens)
        self.gain_frac = RtbRowe.nans(num_ens)

        self.pings = RtbRowe.nans(num_ens)
        self.snr_thresh = RtbRowe.nans(num_ens)
        self.gain_thresh = RtbRowe.nans(num_ens)
        self.stat_thresh = RtbRowe.nans(num_ens)
        self.xmt_cycles = RtbRowe.nans(num_ens)
        self.depth_offset = RtbRowe.nans(num_ens)

    def decode_data(self, ens_bytes: list, ens_index: int, name_len: int = 8):
        """
        Decode the ancillary data for the Configuration data.

        :param ens_bytes: Byte array containing the ensemble data.
        :param ens_index: Index into array.
        :param name_len: Length of the name of the dataset.

        Parameters
        ----------
        ens_bytes
        ens_index
        name_len
        """
        # Determine where to start in the ensemble data
        packet_pointer = RtbRowe.get_base_data_size(name_len)

        self.status[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 0, RtbRowe.BYTES_FLOAT,
                                                   ens_bytes)
        self.avg_range[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 1, RtbRowe.BYTES_FLOAT,
                                                      ens_bytes)
        self.sd[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 2, RtbRowe.BYTES_FLOAT, ens_bytes)
        self.avg_sn[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 3, RtbRowe.BYTES_FLOAT,
                                                   ens_bytes)
        self.n[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 4, RtbRowe.BYTES_FLOAT, ens_bytes)
        self.salinity[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 5, RtbRowe.BYTES_FLOAT,
                                                     ens_bytes)
        self.pressure[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 6, RtbRowe.BYTES_FLOAT,
                                                     ens_bytes)
        self.depth[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 7, RtbRowe.BYTES_FLOAT,
                                                  ens_bytes)
        self.water_temp[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 8, RtbRowe.BYTES_FLOAT,
                                                       ens_bytes)
        self.backplane_temp[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 9,
                                                           RtbRowe.BYTES_FLOAT, ens_bytes)
        self.speed_of_sound[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 10,
                                                           RtbRowe.BYTES_FLOAT, ens_bytes)
        self.heading[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 11, RtbRowe.BYTES_FLOAT,
                                                    ens_bytes)
        self.pitch[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 12, RtbRowe.BYTES_FLOAT,
                                                  ens_bytes)
        self.roll[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 13, RtbRowe.BYTES_FLOAT,
                                                 ens_bytes)
        self.avg_s[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 14, RtbRowe.BYTES_FLOAT,
                                                  ens_bytes)
        self.avg_n1[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 15, RtbRowe.BYTES_FLOAT,
                                                   ens_bytes)
        self.avg_n2[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 16, RtbRowe.BYTES_FLOAT,
                                                   ens_bytes)
        self.gain_frac[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 17, RtbRowe.BYTES_FLOAT,
                                                      ens_bytes)
        self.pings[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 18, RtbRowe.BYTES_FLOAT,
                                                  ens_bytes)
        self.snr_thresh[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 19, RtbRowe.BYTES_FLOAT,
                                                       ens_bytes)
        self.gain_thresh[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 20, RtbRowe.BYTES_FLOAT,
                                                        ens_bytes)
        self.stat_thresh[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 21, RtbRowe.BYTES_FLOAT,
                                                        ens_bytes)
        self.xmt_cycles[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 22, RtbRowe.BYTES_FLOAT,
                                                       ens_bytes)
        self.depth_offset[ens_index] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 23, RtbRowe.BYTES_FLOAT,
                                                         ens_bytes)


class RiverBT:
    """
    River Bottom Track data from the ensemble dataset.
    """
    def __init__(self, num_ens: int, num_subsystems: int):
        """
        Initialize all the values.

        Initializing the lists as list and converting
        to numpy array after data is decoded.
        :param num_ens: Number of ensembles in the file.
        """
        self.num_subsystems = RtbRowe.nans(num_ens)                                  # Number of subsystems to decode
        self.ping_count = RtbRowe.nans([num_ens, num_subsystems])                    # Pings averaged
        self.status = RtbRowe.nans([num_ens, num_subsystems])                        # Data status
        self.beams = RtbRowe.nans([num_ens, num_subsystems])                         # Number of beams
        self.nce = RtbRowe.nans([num_ens, num_subsystems])                           # Number of code elements
        self.repeats_n = RtbRowe.nans([num_ens, num_subsystems])                     # Number of code repeats
        self.cpce = RtbRowe.nans([num_ens, num_subsystems])                          # Codes per code elements
        self.bb = RtbRowe.nans([num_ens, num_subsystems])                            # Broadband
        self.ll = RtbRowe.nans([num_ens, num_subsystems])
        self.beam_mux = RtbRowe.nans([num_ens, num_subsystems])                      # Beam Mux setup
        self.nb = RtbRowe.nans([num_ens, num_subsystems])                            # Narrowband
        self.ping_sec = RtbRowe.nans([num_ens, num_subsystems])                      # Ping time in seconds
        self.heading = RtbRowe.nans([num_ens, num_subsystems])                       # Heading 0 to 360
        self.pitch = RtbRowe.nans([num_ens, num_subsystems])                         # Pitch -90 to 90
        self.roll = RtbRowe.nans([num_ens, num_subsystems])                          # Roll -180 to 180
        self.water_temp = RtbRowe.nans([num_ens, num_subsystems])                    # Water Temperature in C
        self.backplane_temp = RtbRowe.nans([num_ens, num_subsystems])                # Internal System temperature in C
        self.salinity = RtbRowe.nans([num_ens, num_subsystems])                      # Salinity in PPT
        self.pressure = RtbRowe.nans([num_ens, num_subsystems])                      # Pressure in Pascal
        self.depth = RtbRowe.nans([num_ens, num_subsystems])                         # Pressure converted to m
        self.speed_of_sound = RtbRowe.nans([num_ens, num_subsystems])                # Speed of Sound in m/s
        self.mx = RtbRowe.nans([num_ens, num_subsystems])
        self.my = RtbRowe.nans([num_ens, num_subsystems])
        self.mz = RtbRowe.nans([num_ens, num_subsystems])
        self.gp = RtbRowe.nans([num_ens, num_subsystems])
        self.gr = RtbRowe.nans([num_ens, num_subsystems])
        self.gz = RtbRowe.nans([num_ens, num_subsystems])
        self.samples_per_sec = RtbRowe.nans([num_ens, num_subsystems])            # Samples per second
        self.system_freq_hz = RtbRowe.nans([num_ens, num_subsystems])             # System frequency in Hz
        self.bt_range = RtbRowe.nans([num_ens, num_subsystems])                   # Bottom Track Range in m
        self.bt_snr = RtbRowe.nans([num_ens, num_subsystems])                     # Bottom Track SNR in dB
        self.bt_amp = RtbRowe.nans([num_ens, num_subsystems])                     # Bottom Track Amplitude in dB
        self.bt_noise_amp_bp = RtbRowe.nans([num_ens, num_subsystems])            # Noise in Amplitude Back Porch
        self.bt_noise_amp_fp = RtbRowe.nans([num_ens, num_subsystems])            # Noise in Amplitude Front Porch
        self.bt_corr = RtbRowe.nans([num_ens, num_subsystems])                    # Bottom Track Correlation in fraction
        self.vel = RtbRowe.nans([num_ens, num_subsystems])                        # Bottom Track Beam Velocity in m/s
        self.beam_n = RtbRowe.nans([num_ens, num_subsystems])

    def decode_data(self, ens_bytes: list, ens_index: int, name_len: int = 8):
        """
        Decode the River Bottom data data.

        :param ens_bytes: Byte array containing the ensemble data.
        :param ens_index: Ensemble index in the file.
        :param name_len: Length of the name of the dataset.
        """

        # Determine where to start in the ensemble data
        packet_pointer = RtbRowe.get_base_data_size(name_len)

        num_subsystems = int(RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * 0, RtbRowe.BYTES_FLOAT,
                                               ens_bytes))
        self.num_subsystems[ens_index] = num_subsystems

        # Start of the data
        index = 1

        # Create a temp list to hold all the values for each subsystem
        # Accumulate the list then add it to the data type
        # Index will keep track of where we are located in the data
        ping_count = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            ping_count[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT,
                                               ens_bytes)
            index += 1
        self.ping_count[ens_index, :num_subsystems] = ping_count.T

        status = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            status[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.status[ens_index, :num_subsystems] = status.T

        beams = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            beams[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.beams[ens_index, :num_subsystems] = beams.T

        nce = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            nce[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.nce[ens_index, :num_subsystems] = nce.T

        repeats_n = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            repeats_n[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT,
                                              ens_bytes)
            index += 1
        self.repeats_n[ens_index, :num_subsystems] = repeats_n.T

        cpce = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            cpce[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.cpce[ens_index, :num_subsystems] = cpce.T

        bb = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            bb[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.bb[ens_index, :num_subsystems] = bb.T

        ll = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            ll[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.ll[ens_index, :num_subsystems] = ll.T

        beam_mux = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            beam_mux[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT,
                                             ens_bytes)
            index += 1
        self.beam_mux[ens_index, :num_subsystems] = beam_mux.T

        nb = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            nb[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.nb[ens_index, :num_subsystems] = nb.T

        ps = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            ps[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.ping_sec[ens_index, :num_subsystems] = ps.T

        hdg = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            hdg[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.heading[ens_index, :num_subsystems] = hdg.T

        ptch = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            ptch[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.pitch[ens_index, :num_subsystems] = ptch.T

        roll = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            roll[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.roll[ens_index, :num_subsystems] = roll.T

        wt = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            wt[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.water_temp[ens_index, :num_subsystems] = wt.T

        sys_temp = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            sys_temp[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT,
                                             ens_bytes)
            index += 1
        self.backplane_temp[ens_index, :num_subsystems] = sys_temp.T

        sal = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            sal[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.salinity[ens_index, :num_subsystems] = sal.T

        pres = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            pres[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.pressure[ens_index, :num_subsystems] = pres.T

        depth = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            depth[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.depth[ens_index, :num_subsystems] = depth.T

        sos = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            sos[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.speed_of_sound[ens_index, :num_subsystems] = sos.T

        mx = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            mx[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.mx[ens_index, :num_subsystems] = mx.T

        my = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            my[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.my[ens_index, :num_subsystems] = my.T

        mz = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            mz[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.mz[ens_index, :num_subsystems] = mz.T

        gp = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            gp[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.gp[ens_index, :num_subsystems] = gp.T

        gr = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            gr[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.gr[ens_index, :num_subsystems] = gr.T

        gz = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            gz[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.gz[ens_index, :num_subsystems] = gz.T

        sps = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            sps[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.samples_per_sec[ens_index, :num_subsystems] = sps.T

        freq = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            freq[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.system_freq_hz[ens_index, :num_subsystems] = freq.T

        bt_range = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            bt_range[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT,
                                             ens_bytes)
            index += 1
        self.bt_range[ens_index, :num_subsystems] = bt_range.T

        snr = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            snr[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.bt_snr[ens_index, :num_subsystems] = snr.T

        amp = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            amp[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.bt_amp[ens_index, :num_subsystems] = amp.T

        noise_bp = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            noise_bp[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT,
                                             ens_bytes)
            index += 1
        self.bt_noise_amp_bp[ens_index, :num_subsystems] = noise_bp.T

        noise_fp = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            noise_fp[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT,
                                             ens_bytes)
            index += 1
        self.bt_noise_amp_fp[ens_index, :num_subsystems] = noise_fp.T

        corr = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            corr[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.bt_corr[ens_index, :num_subsystems] = corr.T

        vel = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            vel[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.vel[ens_index, :num_subsystems] = vel.T

        beam_n = np.empty(shape=[num_subsystems], dtype=np.float)
        for sb in range(num_subsystems):
            beam_n[sb] = RtbRowe.get_float(packet_pointer + RtbRowe.BYTES_FLOAT * index, RtbRowe.BYTES_FLOAT, ens_bytes)
            index += 1
        self.beam_n[ens_index, :num_subsystems] = beam_n.T


class Surface:
    """
    Surf data are to accommodate RiverRay and RiverPro.  pd0_read sets these
    values to nan when reading Rio Grande or StreamPro data
    """

    def __init__(self, num_ens: int, num_beams: int, max_surface_bins: int):
        """
        Initialize all the values.

        :param num_ens: Number of ensembles in the file.
        :param num_beams: Number of beams on the system.
        :param max_surface_bins: Number of surface bins.
        """
        self.no_cells = RtbRowe.nans(num_ens)                                       # Number of surface cells in the
        # ensemble
        self.cell_size_cm = RtbRowe.nans(num_ens)                                   # Cell size in cm
        self.dist_bin1_cm = RtbRowe.nans(num_ens)                                   # Distance to center of cell 1 in cm
        self.vel_mps = np.tile([np.nan], [num_beams, max_surface_bins, num_ens])    # 3D array of velocity data in each
        # cell and ensemble
        self.corr = RtbRowe.nans([num_beams, max_surface_bins, num_ens])            # 3D array of correlation data for
        # each beam, cell, and ensemble
        self.pergd = RtbRowe.nans([num_beams, max_surface_bins, num_ens])           # 3D array of percent good data for
        # each beam, cell, and ensemble
        self.rssi = RtbRowe.nans([num_beams, max_surface_bins, num_ens])            # 3D array of signal strength data
        # for each beam, cell, and ensemble


class Nmea:
    """
    NMEA data from the ensemble dataset.
    Store the raw NMEA strings.
    Also store the last NMEA values in the message.
    """
    def __init__(self, num_ens: int):
        """
        Initialize all the values.

        Initializing the lists as list and converting
        to numpy array after data is decoded.

        :param num_ens: Number of ensembles in the file.
        """

        self.gga = [''] * num_ens
        self.gsa = [''] * num_ens
        self.vtg = [''] * num_ens
        self.dbt = [''] * num_ens
        self.hdt = [''] * num_ens

        # GGA
        self.gga_delta_time = RtbRowe.nans(num_ens)            # float
        self.gga_header = RtbRowe.nans(num_ens)                # str
        self.utc = RtbRowe.nans(num_ens)                       # float
        self.lat_deg = RtbRowe.nans(num_ens)                   # float
        self.lat_ref = RtbRowe.nans(num_ens)                   # str
        self.lon_deg = RtbRowe.nans(num_ens)                   # float
        self.lon_ref = RtbRowe.nans(num_ens)                   # str
        self.corr_qual = RtbRowe.nans(num_ens)                 # float
        self.num_sats = RtbRowe.nans(num_ens)                  # int
        self.hdop = RtbRowe.nans(num_ens)                      # float
        self.alt = RtbRowe.nans(num_ens)                       # float
        self.alt_unit = RtbRowe.nans(num_ens)                  # str
        self.geoid = RtbRowe.nans(num_ens)                     # str
        self.geoid_unit = RtbRowe.nans(num_ens)                # str
        self.d_gps_age = RtbRowe.nans(num_ens)                 # float
        self.ref_stat_id = RtbRowe.nans(num_ens)               # float

        # VTG
        self.vtg_delta_time = RtbRowe.nans(num_ens)            # float
        self.vtg_header = RtbRowe.nans(num_ens)                # str
        self.course_true = RtbRowe.nans(num_ens)               # float
        self.true_indicator = RtbRowe.nans(num_ens)            # str
        self.course_mag = RtbRowe.nans(num_ens)                # float
        self.mag_indicator = RtbRowe.nans(num_ens)             # str
        self.speed_knots = RtbRowe.nans(num_ens)               # float
        self.knots_indicator = RtbRowe.nans(num_ens)           # str
        self.speed_kph = RtbRowe.nans(num_ens)                 # float
        self.kph_indicator = RtbRowe.nans(num_ens)             # str
        self.mode_indicator = RtbRowe.nans(num_ens)            # str

        # HDT
        self.hdt_header = RtbRowe.nans(num_ens)
        self.heading = RtbRowe.nans(num_ens)
        self.rel_true_north = RtbRowe.nans(num_ens)

        # Used to keep track of the last nmea message to process
        self.last_gga = None
        self.last_vtg = None
        self.last_hdt = None

    def decode(self, ens_bytes: list, ens_index: int, name_len: int = 8):
        """
        Decode the NMEA dataset.  This will be the raw NMEA messages
        from the ADCP containing GPS data.
        :param ens_bytes Bytes for dataset.
        :param ens_index: Ensemble index in the file.
        :param name_len: Name length to get the start location.
        """
        # Clear the previous NMEA messages
        self.last_gga = None
        self.last_vtg = None
        self.last_hdt = None

        packet_pointer = RtbRowe.get_base_data_size(name_len)

        # Convert all the messages to a string
        nmea_str = str(ens_bytes[packet_pointer:], "UTF-8")

        # Accumulate NMEA messages
        for msg in nmea_str.split():
            self.decode_nmea(msg, ens_index)

        # Decode the last messages
        if self.last_gga:
            self.decode_gga(self.last_gga, ens_index)

        if self.last_vtg:
            self.decode_vtg(self.last_vtg, ens_index)

        if self.last_hdt:
            self.decode_hdt(self.last_hdt, ens_index)

    def decode_nmea(self, nmea_str: str, ens_index: int):
        """
        Verify the NMEA message is by checking the checksum.
        Then add the message to the list and decode each message.
        :param nmea_str NMEA string to decode.
        :param ens_index: Ensemble index in the file.
        """

        # Verify the NMEA string is good
        if Nmea.check_nmea_checksum(nmea_str):
            # Add each message to the list
            # Decode the data
            if 'gga' in nmea_str or 'GGA' in nmea_str:
                self.gga[ens_index] += nmea_str
                self.last_gga = nmea_str
            if 'gsa' in nmea_str or 'GSA' in nmea_str:
                self.gsa[ens_index] += nmea_str
            if 'vtg' in nmea_str or 'VTG' in nmea_str:
                self.vtg[ens_index] += nmea_str
                self.last_vtg = nmea_str
            if 'dbt' in nmea_str or 'DBT' in nmea_str:
                self.dbt[ens_index] += nmea_str
            if 'hdt' in nmea_str or 'HDT' in nmea_str:
                self.hdt[ens_index] += nmea_str
                self.last_hdt = nmea_str

    def decode_gga(self, nmea_str: str, ens_index: int):
        """
        Decode GGA message.  Update the variables.
        Store the last result for the ensemble.

        :param nmea_str NMEA string.
        :param ens_index: Ensemble index.
        """
        try:
            if nmea_str:
                temp_array = np.array(nmea_str.split(','))
                temp_array[temp_array == '999.9'] = ''

                # self.gga_delta_time = delta_time
                self.gga_header[ens_index] = temp_array[0]
                self.utc[ens_index] = float(temp_array[1])
                lat_str = temp_array[2]
                lat_deg = float(lat_str[0:2])
                lat_deg = lat_deg + float(lat_str[2:]) / 60
                self.lat_deg[ens_index] = lat_deg
                self.lat_ref[ens_index] = temp_array[3]
                lon_str = temp_array[4]
                lon_num = float(lon_str)
                lon_deg = np.floor(lon_num / 100)
                lon_deg = lon_deg + (((lon_num / 100.) - lon_deg) * 100.) / 60.
                self.lon_deg[ens_index] = lon_deg
                self.lon_ref[ens_index] = temp_array[5]
                self.corr_qual[ens_index] = float(temp_array[6])
                self.num_sats[ens_index] = float(temp_array[7])
                self.hdop[ens_index] = float(temp_array[8])
                self.alt[ens_index] = float(temp_array[9])
                self.alt_unit[ens_index] = temp_array[10]
                self.geoid[ens_index] = temp_array[11]
                self.geoid_unit[ens_index] = temp_array[12]
                self.d_gps_age[ens_index] = float(temp_array[13])
                idx_star = temp_array[14].find('*')
                self.ref_stat_id[ens_index] = float(temp_array[15][:idx_star])

        except (ValueError, EOFError, IndexError):
            pass

    def decode_vtg(self, nmea_str: str, ens_index: int):
        """
        Decode the VTG message and set all the variables.
        Decode the last message.

        :param nmea_str: NMEA string.
        :param ens_index: Ensemble index.
        """
        try:
            if nmea_str:
                temp_array = np.array(nmea_str.split(','))
                temp_array[temp_array == '999.9'] = ''

                # self.vtg_delta_time = delta_time
                self.vtg_header[ens_index] = temp_array[0]
                self.course_true[ens_index] = Nmea.valid_number(temp_array[1])
                self.true_indicator[ens_index] = temp_array[2]
                self.course_mag[ens_index] = Nmea.valid_number(temp_array[3])
                self.mag_indicator[ens_index] = temp_array[4]
                self.speed_knots[ens_index] = Nmea.valid_number(temp_array[5])
                self.knots_indicator[ens_index] = temp_array[6]
                self.speed_kph[ens_index] = Nmea.valid_number(temp_array[7])
                self.kph_indicator[ens_index] = temp_array[8]
                idx_star = temp_array[9].find('*')
                self.mode_indicator[ens_index] = temp_array[9][:idx_star]

        except (ValueError, EOFError, IndexError):
            pass

    def decode_hdt(self, nmea_str: str, ens_index: int):
        """
        Decode the HDT message and set all the variables.
        Decode the last message.

        :param nmea_str: NMEA string.
        :param ens_index: Ensemble Index.
        """
        try:
            if nmea_str:
                temp_array = np.array(nmea_str.split(','))
                temp_array[temp_array == '999.9'] = ''

                # self.vtg_delta_time = delta_time
                self.hdt_header[ens_index] = temp_array[0]
                self.heading[ens_index] = Nmea.valid_number(temp_array[1])
                idx_star = temp_array[2].find('*')
                self.rel_true_north[ens_index] = temp_array[2][:idx_star]

        except (ValueError, EOFError, IndexError):
            pass

    @staticmethod
    def valid_number(data_in):
        """
        Check to see if data_in can be converted to float.

        :param data_in: str String to be converted to float
        :return Returns a float of data_in or nan if conversion is not possible
        """

        try:
            data_out = float(data_in)
        except ValueError:
            data_out = np.nan
        return data_out

    @staticmethod
    def check_nmea_checksum(nmea_str: str):
        """
        Calculate the NMEA checksum.  Verify the
        checksum value matches the given value.
        :param nmea_str NMEA string.
        :return TRUE = Good checksum
        """
        try:
            # Remove newline and spaces at the end
            nmea_str = nmea_str.rstrip('\n')
            # Get the checksum value
            checksum = nmea_str[len(nmea_str) - 2:]
            checksum = int(checksum, 16)

            # Get the data from the string
            nmea_data = re.sub("(\n|\r\n)", "", nmea_str[nmea_str.find("$") + 1:nmea_str.find("*")])

            # Calculate the checksum
            calc_checksum = 0
            for c in nmea_data:
                calc_checksum ^= ord(c)
            calc_checksum = calc_checksum & 0xFF

            # Verify the checksum matches
            if calc_checksum == checksum:
                return True

            return False
        except Exception as ex:
            logging.error(ex)
            return False


class Gps(object):
    """
    Class to hold GPS data from WinRiver.
    RTB format does not include all this information.
    Specifically the velocities.  I typically use a
    geodectic calculator like pygeodesy to do these
    calculations.

    Attributes
    ----------
    alt_m: np.array(float)
        Altitude in meters
    gga_diff: np.array(int)
        Differential correction indicator
    gga_hdop: np.array(float)
        Horizontal dilution of precision
    gga_n_stats: np.array(int)
        Number of satellites
    gga_vel_e_mps: np.array(float)
        Velocity in east direction from GGA data
    gga_vel_n_mps: np.array(float)
        Velocity in north direction from GGA data
    gsa_p_dop: np.array(int)
        Position dilution of precision
    gsa_sat: np.array(int)
        Satellites
    gsa_v_dop: np.array(float)
        Vertical dilution of precision
    lat_deg: np.array(float)
        Latitude in degrees
    long_deg: np.array(float)
        Longitude in degrees
    vtg_vel_e_mps: np.array(float)
        Velocity in east direction from VTG data
    vtg_vel_n_mps: np.array(float)
        Velocity in north direction from VTG data
    """

    def __init__(self, num_ens: int):
        """
        Initialize instance variables.

        :param num_ens: Number of ensembles
        """

        self.alt_m = RtbRowe.nans(num_ens)
        self.gga_diff = RtbRowe.nans(num_ens)
        self.gga_hdop = RtbRowe.nans(num_ens)
        self.gga_n_stats = RtbRowe.nans(num_ens)
        self.gga_vel_e_mps = RtbRowe.nans(num_ens)
        self.gga_vel_n_mps = RtbRowe.nans(num_ens)
        self.gsa_p_dop = RtbRowe.nans(num_ens)
        self.gsa_sat = RtbRowe.nans([num_ens, 6])
        self.gsa_v_dop = RtbRowe.nans(num_ens)
        self.lat_deg = RtbRowe.nans(num_ens)
        self.long_deg = RtbRowe.nans(num_ens)
        self.vtg_vel_e_mps = RtbRowe.nans(num_ens)
        self.vtg_vel_n_mps = RtbRowe.nans(num_ens)

    # def decode(self, ens_bytes: list, ens_index: int, num_ens: int, name_len: int = 8):
    def decode(self, ens_bytes: list, ens_index: int, name_len: int = 8):
        """
        Decode the NMEA dataset.  This will be the raw NMEA messages
        from the ADCP containing GPS data.
        :param ens_bytes Bytes for dataset.
        :param ens_index: Ensemble index in the file.
        # :param num_ens:  Number of ensembles in the file.
        :param name_len: Name length to get the start location.
        """
        packet_pointer = RtbRowe.get_base_data_size(name_len)

        # Convert all the messages to a string
        nmea_str = str(ens_bytes[packet_pointer:], "UTF-8")

        # Decode each NMEA message
        for msg in nmea_str.split():
            # Verify the NMEA string is good
            if Nmea.check_nmea_checksum(msg):
                # Add each message to the list
                # Decode the data
                if 'gga' in msg or 'GGA' in msg:
                    self.decode_gga(nmea_str, ens_index)

    def decode_gga(self, nmea_str: str, ens_index: int):
        """
        Decode GGA message.  Update the variables.

        :param nmea_str NMEA string.
        :param ens_index: Ensemble index.
        """
        try:
            if nmea_str:
                temp_array = np.array(nmea_str.split(','))
                temp_array[temp_array == '999.9'] = ''

                # self.gga_delta_time = delta_time
                # self.gga_header.append(temp_array[0])
                # self.utc.append(float(temp_array[1]))
                lat_str = temp_array[2]
                lat_deg = float(lat_str[0:2])
                lat_deg = lat_deg + float(lat_str[2:]) / 60
                self.lat_deg[ens_index] = lat_deg
                # self.lat_ref.append(temp_array[3])
                lon_str = temp_array[4]
                lon_num = float(lon_str)
                lon_deg = np.floor(lon_num / 100)
                lon_deg = lon_deg + (((lon_num / 100.) - lon_deg) * 100.) / 60.
                self.long_deg[ens_index] = lon_deg
                # self.lon_ref.append(temp_array[5])
                self.gga_diff[ens_index] = float(temp_array[6])
                self.gga_n_stats[ens_index] = float(temp_array[7])
                self.gga_hdop[ens_index] = float(temp_array[8])
                self.alt_m[ens_index] = float(temp_array[9])
                # self.alt_unit.append(temp_array[10])
                # self.geoid.append(temp_array[11])
                # self.geoid_unit.append(temp_array[12])
                # self.d_gps_age.append(float(temp_array[13]))
                # idx_star = temp_array[14].find('*')
                # self.ref_stat_id.append(float(temp_array[15][:idx_star]))

        except (ValueError, EOFError, IndexError):
            pass


class Gps2(object):
    """Class to hold GPS data for WinRiver II.

    Attributes
    ----------
    gga_delta_time: np.array(float)
        Time between ping and gga data
    gga_header: list
        GGA header
    gga_sentence: list
        GGA sentence
    utc: np.array(float)
        UTC time
    lat_deg: np.array(float)
        Latitude in degrees
    lat_ref: list
        Latitude reference
    lon_deg: np.array(float)
        Longitude in degrees
    lon_ref: list
        Longitude reference
    corr_qual: np.array(float)
        Differential quality indicator
    num_sats: np.array(int)
        Number of satellites
    hdop: np.array(float)
        Horizontal dilution of precision
    alt: np.array(float)
        Altitude
    alt_unit: list
        Units for altitude
    geoid: np.array(float)
        Geoid height
    geoid_unit: list
        Units for geoid height
    d_gps_age: np.array(float)
        Age of differential correction
    ref_stat_id: np.array(float)
        Reference station ID
    vtg_delta_time: np.array(float)
        Time between ping and VTG data
    vtg_header: list
        VTG header
    vtg_sentence: list
        VTG sentence
    course_true: np.array(float)
        Course relative to true north
    true_indicator: list
        True north indicator
    course_mag: np.array(float)
        Course relative to magnetic north
    mag_indicator: list
        Magnetic north indicator
    speed_knots: np.array(float)
        Speed in knots
    knots_indicator: list
        Knots indicator
    speed_kph: np.array(float)
        Speed in kilometers per hour
    kph_indicator: list
        Kilometers per hour indicator
    mode_indicator: list
        Mode indicator
    dbt_delta_time: np.array(float)
        Time between ping and echo sounder data
    dbt_header: list
        Echo sounder header
    depth_ft: np.array(float)
        Depth in ft from echo sounder
    ft_indicator: list
        Feet indicator
    depth_m: np.array(float)
        Depth in meters from echo sounder
    m_indicator: list
        Meters indicator
    depth_fath: np.array(float)
        Depth in fathoms from echo sounder
    fath_indicator: list
        Fathoms indicator
    hdt_delta_time: np.array(float)
        Time between ping and external heading data
    hdt_header: list
        External heading header
    heading_deg: np.array(float)
        Heading in degrees from external heading
    h_true_indicator: list
        Heading indicator to true north
    gga_velE_mps: np.array(float)
        Velocity in east direction in m/s from GGA for WR
    gga_velN_mps: np.array(float)
        Velocity in north direction in m/s from GGA for WR
    vtg_velE_mps: np.array(float)
        Velocity in east direction in m/s from VTG for WR
    vtg_velN_mps: np.array(float)
        Velocity in north direction in m/s from VTG for WR
    """

    def __init__(self, num_ens: int):
        """
        Initialize instance variables.

        Parameters
        ----------
        :param num_ens: Number of ensembles
        """

        self.gga_delta_time = np.full([num_ens, 20], np.nan)
        self.gga_header = [x[:] for x in [[''] * 20] * num_ens]
        self.gga_sentence = [x[:] for x in [[''] * 20] * num_ens]
        self.utc = np.full([num_ens, 20], np.nan)
        self.lat_deg = np.zeros([num_ens, 20])
        # self.lat_deg = [[np.nan]] * num_ens
        self.lat_ref = [x[:] for x in [[''] * 20] * num_ens]
        self.lon_deg = np.zeros([num_ens, 20])
        self.lon_ref = [x[:] for x in [[''] * 20] * num_ens]
        self.corr_qual = np.full([num_ens, 20], np.nan)
        # self.corr_qual = [[np.nan]] * num_ens
        self.num_sats = np.full([num_ens, 20], np.nan)
        self.hdop = np.full([num_ens, 20], np.nan)
        self.alt = np.full([num_ens, 20], np.nan)
        self.alt_unit = [x[:] for x in [[''] * 20] * num_ens]
        self.geoid = np.full([num_ens, 20], np.nan)
        self.geoid_unit = [x[:] for x in [[''] * 20] * num_ens]
        self.d_gps_age = np.full([num_ens, 20], np.nan)
        self.ref_stat_id = np.full([num_ens, 20], np.nan)
        self.vtg_delta_time = np.full([num_ens, 20], np.nan)
        self.vtg_header = [x[:] for x in [[''] * 20] * num_ens]
        self.vtg_sentence = [x[:] for x in [[''] * 20] * num_ens]
        self.course_true = np.full([num_ens, 20], np.nan)
        self.true_indicator = [x[:] for x in [[''] * 20] * num_ens]
        self.course_mag = np.full([num_ens, 20], np.nan)
        self.mag_indicator = [x[:] for x in [[''] * 20] * num_ens]
        self.speed_knots = np.full([num_ens, 20], np.nan)
        self.knots_indicator = [x[:] for x in [[''] * 20] * num_ens]
        self.speed_kph = np.zeros([num_ens, 20])
        self.kph_indicator = [x[:] for x in [[''] * 20] * num_ens]
        self.mode_indicator = [x[:] for x in [[''] * 20] * num_ens]
        self.dbt_delta_time = np.full([num_ens, 20], np.nan)
        self.dbt_header = [x[:] for x in [[''] * 20] * num_ens]
        self.depth_ft = np.full([num_ens, 20], np.nan)
        self.ft_indicator = [x[:] for x in [[''] * 20] * num_ens]
        self.depth_m = np.zeros([num_ens, 20])
        self.m_indicator = [x[:] for x in [[''] * 20] * num_ens]
        self.depth_fath = np.full([num_ens, 20], np.nan)
        self.fath_indicator = [x[:] for x in [[''] * 20] * num_ens]
        self.hdt_delta_time = np.full([num_ens, 20], np.nan)
        self.hdt_header = [x[:] for x in [[''] * 20] * num_ens]
        self.heading_deg = np.full([num_ens, 20], np.nan)
        self.h_true_indicator = [x[:] for x in [[''] * 20] * num_ens]

        # if wr2:
        self.gga_velE_mps = RtbRowe.nans(num_ens)
        self.gga_velN_mps = RtbRowe.nans(num_ens)
        self.vtg_velE_mps = RtbRowe.nans(num_ens)
        self.vtg_velN_mps = RtbRowe.nans(num_ens)

        # Keep track of entries for each ensemble
        self.gga_index = 0
        self.vtg_index = 0
        self.dbt_index = 0
        self.hdt_index = 0

        # Used to calculate delta time
        self.last_gga_time = np.nan
        self.last_vtg_time = np.nan
        self.last_dbt_time = np.nan
        self.last_hdt_time = np.nan
        self.last_gga_delta_time = None

    # def decode(self, ens_bytes: list, ens_index: int, num_ens: int, name_len: int = 8):
    def decode(self, ens_bytes: list, ens_index: int, name_len: int = 8):
        """
        Decode the NMEA dataset.  This will be the raw NMEA messages
        from the ADCP containing GPS data.
        :param ens_bytes Bytes for dataset.
        :param ens_index: Ensemble index in the file.
        # :param num_ens:  Number of ensembles in the file.
        :param name_len: Name length to get the start location.
        """
        # Reset all the index for these new entries
        self.gga_index = 0
        self.vtg_index = 0
        self.dbt_index = 0
        self.hdt_index = 0

        packet_pointer = RtbRowe.get_base_data_size(name_len)

        # Convert all the messages to a string
        nmea_str_list = str(ens_bytes[packet_pointer:], "UTF-8")

        # Decode each NMEA message
        for nmea_str in nmea_str_list.split():
            # self.decode_nmea(msg, ens_index, num_ens)

            # Verify the NMEA string is good
            if Nmea.check_nmea_checksum(nmea_str):
                # Add each message to the list
                # Decode the data
                if 'gga' in nmea_str or 'GGA' in nmea_str:
                    self.decode_gga(nmea_str, ens_index)
                    self.gga_index += 1
                if 'vtg' in nmea_str or 'VTG' in nmea_str:
                    self.decode_vtg(nmea_str, ens_index)
                    self.vtg_index += 1
                if 'dbt' in nmea_str or 'DBT' in nmea_str:
                    self.decode_dbt(nmea_str, ens_index)
                    self.dbt_index += 1
                if 'hdt' in nmea_str or 'HDT' in nmea_str:
                    self.decode_hdt(nmea_str, ens_index)
                    self.hdt_index += 1

    def decode_nmea(self, nmea_str: str, ens_index: int):  # , num_ens: int):
        """
        Verify the NMEA message is by checking the checksum.
        Then add the message to the list and decode each message.
        :param nmea_str NMEA string to decode.
        :param ens_index: Ensemble index in the file.
        # :param num_ens: Number of ensembles in the file.
        """

        gga_list = []
        vtg_list = []
        dbt_list = []
        hdt_list = []

        # Verify the NMEA string is good
        if Nmea.check_nmea_checksum(nmea_str):
            # Add each message to the list
            # Decode the data
            if 'gga' in nmea_str or 'GGA' in nmea_str:
                gga_list.append(nmea_str)
                # self.decode_gga(nmea_str, ens_index)
                # self.gga_index += 1
            if 'vtg' in nmea_str or 'VTG' in nmea_str:
                vtg_list.append(nmea_str)
                # self.decode_vtg(nmea_str, ens_index)
                # self.vtg_index += 1
            if 'dbt' in nmea_str or 'DBT' in nmea_str:
                dbt_list.append(nmea_str)
                # self.decode_dbt(nmea_str, ens_index)
                # self.dbt_index += 1
            if 'hdt' in nmea_str or 'HDT' in nmea_str:
                hdt_list.append(nmea_str)
                # self.decode_hdt(nmea_str, ens_index)
                # self.hdt_index += 1

        # Initialize the array based on the number of messages found
        empty_arr = RtbRowe.nans(len(gga_list))
        self.corr_qual[ens_index] = empty_arr

    def decode_gga(self, nmea_str: str, ens_index: int):
        """
        Decode GGA message.  Update the variables.

        :param nmea_str NMEA string.
        :param ens_index: Ensemble Index in the file.
        """
        try:
            if nmea_str:
                temp_array = np.array(nmea_str.split(','))
                temp_array[temp_array == '999.9'] = ''

                self.gga_header[ens_index][self.gga_index] = temp_array[0]       # Set the Initial value
                utc_time = float(temp_array[1])
                self.utc[ens_index, self.gga_index] = utc_time
                lat_str = temp_array[2]
                lat_deg = float(lat_str[0:2])
                lat_deg = lat_deg + float(lat_str[2:]) / 60
                self.lat_deg[ens_index, self.gga_index] = lat_deg
                self.lat_ref[ens_index][self.gga_index] = temp_array[3]
                lon_str = temp_array[4]
                lon_num = float(lon_str)
                lon_deg = np.floor(lon_num / 100)
                lon_deg = lon_deg + (((lon_num / 100.) - lon_deg) * 100.) / 60.
                self.lon_deg[ens_index, self.gga_index] = lon_deg
                self.lon_ref[ens_index][self.gga_index] = temp_array[5]
                self.corr_qual[ens_index, self.gga_index] = float(temp_array[6])
                self.num_sats[ens_index, self.gga_index] = float(temp_array[7])
                self.hdop[ens_index, self.gga_index] = float(temp_array[8])
                self.alt[ens_index, self.gga_index] = float(temp_array[9])
                self.alt_unit[ens_index][self.gga_index] = temp_array[10]
                self.geoid[ens_index, self.gga_index] = temp_array[11]
                self.geoid_unit[ens_index][self.gga_index] = temp_array[12]
                if temp_array[13] != "":
                    self.d_gps_age[ens_index, self.gga_index] = float(temp_array[13])
                idx_star = temp_array[14].find('*')
                self.ref_stat_id[ens_index, self.gga_index] = float(temp_array[14][:idx_star])

                if not np.isnan(self.last_gga_time):
                    # Calculate the delta time and set the new last time
                    self.gga_delta_time[ens_index, self.gga_index] = utc_time - self.last_gga_time
                    self.last_gga_time = utc_time

                    # Since VTG, HDT and HBT do not have a timestamp
                    # I will use the GGA delta time for all the messages
                    # TODO Get a delta time for those NMEA messages
                    self.last_gga_delta_time = self.gga_delta_time[ens_index, self.gga_index]
                else:
                    self.gga_delta_time[ens_index, self.gga_index] = 0
                    self.last_gga_delta_time = 0
                    self.last_gga_time = utc_time

        except (ValueError, EOFError, IndexError):
            pass

    def decode_vtg(self, nmea_str: str, ens_index: int):
        """
        Decode the VTG message and set all the variables.

        :param nmea_str: NMEA string.
        :param ens_index: Ensemble index in the file.
        """
        try:
            if nmea_str:
                temp_array = np.array(nmea_str.split(','))
                temp_array[temp_array == '999.9'] = ''

                # self.vtg_delta_time = delta_time
                self.vtg_header[ens_index][self.vtg_index] = temp_array[0]
                self.course_true[ens_index][self.vtg_index] = Nmea.valid_number(temp_array[1])
                self.true_indicator[ens_index][self.vtg_index] = temp_array[2]
                self.course_mag[ens_index][self.vtg_index] = Nmea.valid_number(temp_array[3])
                self.mag_indicator[ens_index][self.vtg_index] = temp_array[4]
                self.speed_knots[ens_index][self.vtg_index] = Nmea.valid_number(temp_array[5])
                self.knots_indicator[ens_index][self.vtg_index] = temp_array[6]
                self.speed_kph[ens_index][self.vtg_index] = Nmea.valid_number(temp_array[7])
                self.kph_indicator[ens_index][self.vtg_index] = temp_array[8]
                idx_star = temp_array[9].find('*')
                self.mode_indicator[ens_index][self.vtg_index] = temp_array[9][:idx_star]

                # TODO Find a way to calculate this value
                if self.last_gga_delta_time:
                    self.vtg_delta_time[ens_index, self.vtg_index] = self.last_gga_delta_time
                else:
                    self.vtg_delta_time[ens_index, self.vtg_index] = 0.0

        except (ValueError, EOFError, IndexError):
            pass

    def decode_hdt(self, nmea_str: str, ens_index: int):
        """
        Decode the HDT message and set all the variables.

        :param nmea_str: NMEA string.
        :param ens_index: Ensemble index in the file.
        """
        try:
            if nmea_str:
                temp_array = np.array(nmea_str.split(','))
                temp_array[temp_array == '999.9'] = ''

                # self.vtg_delta_time = delta_time
                self.hdt_header[ens_index][self.hdt_index] = temp_array[0]
                self.heading_deg[ens_index, self.hdt_index] = Nmea.valid_number(temp_array[1])
                idx_star = temp_array[2].find('*')
                self.h_true_indicator[ens_index][self.hdt_index] = temp_array[2][:idx_star]

                # TODO Find a way to calculate this value
                if self.last_gga_delta_time:
                    self.hdt_delta_time[ens_index, self.vtg_index] = self.last_gga_delta_time
                else:
                    self.hdt_delta_time[ens_index, self.vtg_index] = 0.0

        except (ValueError, EOFError, IndexError):
            pass

    def decode_dbt(self, nmea_str: str, ens_index: int):
        """
        Decode the DBT Depth Sounder message and set all the variables.

        :param nmea_str: NMEA string.
        :param ens_index: Ensemble index in the file.
        """
        try:
            if nmea_str:
                temp_array = np.array(nmea_str.split(','))
                temp_array[temp_array == '999.9'] = ''

                # self.dbt_delta_time = delta_time
                self.dbt_header[ens_index][self.dbt_index] = temp_array[0]
                self.depth_ft[ens_index, self.dbt_index] = Nmea.valid_number(temp_array[1])
                self.ft_indicator[ens_index][self.dbt_index] = temp_array[2]
                self.depth_m[ens_index, self.dbt_index] = Nmea.valid_number(temp_array[3])
                self.m_indicator[ens_index][self.dbt_index] = temp_array[4]
                self.depth_fath[ens_index, self.dbt_index] = Nmea.valid_number(temp_array[5])
                idx_star = temp_array[6].find('*')
                self.fath_indicator[ens_index][self.dbt_index] = temp_array[6][:idx_star]

                # TODO Find a way to calculate this value
                if self.last_gga_delta_time:
                    self.dbt_delta_time[ens_index, self.vtg_index] = self.last_gga_delta_time
                else:
                    self.dbt_delta_time[ens_index, self.vtg_index] = 0.0

        except (ValueError, EOFError, IndexError):
            pass

    @staticmethod
    def valid_number(data_in):
        """
        Check to see if data_in can be converted to float.

        :param data_in: str String to be converted to float
        :return Returns a float of data_in or nan if conversion is not possible
        """

        try:
            data_out = float(data_in)
        except ValueError:
            data_out = np.nan
        return data_out

    @staticmethod
    def check_nmea_checksum(nmea_str: str):
        """
        Calculate the NMEA checksum.  Verify the
        checksum value matches the given value.
        :param nmea_str NMEA string.
        :return TRUE = Good checksum
        """
        try:
            # Remove newline and spaces at the end
            nmea_str = nmea_str.rstrip('\n')
            # Get the checksum value
            checksum = nmea_str[len(nmea_str) - 2:]
            checksum = int(checksum, 16)

            # Get the data from the string
            nmea_data = re.sub("(\n|\r\n)", "", nmea_str[nmea_str.find("$") + 1:nmea_str.find("*")])

            # Calculate the checksum
            calc_checksum = 0
            for c in nmea_data:
                calc_checksum ^= ord(c)
            calc_checksum = calc_checksum & 0xFF

            # Verify the checksum matches
            if calc_checksum == checksum:
                return True

            return False
        except Exception as ex:
            logging.error(ex)
            return False

    def gga_expand(self, num_ens):
        self.gga_delta_time = np.concatenate(
            (self.gga_delta_time, np.tile(np.nan, (1, num_ens)).T), axis=1)
        self.utc = np.concatenate(
            (self.utc, np.tile(np.nan, (1, num_ens)).T), axis=1)
        self.lat_deg = np.concatenate(
            (self.lat_deg, np.tile(np.nan, (1, num_ens)).T), axis=1)
        self.lon_deg = np.concatenate(
            (self.lon_deg, np.tile(np.nan, (1, num_ens)).T), axis=1)
        self.corr_qual = np.concatenate(
            (self.corr_qual, np.tile(np.nan, (1, num_ens)).T), axis=1)
        self.num_sats = np.concatenate(
            (self.num_sats, np.tile(np.nan, (1, num_ens)).T), axis=1)
        self.hdop = np.concatenate(
            (self.hdop, np.tile(np.nan, (1, num_ens)).T), axis=1)
        self.alt = np.concatenate(
            (self.alt, np.tile(np.nan, (1, num_ens)).T), axis=1)
        self.geoid = np.concatenate(
            (self.geoid, np.tile(np.nan, (1, num_ens)).T), axis=1)
        self.d_gps_age = np.concatenate(
            (self.d_gps_age, np.tile(np.nan, (1, num_ens)).T), axis=1)
        self.ref_stat_id = np.concatenate(
            (self.ref_stat_id, np.tile(np.nan, (1, num_ens)).T), axis=1)
        for ens in range(num_ens):
            self.gga_header[ens].append('')
            self.geoid_unit[ens].append('')
            self.alt_unit[ens].append('')
            self.lon_ref[ens].append('')
            self.lat_ref[ens].append('')

    def vtg_expand(self, num_ens):
        self.vtg_delta_time = np.concatenate(
            (self.vtg_delta_time, np.tile(np.nan, (1, num_ens)).T), axis=1)
        self.course_true = np.concatenate(
            (self.course_true, np.tile(np.nan, (1, num_ens)).T), axis=1)
        self.course_mag = np.concatenate(
            (self.course_mag, np.tile(np.nan, (1, num_ens)).T), axis=1)
        self.speed_knots = np.concatenate(
            (self.speed_knots, np.tile(np.nan, (1, num_ens)).T), axis=1)
        self.speed_kph = np.concatenate(
            (self.speed_kph, np.tile(np.nan, (1, num_ens)).T), axis=1)
        for ens in range(num_ens):
            self.kph_indicator[ens].append('')
            self.mode_indicator[ens].append('')
            self.vtg_header[ens].append('')
            self.true_indicator[ens].append('')
            self.mag_indicator[ens].append('')
            self.knots_indicator[ens].append('')

    def dbt_expand(self, num_ens):
        self.dbt_delta_time = np.concatenate(
            (self.dbt_delta_time, np.tile(np.nan, (1, num_ens)).T), axis=1)
        self.depth_ft = np.concatenate(
            (self.depth_ft, np.tile(np.nan, (1, num_ens)).T), axis=1)
        self.depth_m = np.concatenate(
            (self.depth_m, np.tile(np.nan, (1, num_ens)).T), axis=1)
        self.depth_fath = np.concatenate(
            (self.depth_fath, np.tile(np.nan, (1, num_ens)).T), axis=1)
        for ens in range(num_ens):
            self.fath_indicator[ens].append('')
            self.dbt_header[ens].append('')
            self.ft_indicator[ens].append('')
            self.m_indicator[ens].append('')

    def hdt_expand(self, num_ens):
        self.hdt_delta_time = np.concatenate(
            (self.hdt_delta_time, np.tile(np.nan, (1, num_ens)).T), axis=1)
        self.heading_deg = np.concatenate(
            (self.heading_deg, np.tile(np.nan, (1, num_ens)).T), axis=1)
        for ens in range(num_ens):
            self.h_true_indicator[ens].append('')
            self.hdt_header[ens].append('')
