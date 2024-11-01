import csv
import os
import json
import pandas as pd
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import scipy.signal as sig
import open_ephys.analysis
import psutil

class process_ADC_Recordings:
    def __init__(self, dirname, rig = None):
        self.dirname = dirname
        self.rig = rig
        if self.rig == None:
            self.rig == 1

        self.extract_ADC_data()

        self.get_DAQ_pulses()

        self.get_camera_pulses()
        
    def extract_ADC_data(self):
        self.recording = open_ephys.analysis.Session(self.dirname).recordnodes[0].recordings[0].continuous[0]
        self.samples = self.recording.samples   # raw samples, not in microvolts
        self.sample_numbers = self.recording.sample_numbers
        self.timestamps = self.recording.timestamps
        self.metadata = self.recording.metadata

        self.total_sample_number = len(self.sample_numbers)

        self.ADC_channels = {}

        available_memory = psutil.virtual_memory().available

        print(f"Available Memory: {available_memory / (1024 ** 3)} GiB")


        for i in range(self.metadata['num_channels']):
            if 'ADC' in self.metadata['channel_names'][i]:
                self.ADC_channels[self.metadata['channel_names'][i]] = self.channel_data(i)
        
        # self.ADC_channels_filtered = {}
        # for channel in self.ADC_channels:
        #     self.ADC_channels_filtered[channel] = self.filter_data(self.ADC_channels[channel])

    def channel_data(self, index):
        data = []
        for row in self.recording.get_samples(start_sample_index = 0, end_sample_index = self.total_sample_number):
            data.append(row[index])
        
        return self.clean_square_wave(data)
    
    def clean_square_wave(self, data):
        # find max value in data
        max_value = max(data[1000:10000])
        # find min value in data
        min_value = min(data[1000:10000])
        # find the mean of the two
        mean_value = (max_value + min_value) / 2
        # if datapoint is above mean, set to max value
        # if datapoint is below mean, set to min value
        normalised_data = []
        for i, datapoint in enumerate(data):
            if datapoint > mean_value and datapoint > 1.5:
                normalised_data.append(1)
            else:
                normalised_data.append(0)
        
        return normalised_data
        
    
    def filter_data(self, original_data):
        # Filter requirements.
        T = 5.0         # Sample Period
        fs = 30000.0       # sample rate, Hz
        cutoff = 10  # desired cutoff frequency of the filter, Hz ,  
        nyq = 0.5 * fs  # Nyquist Frequency
        order = 2       # sin wave can be approx represented as quadratic
        n = int(T * fs) # total number of samples

        normal_cutoff = cutoff / nyq
        b, a = sig.butter(order, normal_cutoff, btype='lowpass', analog=False)       
        filtered_data = sig.filtfilt(b, a, original_data)

        return filtered_data
        
    def get_DAQ_pulses(self):
        """
        creates self.pulses, a list of timestamps for each pulse in the channel
        """
        try:
            data = self.ADC_channels["ADC7"]
        except KeyError:
            print(f"Channel not found")
            return

        self.pulses = []
        for i, datapoint in enumerate(data):
            if datapoint == 1:
                if data[i-1] == 0:
                    self.pulses.append(self.timestamps[i])

        # print(f"Channel ADC1 has {len(self.pulses)} pulses")

    def get_camera_pulses(self):

        try:
            data = self.ADC_channels["ADC6"]
            
        except KeyError:
            print(f"Channel not found")
            return

        self.camera_pulses = []
        for i, datapoint in enumerate(data):
            if datapoint == 0:
                if data[i-1] == 1:
                    self.camera_pulses.append(self.timestamps[i])

    def get_laser_pulses(self):
        try:
            data = self.ADC_channels["ADC8"]
        except KeyError:
            print("Channel not found")
            return

        self.laser_pulses = []
        high_time = None

        for i, datapoint in enumerate(data):
            if datapoint == 1:
                if i == 0 or data[i-1] == 0:  # Rising edge detected
                    high_time = self.timestamps[i]
            elif datapoint == 0:
                if i > 0 and data[i-1] == 1:  # Falling edge detected
                    low_time = self.timestamps[i]
                    self.laser_pulses.append((high_time, low_time))
                    high_time = None  # Reset high_time for the next pulse


    def import_arduino_data(self, path):
        with open(path, 'r') as f:
            data = json.load(f)
        messages = data["messages"]
        for i, message in enumerate(messages):
            try:
                message.append(self.pulses[i])
            except IndexError:
                print(f"IndexError at message {i}")
                break
        print(len(messages))
        filename = f"{self.dirname.name}_arduino_data.json"
        with open(filename, 'w') as f:
            json.dump(messages, f)
        return messages
        



    def view_ADC_data(self, *channels_to_plot, filtered = False):

        if len(channels_to_plot) == 0:
            channels_to_plot = self.ADC_channels.keys()
        print(channels_to_plot, len(channels_to_plot))

        fig, axs = plt.subplots(len(channels_to_plot), 1, figsize = (15, 10))

        for i, channel in enumerate(channels_to_plot):
            if filtered == False:
                data = self.ADC_channels[channel]
            if filtered == True:
                data = self.ADC_channels_filtered[channel]
            try:
                axs[i].scatter(self.timestamps, data, s = 0.1)
                axs[i].set_title(channel, loc = 'left', fontsize = 8)
            except TypeError:
                axs.scatter(self.timestamps, data, s = 0.1)
                axs.set_title(channel, loc = 'left', fontsize = 8)


        # fig, axs = plt.subplots(len(self.ADC_channels), 1, figsize = (15, 10))
        # for i, channel in enumerate(self.ADC_channels):
        #     axs[i].plot(self.timestamps, self.ADC_channels[channel])
        #     axs[i].set_title(channel, loc = 'left', fontsize = 8)
        
        plt.setp(axs, ylim=[-5, 5], xlim=[self.timestamps[0], self.timestamps[-1]])
        plt.subplots_adjust(hspace=0.65, left = 0.05, right = 0.97, top = 0.95, bottom = 0.05)
        
        plt.show()
        
if __name__ == "__main__":
    test = process_ADC_Recordings(r"C:\Users\Tripodi Group\OneDrive - University of Cambridge\01 - PhD at LMB\Coding projects\231101 - New analysis pipeline\231205_213113_test\2023-12-05_21-31-02")
    test.view_ADC_data("ADC2")