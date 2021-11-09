import sys
from contextlib import contextmanager
import matplotlib.pyplot as plt
from logging.handlers import RotatingFileHandler
import logging
import collections
import os
import dlr
import json
import cv2
import numpy as np
import datetime
from IPython.display import clear_output
import boto3
import time
from dlr.counter.phone_home import PhoneHome
PhoneHome.disable_feature()
logging.basicConfig(filename="SimulatorLog.log")
log_p = logging.getLogger('panoramasdk')
log_p.setLevel(logging.DEBUG)
handler = RotatingFileHandler("SimulatorLog.log", maxBytes=100000000, backupCount=2)
formatter = logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
handler.setFormatter(formatter)
log_p.addHandler(handler)
plt.rcParams["figure.figsize"] = (20, 20)
# Imports done

# Globals
frames_to_process = 10 ^ 20

# Read Graph
with open("{}/{}/{}/graphs/{}/graph.json".format(workdir, project_name, app_name, app_name)) as f:
    graph = json.load(f)
account_id = graph['nodeGraph']['packages'][0]['name'].split('::')[0]


@contextmanager
def nullify_output(suppress_stdout=True, suppress_stderr=True):
    """
    Stop DLR from putting out INFO messages
    Parameters
    ----------
    suppress_stdout : bool
    suppress_stderr : bool
    """

    stdout = sys.stdout
    stderr = sys.stderr
    devnull = open(os.devnull, "w")
    try:
        if suppress_stdout:
            sys.stdout = devnull
        if suppress_stderr:
            sys.stderr = devnull
        yield
    finally:
        if suppress_stdout:
            sys.stdout = stdout
        if suppress_stderr:
            sys.stderr = stderr


class callable_node:
    """
    Mock Callable Inference Node

    Parameters
    ----------
    model_name : str
    """

    def __init__(self):
        #self.inputs = inputs
        pass

    def model_name(self):
        self.model_name = 'test'

        def get():
            return self.model_name

    def get(self):
        return self.model_name


class media(object):

    """
    This class mimics the Media object in Panoroma SDK .

    ...

    Attributes
    ----------
    inputpath : str
        input path is a string path to a video file

    gen : video_reader instance

    Methods
    -------
    video_reader(key)
        CV2 based Generator for Video

    image : Property
        Gets the next frame using the generator

    image : Property Setter
        If we want to set the value of stream.image

    add_label:
        Add text to frame

    add_rect:
        add rectangles to frame

    time_stamp:
        returns the current timestamp

    stream_uri:
        returns a hardcoded value for now

    """

    def __init__(self, array):
        self.image = array
        self.w, self.h, self.c = array.shape

    @property
    def image(self):
        return self.__image

    @image.setter
    def image(self, array):
        self.__image = array

    def add_label(self, text, x1, y1):

        if x1 > 1 or y1 > 1:
            raise ValueError('Value should be between 0 and 1')

        # font
        font = cv2.FONT_HERSHEY_SIMPLEX
        # org
        org = (int(x1 * self.h), int(y1 * self.w))

        # fontScale
        fontScale = 1
        # Blue color in BGR
        color = (255, 0, 0)
        # Line thickness of 2 px
        thickness = 2

        # Using cv2.putText() method
        self.__image = cv2.putText(self.__image, text, org, font,
                                   fontScale, color, thickness, cv2.LINE_AA)

    def add_rect(self, x1, y1, x2, y2):

        if x1 > 1 or y1 > 1 or x2 > 1 or y2 > 1:
            raise ValueError('Value should be between 0 and 1')

        color = (255, 0, 0)
        # Line thickness of 2 px
        thickness = 2

        start_point = (int(x1 * self.h), int(y1 * self.w))
        end_point = (int(x2 * self.h), int(y2 * self.w))

        self.__image = cv2.rectangle(
            self.__image,
            start_point,
            end_point,
            color,
            thickness)

    @property
    def time_stamp(self):
        dateTimeObj = datetime.datetime.now()
        timestampStr = dateTimeObj.strftime("%d-%b-%Y (%H:%M:%S.%f)")
        return timestampStr

    @property
    def stream_uri(self):
        """Hardcoded Value for Now"""

        return 'cam1'


class AccessWithDot:

    """
    This class is implemented so we can mimic accessing dictionary keys with a .

    ...

    Attributes
    ----------
    response : dictionary
        Input is a dictionary object


    Methods
    -------
    __getattr__(key)
        First, try to return from _response
    """

    def __init__(self, response):
        self.__dict__['_response'] = response
        self.op_name = list(response.keys())[0]

    def __getattr__(self, key):
        # First, try to return from _response
        try:
            return self.__dict__['_response'][key]
        except KeyError as e:
            log_p.info('Key {} Not Found. Please Check {} package.json'.format(
                    e, package_name))
        # If that fails, return default behavior so we don't break Python
        try:
            return self.__dict__[key]
        except KeyError:
            raise AttributeError
            log_p.info('Attribute Error')


class getgraphdata:

    """
    Helper Class to Collect List of Nodes and Edges from the Graph.json

    Parameters
    ----------
    None
    """

    def __init__(self):
        pass

    def getlistofnodes(self):
        # read graph.json

        # get nodes into a dict
        graph_nodes = graph['nodeGraph']['nodes']

        # create node_dict
        node_dict = {}
        for d in graph_nodes:
            for key in d.keys():
                if key == 'name':
                    node_name = d[key]
                    node_dict[node_name] = [node_name]  # {}
                elif key != 'name':
                    node_dict[node_name].append(d[key])
            
            node_dict[node_name].append(d)
            

            # get edge name from edge dict from Node name
            edge_dict = self.getlistofedges()

            try:
                node_name_edge = edge_dict[node_name]
            except BaseException:
                node_name_edge = node_name

            # use the above name in the node dict
            node_dict[node_name_edge] = port(node_dict[node_name])

        return node_dict

    def getlistofedges(self):

        # read graph.json

        # get edges into a dict
        graph_edges = graph['nodeGraph']['edges']

        # create edge_dict
        edge_dict = {}
        for d in graph_edges:
            edge_dict[d['producer'].split(
                '.')[0]] = d['consumer'].split('.')[1]

        return edge_dict

    def getoutputsfrompackagejson(self):
        # read package.json from main package
        path = '{}/{}/{}/packages/'.format(workdir, project_name, app_name) + \
            account_id + '-' + package_name + '-1.0/' + 'package.json'

        # Read Graph
        with open(path) as f:
            package_json = json.load(f)

        output_name = package_json["nodePackage"]["interfaces"][0]["outputs"][0]["name"]

        return output_name


###### Video array CLASS #####

class Video_Array(object):

    """
    This class is implemented so we can use the opencv VideoCapture Method

    ...

    Attributes
    ----------
    inputpath :
        Input is a path to a video


    Methods
    -------
    get_frames
        returns a list of frames that total the global variable frames_to_process
    """

    def __init__(self, inputpath):
        self.input_path = inputpath

    def get_frames(self):

        try:

            video_frames = []
            cap = cv2.VideoCapture(self.input_path)

            num = frames_to_process
            frame_num = 0

            while (frame_num <= num):
                _, frame = cap.read()

                video_frames.append(frame)
                frame_num += 1

            return video_frames

        except Exception as e:
            raise ValueError(
                'Exception Class : Video_Array, Exception Method : get_frames, Exception Message : {}'.format(e))


class port():

    """
    Port Class Mock on the Device Panorama SDK

    Parameters
    ----------
    call_node : Dict

    Methods
    -------
    get : Gets the next frame from the video provided as a generator object
    """

    def __init__(self, call_node):
        
        try:
            self.call_node = call_node
            self.frame_output = []

            # classifying call_node
            self.call_node_type = 'call_node_name'
            self.call_node_location = None
            for val in self.call_node[:-1]:
                if not isinstance(
                        val, bool) and isinstance(
                        val, str) and len(
                        val.split('.')) > 1:
                    self.call_node_type = 'call_node_location'
                    self.call_node_location = val
                    break
                elif isinstance(val, bool) or type(val) in [int, float]:
                    continue

            # RTSP Stream Video Frames Creation
            if self.call_node_type == 'call_node_location' and self.call_node_location.split(
                    '.')[-2].split('::')[1] == camera_node_name:
                
                if camera_node_name != 'abstract_rtsp_media_source':

                    # 'reading in the video / rtsp stream'
                    path = '{}/{}/{}/packages/'.format(workdir, project_name, app_name) + self.call_node_location.split(
                        '.')[0].replace('::', '-') + '-1.0/' + 'package.json'
                    with open(path) as f:
                        package = json.load(f)
                    rtsp_url = package['nodePackage']['interfaces'][0]['inputs'][-1]['default']

                    # this may be temp or perm dont know yet
                    if rtsp_url.split('.')[-1] in ['avi', 'mp4']:
                        rtsp_url = '{}/{}/{}/assets/'.format(
                            workdir,project_name, app_name) + rtsp_url
                    
                    video_name = '{}/panorama_sdk/videos/{}'.format(workdir,videoname)
                
                elif camera_node_name == 'abstract_rtsp_media_source':
                    log_p.info('{}'.format('Using Abstract Data Source'))
                    video_name = '{}/panorama_sdk/videos/{}'.format(workdir,videoname)
                
                self.video_frames = (
                    media(x) for x in Video_Array(video_name).get_frames())
        except Exception as e:
            raise ValueError(
                'Exception Class : Port, Exception Method : __init__, Exception Message : {}'.format(e))

    def get(self):
        try:
            if self.call_node_type == 'call_node_name':
                return self.call_node[-1]['value']
            elif self.call_node_location.split('.')[-2].split('::')[1] == camera_node_name:
                # video frame generator
                return [next(self.video_frames)]

        except Exception as e:
            raise ValueError(
                'Exception Class : Port, Exception Method : get, Exception Message : {}'.format(e))


### MODEL CLASS #############

class ModelClass:
    """
    Model Class is a helper function for Node Class

    Parameters
    ----------
    None

    Methods
    -------
    None

    """

    def __init__(self, input_val1, model_name=""):
        self.input_val1 = input_val1
        self.model_name = model_name

    def __iter__(self):

        if self.model_name == "":
            raise ValueError(
                'Exception Class : ModelClass, Exception Method : __iter__, Exception Message : Please Provide Model Name')

        # Check if the supplied name is valid or not
        # Step 1: Get the interface for the model_node_name provided
        model_pkg = '{}/{}/{}/packages/'.format(workdir, project_name,
                                                app_name) + '/{}-{}'.format(account_id,
                                                                                model_node_name) + '-1.0/' + 'package.json'
        with open(model_pkg) as f:
            package = json.load(f)

        correct_interface = package["nodePackage"]["interfaces"][0]["name"]

        # get nodes from graph and get corresponding interface to the model
        # name in model_name
        graph_nodes = graph['nodeGraph']['nodes']
        interface_name = "not_found_yet"

        for dicts in graph_nodes:
            if dicts["name"] == self.model_name:
                interface_name = dicts["interface"]
            if dicts["interface"].split(
                    "::")[-1].split('.')[-1] == correct_interface:
                correct_name = dicts["name"]

        if interface_name == "not_found_yet":
            raise ValueError(
                'Exception Class : ModelClass, Exception Method : __iter__, Exception Message : Model Not Found in graph.json nodes')

        folder_name = interface_name.split('.')[0].replace('::', '-')
        name_in_interfaces_pjson = interface_name.split('.')[1]

        if name_in_interfaces_pjson != correct_interface:
            raise ValueError(
                'Exception Class : ModelClass, Exception Method : __iter__, Exception Message : Please Use the correct Model Node Name: {}'.format(correct_name))

        # read package.json from the folder name we got from the interface,
        # which is in the package folder
        path = '{}/{}/{}/packages/'.format(workdir, project_name,
                                           app_name) + folder_name + '-1.0/' + 'package.json'
        with open(path) as f:
            package = json.load(f)

        interfaces = package["nodePackage"]["interfaces"]
        assets = package["nodePackage"]["assets"]

        # loop thru interfaces to get the asset name of the corresponding
        # interface
        asset_name = "not_found_yet"
        for dicts in interfaces:
            if dicts["name"] == name_in_interfaces_pjson:
                asset_name = dicts["asset"]

        if asset_name == "not_found_yet":
            raise ValueError(
                'Exception Class : ModelClass, Exception Method : __iter__, Exception Message : Asset Not Found in package.json interfaces')

        try:
            # get inference
            model_name = emulator_model_name

            with nullify_output(suppress_stdout=True, suppress_stderr=True):
                model = dlr.DLRModel('{}/panorama_sdk/models/{}'.format(workdir, model_name))
                output = model.run(self.input_val1)

            if len(output) == 3 and list(
                    self.input_val1.keys())[0] == 'data':  # OD model
                k = -1
                class_data = None
                bbox_data = None
                conf_data = None

                output_final = []

                for data in output:
                    k += 1
                    if k == 0:
                        class_data = data
                        output_final.append(class_data)
                    if k == 1:
                        conf_data = data
                        output_final.append(conf_data)
                    if k == 2:
                        bbox_data = data
                        output_final.append(bbox_data)

            else:
                output_final = output

        except Exception as e:
            raise ValueError(
                'Exception Class : ModelClass, Exception Method : __iter__, Exception Message {}'.format(e))

        return iter(output_final)


#### OUTPUT CLASS #######

class OutputClass(object):
    """
    Output Class is a helper function for Port Class

    Parameters
    ----------
    initial : Frame Object to be displayed

    Methods
    -------
    None

    """

    def __init__(self, initial=None):
        try:
            self._list = initial
            for img in self._list:
                plt.imshow(img.image)
                plt.show()
                clear_output(wait=True)
        except Exception as e:
            raise ValueError(
                'Exception Class : OutputClass, Exception Method : __init__, Exception Message {}'.format(e))


################# CLASS DEFS DONE ##########################

node_dict = getgraphdata().getlistofnodes()
edge_dict = getgraphdata().getlistofedges()


class node(object):
    """
    This class is implemented to mimic Panoroma Node Class.

    ...

    Attributes
    ----------

    Methods
    -------
    """

    inputs = AccessWithDot(node_dict)
    try:
        output_name = getgraphdata().getoutputsfrompackagejson()
        outputs = AccessWithDot(
            {output_name: AccessWithDot({'put': OutputClass})})
    except Exception as e:
        raise ValueError(e)
        log_p.info('{}'.format(e))

    call = ModelClass