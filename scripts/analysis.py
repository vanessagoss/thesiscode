###############################################################################
# File  : thesiscode/scripts/analysis.py
# Author: madicken
# Date  : Tue Mar 14 14:05:05 2017
#
# <+Description+>
###############################################################################

from __future__ import (division, absolute_import, print_function, )

#-----------------------------------------------------------------------------#

import numpy as np
import h5py
import pandas as pd
from mcnpoutput import TrackLengthTally
from plotting_utils import ( names, energy_histogram )
from analysis_utils import get_num_cores
import matplotlib as mpl
mpl.use('agg')
import matplotlib.pyplot as plt
import seaborn as sns
import logging
import json

###############################################################################

class MCNPOutput(object):
    '''
    MCNPOutput is a simple wrapping class to pull in tally data for an
    f4 tally binned by energy. Given a mcnp output file location and the tally
    number (defaulted to 44), this class will return that tally data
    '''
    def __init__(self, outputlocation, tallynumber='44'):
        '''
        Returns output location, tally number, and title of solution as
        class objects
        '''
        self.outputlocation = str(outputlocation)
        self.title = self.outputlocation
        self.tallynumber = tallynumber
        pass

    def get_tally_data(self):
        '''
        Returns dict of tally data. Dict includes timing data returned from
        convergence information, and tally results.
        '''
        output_init = TrackLengthTally(self.outputlocation, self.tallynumber)
        output_fom = output_init.get_fom_data()
        output_tally = output_init.get_tally_result()
        output_timing = output_init.get_timing_data()

        output_container = {'timing' : output_timing,
                            'fom_trends' : output_fom,
                            'tally_data' : output_tally}

        return output_container


#-----------------------------------------------------------------------------#

class TimingOutput(object):
    '''
    This class reads in the timing dict from the timing.json file ouputted from
    a modified ADVANTG run.
    '''
    def __init__(self, timingfilelocation, num_cores=None):
        '''
        Adds timingfile location to class as object.
        '''
        self.timingfile = str(timingfilelocation)
        self.cores = num_cores
        pass

    def get_timing_data(self, extraopts=['strings']):
        '''
        Returns a dict of timing information. Dict includes full deterministic
        runtime, modified deterministic runtime (the full time less extraopts
        and a few extra parameters), the keys used to calculate each time, and
        the units of the dict.

        get_timing_data() will return a modified deterministic runtime with the
        default timings modified (mix_mats, map_cells, and anisotropy
        quantification)

        get_timing_data(extraopts=['Writing omega solution to disk']) will
        return a modified runtime with the default timings subtrated and also
        everything contained in extraopts.
        '''
        # open the logger
        logger = logging.getLogger("analysis.fomanalysis.timing_data")

        timingfile = open(self.timingfile)
        tf = json.loads(timingfile.read())

        defaults = [
              'mix_mats',
              'map_cells',
              'Quantifying anisotropy with six anisotropy metrics.',
              ]

        ignore_keys = defaults + extraopts

        times = self.split_timing_dict(tf, ignore_keys)

        adv_time = np.sum(times['advantg_times'].values())
        denovo_time = np.sum(times['denovo_times'].values())

        if self.cores is not None:
            logger.debug('''calculating adjusted denovo runtime by %.2f seconds and
                    %d number of cores to get walltime''' %(denovo_time,
                        self.cores))
            denovo_time = self.cores*denovo_time
        omega_time = np.sum(times['omega_times'].values())
        dispose_time = np.sum(times['dispose_times'].values())
        total_time = denovo_time + omega_time + adv_time

        totals = {'advantg_time': adv_time,
                  'denovo_time': denovo_time,
                  'omega_time': omega_time,
                  'dispose_time': dispose_time,
                  'total': total_time}
        times['totals'] = totals

        newtime = total_time
        full_det_time = newtime + dispose_time

        timing_data = {
                'full_deterministic_time': full_det_time,
                'adjusted_deterministic_time': newtime,
                'num_cores' : self.cores,
                'timing_dicts' : times,
                'units':'seconds'
                }

        return timing_data

    def split_timing_dict(self, timingdict, ignore_keys):
        # open the logger
        logger = logging.getLogger("analysis.fomanalysis.timing_data")

        # define the keys that will go into each dictionary
        denovo_keys=['Loading material compositions',
                     'Executing Denovo',
                     'Calculating Denovo responses',
                     'Saving Denovo responses',
                     ]
        omega_keys=['Calculating the omega fluxes',
                    'Reading and cleaning angular flux data from disk',
                    'Writing omega solution to disk',
                    ]
        # advantg dict not defined becuase everything not in denovo, omega, or
        # dispose keys will go to advantg dictionary.

        dispose_keys=ignore_keys

        advantg_dict={}
        denovo_dict={}
        omega_dict={}
        dispose_dict={}

        for key in timingdict:
            if key in denovo_keys:
                denovo_dict[key]=timingdict[key]
            elif key in omega_keys:
                omega_dict[key]=timingdict[key]
            elif key in dispose_keys:
                dispose_dict[key]=timingdict[key]
            else:
                advantg_dict[key]=timingdict[key]

        alltimes = {
                'advantg_times': advantg_dict,
                'denovo_times': denovo_dict,
                'omega_times': omega_dict,
                'dispose_times': dispose_dict}

        return alltimes


#-----------------------------------------------------------------------------#

class H5Output(object):
    '''
    HDF5 reader class, custom for anisotropy output file specifically. In an
    ADVANTG run, this file should be located at
    ${solution_dir}/omega_solution/problem_anisotropies.h5
    '''
    def __init__(self, outputlocation):
        self.outputlocation = str(outputlocation)
        self.filtermatrix = {}
        pass

    # this function still in progress. Not fully functional.
    def get_all_data(self):
        '''
        Returns all data from an hdf5 file. Users should be cautious because
        all of this data will be read into memory at one time.
        '''
        f=h5py.File('%s' %(self.outputlocation), 'r')

        return all_data

    def get_datanames(self):
        '''
        Returns dict of metric_names and energy_groups contained in the
        anisotropy file. These can be used for labeling of data.
        '''
        f = h5py.File('%s' %(self.outputlocation),'r')
        metric_names = f.keys()
        energy_groups = f[metric_names[0]].keys()

        names = {'metric_names' : metric_names,
                 'energy_groups' : energy_groups}

        return names

    def get_dataset_by_metric(self, metric_name, num_samples = 1500,
                             flatten_data=True, **kwargs):
        '''
        Returns a dict with the names of each energy group
        and a matrix of data corresponding to a sample of anisotropy data
        (num_samples) for a specified metric name.
        '''
        # open the logger
        logger = logging.getLogger("analysis.H5Output.subdatabymetric")

        full_dataset = self.get_data_by_metric(metric_name,
                flatten_data=flatten_data, **kwargs)
        full_data = full_dataset['data']

        logger.debug('getting dataset of %s particles for %s' %(num_samples,
            metric_name))

        size = np.shape(full_data)
        num_groups = size[-1]

        data = np.zeros(num_samples)
        for group in np.arange(num_groups):
            datasample = full_data[:,group]
            dataset = datasample[~np.isnan(datasample)]
            newdata = np.random.choice(dataset,num_samples)
            data = np.column_stack((data,newdata))

        data = data[:,1:]

        metricdata = {'names' : full_dataset['names'],
                     'data' : data,
                     'description': '%s count sample of ' %(num_samples)
                           + 'anisotropy data for all energy groups, %s'
                     %(metric_name)}

        return metricdata


    def get_data_by_metric(self, metric_name, flatten_data=True, **kwargs):
        '''
        Returns a dict with the names of each group and a
        matrix of data corresponding to the anisotropy data (groupwise) for a
        specifed metric name If flatten_data is set to False, then the data
        matrix returned in the dict will have dimensions of (groups, x, y, z),
        else it will be (groups, x*y*z). Because this function is used
        primarily for plotting, the dimensionality of the flattened array is
        desired.
        '''
        # open the logger
        logger = logging.getLogger("analysis.H5Output.databymetric")

        # open the file as readonly
        f=h5py.File('%s' %(self.outputlocation), 'r')


        # set up empty arrays for data storage before loading it in
        matrix_size = f['%s' %metric_name]['group_000'].size
        data = np.zeros([matrix_size])
        names = []

        # loop through the data in the hdf5 file and load it in
        for group in f['%s' %metric_name]:
            subdata = f['%s' %metric_name][group][:]
            if kwargs.get('cutoff') == 'mean' or kwargs.get('cutoff') == 'median':
                filter_mat = self.get_filter_matrix(group, **kwargs)
                subdata = subdata*filter_mat
                subdata[subdata == 0] = np.nan
                subdata = subdata.flatten()
            elif kwargs.get('cutoff') == 'full':
                logger.debug('cutoff value of full specified. Using all'
                        + ' anisotropy values for %s data selection' %group)
                subdata = subdata.flatten()
            elif kwargs.get('cutoff') == None:
                logger.error('cutoff value not specified. Default to plot'
                        + 'all anisotropy values for %s.' %group)
                subdata = subdata.flatten()
            else:
                logger.error('cutoff value of %s not recognized'
                        %kwargs.get('cutoff'))
            data = np.row_stack((data,subdata))
            names.append(group)

        # Rotate the matrix for plotting optimization
        data = np.transpose(data)

        # clear out the row of zeros that appears from row_stack
        data = data[:,1:]

        metricdata = {'names' : names,
                     'data' : data,
                     'description': 'anisotropy data for all energy groups, %s'
                     %metric_name}

        return metricdata

    def get_data_by_energy(self, group_number, flatten_data=True, **kwargs):
        '''This function will return a dict of the names of each metric that
        have been aquired and an array of data corresponding to the anisotropy
        data for each metric given a specified energy group number. If
        flatten_data is set to False, then the data matrix will have
        dimensions of (no. metrics, x, y, z), else it will be (no. metrics,
        x*y*z) '''

        # open the logger
        logger = logging.getLogger("analysis.H5Output.databyenergy")

        # open the file as readonly
        f=h5py.File('%s' %(self.outputlocation), 'r')

        # set up empty arrays for data storage before loading it in
        matrix_size = f['forward_anisotropy']['group_000'].size
        data = np.zeros([matrix_size])
        metric_names = f.keys()
        if 'contributon_flux' in metric_names:
            metric_names.remove('contributon_flux')

        # check to see how user specified group number. Make it usable by
        # function.
        if type(group_number) == int:
            group_number = 'group_%03d' %group_number
        elif type(group_number) == unicode or str:
            group_number = group_number
        else:
            logger.error('group number is not a recognized type')

        logger.debug('using data for %s' %group_number)
        # loop through the data in the hdf5 file and load it in
        for metric in metric_names:
            subdata = f[metric][group_number][:]
            if kwargs.get('cutoff') == 'mean' or kwargs.get('cutoff') == 'median':
                filter_mat = self.get_filter_matrix(group_number, **kwargs)
                subdata = subdata*filter_mat
                subdata[subdata == 0] = np.nan
                subdata = subdata.flatten()
            elif kwargs.get('cutoff') == 'full':
                logger.debug('cutoff value of full specified. Using all'
                        + ' anisotropy values for %s data selection' %metric)
                subdata = subdata.flatten()
            elif kwargs.get('cutoff') == None:
                logger.error('cutoff value not specified. Default to plot'
                        + 'all anisotropy values for %s.' %metric)
                subdata = subdata.flatten()
            else:
                logger.error('cutoff value of %s not recognized'
                        %kwargs.get('cutoff'))
            data = np.row_stack((data,subdata))

        # Rotate the matrix for plotting optimization
        data = np.transpose(data)

        # clear out the row of zeros that appears from row_stack
        data = data[:,1:]

        groupdata = {'names': names,
                      'data': data,
                      'description':'anisotropy data for all metrics, energy %s'
                                     %group_number}

        return groupdata

    def get_dataset_by_energy(self, group_number, num_samples = 1500,
                             flatten_data=True, **kwargs):
        '''
        Returns a dict with the names of eeach energy group
        and a matrix of data corresponding to a sample of anisotropy data (n
        samples) for a specified metric name.
        '''

        # open the logger
        logger = logging.getLogger("analysis.H5Output.subdatabyenergy")

        if type(group_number) == int:
            group_number = 'group_%03d' %group_number
        elif type(group_number) == unicode or str:
            group_number = group_number
        else:
            logger.error('group number is not a recognized type')

        full_dataset = self.get_data_by_energy(group_number,
                flatten_data=flatten_data, **kwargs)
        full_data = full_dataset['data']

        logger.debug('getting dataset of %s particles for %s' %(num_samples,
            group_number))

        size = np.shape(full_data)
        num_metrics = size[-1]

        data = np.zeros(num_samples)
        for metric in np.arange(num_metrics):
            datasample = full_data[:,metric]
            dataset = datasample[~np.isnan(datasample)]
            newdata = np.random.choice(dataset,num_samples)
            data = np.column_stack((data,newdata))

        data = data[:,1:]

        groupdata = {'names' : full_dataset['names'],
                     'data' : data,
                     'description': '%s count sample of ' %(num_samples)
                           + 'anisotropy data for all metrics, energy %s'
                     %(group_number)}

        return groupdata

    def get_filter_matrix(self, group, cutoff='mean'):
        # open the logger
        logger = logging.getLogger("analysis.H5Output.filtermetric")

        if cutoff in self.filtermatrix and group in \
        self.filtermatrix[cutoff]:
            filter_matrix = self.filtermatrix[cutoff][group]
            logger.debug('Found precalculated %s filter matrix for' %(group)
                     + ' contributon flux %s value.' %cutoff)
        else:
            # open the file as readonly
            f=h5py.File('%s' %(self.outputlocation), 'r')

            data = f['contributon_flux'][group][:]

            if cutoff == 'mean':
                cutoff_val = np.mean(data)
            elif cutoff == 'median':
                cutoff_val = np.median(data)

            data[data > cutoff_val] = 1
            data[data <= cutoff_val] = 0

            unique, counts = np.unique(data, return_counts=True)

            logger.debug('Filter matrix for %s created with' %(group)
                     + ' contributon flux %s value.' %cutoff
                     + ' %d counts above the mean,' %counts[1]
                     + ' and %d counts filtered out' %counts[0] )

            filter_matrix = data

            logger.debug('Adding %s filter matrix to %s dictionary'
                    %(group, cutoff))
            if cutoff in self.filtermatrix:
                self.filtermatrix[cutoff][group] = filter_matrix
            else:
                self.filtermatrix[cutoff] = {}
                self.filtermatrix[cutoff][group] = filter_matrix

        return filter_matrix

    def get_data_statistics(self, filter_data=False, **kwargs):
        '''
        Calculates the average value, median value, metric variance,
        and standard deviation for each
        metric by energy group and returns a dict with that data:
        - the metrics for which the statistics were calculated
        - the group numbers over which the metrics were calculated
        - the statistics calculated ('data')
        - labels for the statistics ('statistics')
        The actual data returned in the dict will have dimensions of:
        (metric*no.groups*statistics) corresponding to the averages, and the other for the
        standard deviations.
        '''

        # open the file as readonly
        f=h5py.File('%s' %(self.outputlocation), 'r')

        # set up the labelling lists
        metric_names = f.keys()
        if 'contributon_flux' in metric_names:
            metric_names.remove('contributon_flux')
        group_numbers = f['forward_anisotropy'].keys()

        # set up empty arrays for data storage before loading it in
        no_metrics = len(metric_names)
        no_groups = len(group_numbers)
        data = np.zeros([no_metrics, no_groups, 4])

        counts = {}

        # now set up the loops to calculate metrics on subsets of data
        for metric in metric_names:
            metric_location = metric_names.index(metric)
            for group in group_numbers:
                group_location = group_numbers.index(group)

                # pull the chunk of data associated with metric and group from
                # the file.
                data_chunk = f[metric][group][:]

                if filter_data == True:
                    # sift out any of the values of the flux that lie in
                    # unimportant regions
                    filter_mat = self.get_filter_matrix(group, **kwargs)
                    data_chunk = data_chunk*filter_mat

                    # get rid of all zero-valued data
                    filtered_data = data_chunk[data_chunk != 0]
                    counts[group] = filtered_data.size

                    if filtered_data.size != np.sum(filter_mat):
                        logger.warning('The filtered data does not tally to the'
                                + 'same number of nonzero bins as the filter'
                                + 'matrix.')

                elif filter_data == False:
                    filtered_data = data_chunk

                # calculate the statistics on the data chunk and put them into
                # an array.
                mean = np.mean(filtered_data)
                median = np.median(filtered_data)
                std = np.std(filtered_data)
                var = np.var(filtered_data)
                stats = np.array([mean, median, std, var])

                data[metric_location,group_location,:] = stats

        statistics = ['mean', 'median', 'standard deviation', 'variance']

        stats_container = {'metrics' : metric_names,
                           'group numbers' : group_numbers,
                           'statistics' : statistics,
                           'data' : data}

        if counts:
            stats_container['counts'] = counts

        return stats_container


#-----------------------------------------------------------------------------#

class DenovoOutput(object):
    def __init__(self, outputdirectory):
        self.outputdirectory = str(outputdirectory)
        pass

    def get_timing_data(self):
        pass

    def get_statistical_info(self):
        pass


#-----------------------------------------------------------------------------#

class AnisotropyAnalysis(object):
    def __init__(self):
        pass

#-----------------------------------------------------------------------------#

class FOMAnalysis(object):
    '''
    This class has the options to calculate simple FoM data for a single
    run. If only a MC_output_file is specified, then foms will be calculated
    for the tally average relative error, the tally maximum relative error, and
    the tally minumum_relative error given a speficied tally number. If a
    deterministic timing file is included, then modified FOMS including the
    deterministic runtime will also be calculated.
    '''
    def __init__(self, MC_output_file, tallynumber,
            deterministic_timing_file='', omnibus_output_file='',
            datasavepath=''):
        '''
        Sets up variables in the class that are usable by all class functions
        '''

        import os

        # set the user-specified variables for accessibility later
        self.mc_output_file = MC_output_file
        self.tallynumber = tallynumber
        self.det_timing_file = deterministic_timing_file
        self.omnibus_output_file = omnibus_output_file

        # read in the relevant data for analysis into objects
        # first, monte carlo data:
        self.mc_data = MCNPOutput(self.mc_output_file,
                        tallynumber=self.tallynumber).get_tally_data()

        # then, if a deterministic timing file has been specified, read that
        # data to an object as well.
        #
        if self.omnibus_output_file:
            self.num_cores = get_num_cores(self.omnibus_output_file)

        if deterministic_timing_file:
            self.det_timingdata = TimingOutput(self.det_timing_file,
                    num_cores=self.num_cores).get_timing_data()
        else:
            self.det_timingdata = None

        # reserve some variables for accessibility later
        self.all_foms = {}
        self.fom_frame = self.generate_fom_frame()
        self.timing_frame = self.generate_timing_frame()
        self.tally_frame = self.get_tallyframe(self.mc_data['fom_trends'],
                          index='nps')


        # specify a folder where the plots and files associated with this
        # method will be saved
        if datasavepath:
            self.savepath = datasavepath
        elif self.det_timingdata is not None:
            # if no path is specified, then assume it should be saved in an
            # analysis folder alongside the MC_output_file.
            path1 = os.path.dirname(MC_output_file)
            path2 = os.path.join(path1, '../analysis/')
            path2 = os.path.normpath(path2)
            self.savepath = path2
        else:
            # if there is no deterministic timing data, then put the saved data
            # in the mcnp folder.
            self.savepath = os.path.dirname(MC_output_file)
        pass

    def print_tally_convergence(self, printtype='', **kwargs):
        '''
        Returns the tally convergence data in a pandas dataframe, or a
        formatted dataframe if printtype is specified. Printtypes available are
        str and tex. Other pandas formatting options can be passed with
        **kwargs.
        '''
        # first get the pandas dataframe from get_tallyframe
        if self.tally_frame is not None:
            frame = self.tally_frame
        else:
            frame = self.get_tallyframe(self.mc_data['fom_trends'], index='nps')

        frame = self.format_dataframe(frame, printtype=printtype, **kwargs)

        return frame

    def print_tally_foms(self, printtype='', **kwargs):
        '''
        Returns the tally figure of merits in a pandas dataframe, or a
        formatted dataframe if printtype is specified. Printtypes available are
        str and tex. Other pandas formatting options can be passed with
        **kwargs.
        '''
        # first get the pandas dataframe from generate_fom_frame
        if self.fom_frame is not None:
            frame = self.fom_frame
        else:
            frame = self.generate_fom_frame()

        frame = self.format_dataframe(frame, printtype=printtype, **kwargs)

        return frame

    def format_dataframe(self, dataframe, printtype='', **kwargs):
        '''
        Given a dataframe, this function will return it given the formatting
        option specified in printtype. If printtype is not specified, this
        funciton will return the same dataframe. Further formatting options can
        be specified through **kwargs. printtype options can be string or
        latex.
        '''

        # open the logger
        logger = logging.getLogger("analysis.fomanalysis.format_dataframe")

        if printtype == '':
            logger.debug('No formatting type specified. Returning user input')
            frame = dataframe
        elif printtype == 'string' or printtype == 'str':
            logger.debug('formatting the dataframe to %s' %printtype)
            frame = dataframe.to_string(**kwargs)
        elif printtype == 'tex' or printtype == 'latex':
            frame = dataframe.to_latex(**kwargs)
            logger.debug('formatting the dataframe to %s' %printtype)
        else:
            logger.warning('%s is not a recognized printing type for this table'
                    %(printtype))
            frame = dataframe

        return frame

    def get_tallyframe(self, datadict, index=''):
        '''
        Given a dictionary containing strings or arrays fo data, get_tallyframe
        will return a pandas dataframe. If index is specified, the key:value
        pair of the dictionary that corresponds with that index will be used
        for the dataframe indexing.
        '''
        if index:
            ind_digits = [int(num) for num in datadict[index]]
            tallyframe = pd.DataFrame(datadict, index=ind_digits)
            tallyframe = tallyframe.drop(index, 1)
        else:
            tallyframe = pd.DataFrame(datadict)

        self.tally_frame = tallyframe
        return tallyframe


    def plot_fom_convergence(self, plot_name='fom_converge'):
        '''
        Convenience plotting function for plotting the FOM convergence as a
        function of particle count.
        '''
        xdata = self.mc_data['fom_trends']['nps']
        ydata = self.mc_data['fom_trends']['fom']
        x_label = 'Number of Source Particles'
        y_label = 'Figure of Merit'
        plt_title = 'Figure of Merit Convergence'
        plt_name = plot_name
        self.generic_scatterplot(xdata, ydata, self.savepath, title=plt_title,
                xlabel=x_label, ylabel=y_label, plot_name=plt_name)
        pass

    def generate_timing_frame(self):
        '''Returns a dataframe of all timing data for the problem. If only an
        MCNP input exists, then only MCNP data will be reported.
        '''

        # open the logger
        logger = logging.getLogger('analysis.fomanalysis.timingrame')

        # pull in the monte carlo data from MCrun.
        std_fom_time = self.mc_data['timing']['mcrun_time']['time']
        mc_units = self.mc_data['timing']['mcrun_time']['units']

        MCNP_time = {'total': [std_fom_time]}

        if self.det_timingdata is not None:
            logger.info('''Constructing
                    timing table with MCNP data from %s and timing data from
                    %s. Parallelized times will be multiplied by %d cores.'''
                    %(self.mc_output_file, self.det_timing_file, self.num_cores))
            totals = self.det_timingdata['timing_dicts']['totals']
            det_times = totals.copy()
            det_units = self.det_timingdata['units']
            total_det_time = det_times['denovo_time']

            # make sure units of time match between files
            if det_units == 'seconds' and mc_units == 'minutes':
                det_times = dict((key, [values/60.0]) for key, values in \
                        det_times.iteritems())

            elif det_units == mc_units:
                logger.debug('The units for the deterministic timing file and '
                        'the monte carlo file are the same: %s' %(det_units))

            else:
                logger.debug('The units for these timing files are different from'
                      'expected vals. det units are %s and mc units are %s'
                      %(det_units, mc_units))

            ttime = MCNP_time['total'][0]+det_times['total'][0]

            walltime = {'total': [ttime]}

            frame1 = pd.DataFrame(det_times).transpose()
            frame2 = pd.DataFrame(MCNP_time).transpose()
            frame3 = pd.DataFrame(walltime).transpose()

            data = [frame1, frame2, frame3]
            labels = ['deterministic time', 'MCNP time', 'wall time']
            frame = pd.concat(data, keys=labels)
            frame.columns = ['time (%s)' %(mc_units)]

        else:
            logger.debug('''No deterministic timing data found. Constructing
                    timing table with MCNP data only.''')

            ttime = MCNP_time['total'][0]
            walltime = {'total': [ttime]}

            frame1 = pd.DataFrame(MCNP_time).transpose()
            frame3 = pd.DataFrame(walltime).transpose()
            frame = pd.concat([frame1,frame3], keys=['MCNP time','wall time'])
            frame.columns = ['time (%s)' %(mc_units)]

        self.timing_frame = frame
        return frame

    def generate_fom_frame(self):
        '''
        Returns a datframe of all FOMS for a tally. If only an MCNP input exists,
        then the tally average, tally maximum relative error and tally minumum
        relative error FOMs will be calculated with the mcrun time. If a
        deterministic timing data file is present, adjusted FOMS will also be
        in the returned dataframe.
        '''

        # check to see if foms have been generated
        if not self.all_foms:
            all_foms = self.calculate_all_foms()
        else:
            all_foms = self.all_foms

        # Put the MCNP FOMs into the data dict.
        data = {'MC': [all_foms['fom_mc']['FOM'], all_foms['fom_max']['FOM'],
            all_foms['fom_min']['FOM'], all_foms['fom_mc']['time'] ] }

        # If the deterministic timing file is present, then calculate the
        # modified FOMS and add them to the data dict too
        if self.det_timingdata is not None:
            data.update({ 'MC_adjusted':
                    [all_foms['fom_mc_det']['FOM'],
                    all_foms['fom_max_det']['FOM'],
                    all_foms['fom_min_det']['FOM'],
                    all_foms['fom_mc_det']['time']]})

        # add labels for the index
        labels = ['tally avg', 'max RE', 'min RE', 'time (mins)']

        # put the data into a datframe.
        frame = pd.DataFrame(data, index=labels)

        # add the frame to the data object.
        self.fom_frame = frame

        return frame

    def generic_scatterplot(self, xdata, ydata, savepath, title='title',
            xlabel='xlabel', ylabel='ylabel', plot_name='generic'):
        '''
        Convenience function for making a scatterplot.
        '''
        sns.set_style('ticks',
                      {'ytick.direction': u'in',
                       'xtick.direction': u'in'})
        pal = sns.cubehelix_palette()
        x=xdata
        y=ydata
        plt.scatter(x,y, s=26, c=pal[3])
        plt.title(title)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.savefig('%s/%s.pdf' %(savepath,plot_name), hbox_inches='tight')

    def calculate_all_foms(self):
        '''
        Function to calculate the FOMS for the problem. Returns dict with
        either 3  or 6 entries. If only MCNP output is found, then dict will
        contain Monte Carlo-exclusive FOMS. If MCNP output and deterministic
        output are found, then dict will also include adjusted FOMS.
        '''

        # open the logger
        logger = logging.getLogger('analysis.fomanalysis.calculatefoms')

        # pull out fom, mean, and error from tally convergence data.
        logger.info("calculating foms for mcnp run")
        std_fom = self.mc_data['fom_trends']['fom'][-1]
        std_fom_mean = self.mc_data['fom_trends']['mean'][-1]
        std_fom_err = self.mc_data['fom_trends']['error'][-1]
        std_fom_pcount = self.mc_data['fom_trends']['nps'][-1]

        # pull in the monte carlo data from MCrun.
        std_fom_time = self.mc_data['timing']['mcrun_time']['time']
        mc_units = self.mc_data['timing']['mcrun_time']['units']

        # put timing data into dict.
        time_data = {'mc_time': std_fom_time,
                     'units': mc_units}

        # from the tally data, get the tally total relative error, max relative
        # error and the min relative error.
        total_err = self.mc_data['tally_data']['tally_total_relative_error']
        max_err = self.mc_data['tally_data']['relative_error'].max()
        min_err = self.mc_data['tally_data']['relative_error'].min()

        if total_err == std_fom_err:
            logger.debug('''Tally convergence relative error and tally results
                    total relative error match''')
        else:
            logger.warning('''Tally convergence relative error and tally
            results total relative error do not match. \n
            Tally convergence RE: %s \n
            Tally results total RE: %s \n ''' %(std_fom_err,total_err))

        # calculate the foms and put them into dictionaries
        dat1 = self.make_fom_dict(std_fom_err, std_fom_time)
        dat2 = self.make_fom_dict(max_err, std_fom_time)
        dat3 = self.make_fom_dict(min_err, std_fom_time)

        # put MC FOMS into solution dictionary. Include particle count and time
        # data.
        fom_results = {
                   'fom_mc': dat1,
                   'fom_max': dat2,
                   'fom_min': dat3,
                   'particle_count': std_fom_pcount,
                   'times_used' : time_data,
                   }

        # check to see if deterministic timing data exists.
        if self.det_timingdata is not None:
            logger.info("""calculating modified foms which incorporate
                   deterministic runtime""")
            # add all deterministic stuff to dict if timingdata has been
            # generated for this problem

            det_time = self.det_timingdata['adjusted_deterministic_time']

            # make sure units of time match between files
            det_units = self.det_timingdata['units']
            if det_units == 'seconds' and mc_units == 'minutes':
                det_time = det_time/60.0
            else:
                logger.debug('The units for these timing files are different from'
                      'expected vals. det units are %s and mc units are %s'
                      %(det_units, mc_units))

            total_time = std_fom_time + det_time

            time_data.update({
                     'det_time' : det_time,
                     'total_time' : total_time,
                })

            # calculate the deterministic adjusted FOMs. Add them to
            # dictionaries.
            dat4 = self.make_fom_dict(total_err, total_time)
            dat5 = self.make_fom_dict(max_err, total_time)
            dat6 = self.make_fom_dict(min_err, total_time)

            # update the solution dict to include new FOMS
            fom_results.update({
                   'fom_mc_det': dat4,
                   'fom_max_det': dat5,
                   'fom_min_det': dat6,
                   'times_used' : time_data,
                })

        self.all_foms = fom_results

        return fom_results

    def make_fom_dict(self,err,time):
        '''
        Convenience function for calculating the figure of merit and
        putting fom data into a dictionary.
        '''

        # calculate the FOM
        figure_of_merit = np.divide(1,(err**2)*time)

        return {
                'time': time,
                'relative_error' : err,
                'FOM' : figure_of_merit,
                }

#-----------------------------------------------------------------------------#

###############################################################################
# end of thesiscode/scripts/analysis.py
###############################################################################
