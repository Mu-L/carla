from experiments.base_experiment import *
from helper.CarlaHelper import spawn_vehicle_at, post_process_image, update_config
import random
import numpy as np
from gym.spaces import Box
from itertools import cycle
import cv2
import time
import carla
import gc
from PIL import Image

SERVER_VIEW_CONFIG = {
}

SENSOR_CONFIG = {
    "CAMERA_NORMALIZED": [True], # apparently doesnt work if set to false, its just for the image!
    "CAMERA_GRAYSCALE": [True],
    "FRAMESTACK": 4,
}

BIRDVIEW_CONFIG = {
    "SIZE": 190,
    "RADIUS": 15,
    "FRAMESTACK": 1
}

OBSERVATION_CONFIG = {
    "CAMERA_OBSERVATION": [False],
    "BIRDVIEW_OBSERVATION": True,
}

EXPERIMENT_CONFIG = {
    "OBSERVATION_CONFIG": OBSERVATION_CONFIG,
    "Server_View": SERVER_VIEW_CONFIG,
    "SENSOR_CONFIG": SENSOR_CONFIG,
    "server_map": "Town02_Opt",
    "BIRDVIEW_CONFIG": BIRDVIEW_CONFIG,
    "n_vehicles": 0,
    "n_walkers": 0,
    "hero_vehicle_model": "vehicle.lincoln.mkz2017",
}

class Experiment(BaseExperiment):
    def __init__(self):
        config=update_config(BASE_EXPERIMENT_CONFIG, EXPERIMENT_CONFIG)
        super().__init__(config)

    def initialize_reward(self, core):
        """
        Generic initialization of reward function
        :param core:
        :return:
        """
        self.previous_distance = 0
        self.i = 0
        self.frame_stack = 1  # can be 1,2,3,4
        self.prev_image_0 = None
        self.prev_image_1 = None
        self.prev_image_2 = None
        self.allowed_types = [carla.LaneType.Driving, carla.LaneType.Parking]

    def set_observation_space(self):
        num_of_channels = 3
        image_space = Box(
            low=0.0,
            high=255.0,
            shape=(
                self.experiment_config["BIRDVIEW_CONFIG"]["SIZE"],
                self.experiment_config["BIRDVIEW_CONFIG"]["SIZE"],
                num_of_channels * self.experiment_config["BIRDVIEW_CONFIG"]["FRAMESTACK"],
            ),
            dtype=np.uint8,
        )
        self.observation_space = image_space

    def process_observation(self, core, observation):
        """
        Process observations according to your experiment
        :param core:
        :param observation:
        :return:
        """
        # if self.i % 1000 == 0:
        #     img = Image.fromarray(observation["birdview"], 'RGB')
        #     img.show()
        # self.i += 1

        self.set_server_view(core)
        image = post_process_image(observation['birdview'],
                                   normalized = False,
                                   grayscale = False
        )

        if self.prev_image_0 is None:
            self.prev_image_0 = image
            self.prev_image_1 = self.prev_image_0
            self.prev_image_2 = self.prev_image_1

        images = image

        if self.frame_stack >= 2:
            images = np.concatenate([self.prev_image_0, images], axis=2)
        if self.frame_stack >= 3 and images is not None:
            images = np.concatenate([self.prev_image_1, images], axis=2)
        if self.frame_stack >= 4 and images is not None:
            images = np.concatenate([self.prev_image_2, images], axis=2)

        self.prev_image_2 = self.prev_image_1
        self.prev_image_1 = self.prev_image_0
        self.prev_image_0 = image

        return images

    def inside_lane(self, map):
        self.current_w = map.get_waypoint(self.hero.get_location(), lane_type=carla.LaneType.Any)
        return self.current_w.lane_type in self.allowed_types

    def dist_to_driving_lane(self, map_):
        cur_loc = self.hero.get_location()
        cur_w = map_.get_waypoint(cur_loc)
        return math.sqrt((cur_loc.x - cur_w.transform.location.x)**2 +
                         (cur_loc.y - cur_w.transform.location.y)**2)

    def deviation_dot_product(self, reference_location, heading_vector):
        target_location = self.route[0].transform.location
        next_vector = target_location - reference_location
        next_vector.z = 0.0
        next_vector = [next_vector.x, next_vector.y, next_vector.z]
        heading_vector = [heading_vector.x, heading_vector.y, heading_vector.z]
        return np.dot(next_vector, heading_vector) <= 0.0

    def compute_reward(self, core, observation, map_, action):
        """
        Reward function
        :param observation:
        :param core:
        :return:
        """

        reward = 0
        reference_location = self.hero.get_location()
        heading_vector = self.hero.get_transform().get_forward_vector()
        heading_vector.z = 0.0

        c = float(np.sqrt(np.square(self.hero.get_location().x - self.route[0].transform.location.x) + \
            np.square(self.hero.get_location().y - self.route[0].transform.location.y)))

        while self.deviation_dot_product(reference_location, heading_vector) and c < 1.0:
            reward += 1
            self.route.pop(0)
            self.route.append(random.choice(self.route[-1].next(5)))
            c = float(np.sqrt(np.square(self.hero.get_location().x - self.route[0].transform.location.x) + \
                    np.square(self.hero.get_location().y - self.route[0].transform.location.y)))

        if reward > 0:
            print("Reward: {}".format(reward))
        return reward

    # def compute_reward(self, core, observation, map, action):
    #     """
    #     Reward function
    #     :param observation:
    #     :param core:
    #     :return:
    #     """
    #     def nearest_wp(loc):
    #         nearest_wp = (None, 9999999999)
    #         for wp in self.route:
    #             d = math.sqrt(
    #                 (wp.transform.location.x - loc.x)**2 +
    #                 (wp.transform.location.y - loc.y)**2
    #             )
    #             if d < nearest_wp[1]:
    #                 nearest_wp = (wp, d)

    #         return nearest_wp

    #     wp, dist = nearest_wp(self.hero.get_location())
    #     if wp is None or dist > 5:
    #         reward = -0.1
    #     else:
    #         reward = 1
    #         self.route.remove(wp)

    #     print("Reward: {}".format(reward))
    #     return reward