#!/usr/bin/env python

import rospy
from geometry_msgs.msg import PoseStamped
from styx_msgs.msg import Lane, Waypoint

import math

#new imports
from scipy.spatial import KDTree
import numpy as np
from std_msgs.msg import Int32

'''
This node will publish waypoints from the car's current position to some `x` distance ahead.

As mentioned in the doc, you should ideally first implement a version which does not care
about traffic lights or obstacles.

Once you have created dbw_node, you will update this node to use the status of traffic lights too.

Please note that our simulator also provides the exact location of traffic lights and their
current status in `/vehicle/traffic_lights` message. You can use this message to build this node
as well as to verify your TL classifier.

TODO (for Yousuf and Aaron): Stopline location for each traffic light.
'''

LOOKAHEAD_WPS = 100 # Number of waypoints we will publish. You can change this number

MAX_DECEL = -2 # - 2 m/sec^2 seems enough

class WaypointUpdater(object):
    def __init__(self):
        rospy.init_node('waypoint_updater')

        rospy.Subscriber('/current_pose', PoseStamped, self.pose_cb)
        rospy.Subscriber('/base_waypoints', Lane, self.waypoints_cb) #is only published once (latched)

        # TODO: Add a subscriber for /traffic_waypoint and /obstacle_waypoint below
        rospy.Subscriber('/traffic_waypoint', Int32, self.traffic_cb)

        self.final_waypoints_pub = rospy.Publisher('final_waypoints', Lane, queue_size=1)
        

        self.pose = None
        self.base_waypoints = None
        self.waypoints_2d = None
        self.waypoint_tree = None
        self.stopline_wp_idx = -1

        self.loop()

    def loop(self):
        rate = rospy.Rate(50)
        while not rospy.is_shutdown():
            if self.pose and self.waypoint_tree:
                closest_waypoint_idx = self.get_closest_waypoint_id()
                self.publish_waypoints(closest_waypoint_idx)
            rate.sleep()
 
    def get_closest_waypoint_id(self):
        #get last obtained car position
        x = self.pose.pose.position.x
        y = self.pose.pose.position.y

        closest_idx = self.waypoint_tree.query([x , y] , 1 ) [1]

        closet_crd = self.waypoints_2d[closest_idx]
        prev_crd   = self.waypoints_2d[closest_idx - 1]

        cl_vect = np.array(closet_crd)
        prev_vect = np.array(prev_crd)
        pos_vect = np.array([x, y])

        #dot product between prev and current postion vector
        val = np.dot(cl_vect - prev_vect, pos_vect - cl_vect)

        if val > 0:
            closest_idx = (closest_idx + 1) % len(self.waypoints_2d)
        return closest_idx

    def publish_waypoints(self , closest_idx):
        lane = Lane()
        lane.header = self.base_waypoints.header
        #lane.waypoints = self.base_waypoints.waypoints[closest_idx : closest_idx + LOOKAHEAD_WPS ]
        farthest_idx = closest_idx + LOOKAHEAD_WPS
        base_waypoints = self.base_waypoints.waypoints[closest_idx : closest_idx + LOOKAHEAD_WPS ]
        
        #check if there is no red light or the red light is very far for us to plan for it
        if self.stopline_wp_idx == -1 or self.stopline_wp_idx >= farthest_idx:
            lane.waypoints = base_waypoints
        else: 
            #now we have to decelerate
            lane.waypoints = self.decelerate_waypoints(base_waypoints , closest_idx)
        self.final_waypoints_pub.publish(lane)

    def decelerate_waypoints(self , waypoints , closest_idx):
        tmp_ret = []

        for i,wp in enumerate(waypoints):
            p = Waypoint()
            p.pose = wp.pose

            stp_idx = max(self.stopline_wp_idx - closest_idx - 3 , 0)
            dist = self.distance(waypoints , i , stp_idx)
            vel = math.sqrt(2 * abs(MAX_DECEL) * dist)
            if vel < 1.0 :
                vel = 0

            p.twist.twist.linear.x = min(vel , wp.twist.twist.linear.x)
            tmp_ret.append(p)
        return tmp_ret

    def pose_cb(self, msg):
        self.pose = msg

    def waypoints_cb(self, waypoints):
        self.base_waypoints = waypoints
        if not self.waypoints_2d:
            self.waypoints_2d = [[waypoint.pose.pose.position.x, waypoint.pose.pose.position.y] for waypoint in waypoints.waypoints ]
            self.waypoint_tree = KDTree(self.waypoints_2d)

    def traffic_cb(self, msg):
        self.stopline_wp_idx = msg.data

    def obstacle_cb(self, msg):
        # TODO: Callback for /obstacle_waypoint message. We will implement it later
        pass

    def get_waypoint_velocity(self, waypoint):
        return waypoint.twist.twist.linear.x

    def set_waypoint_velocity(self, waypoints, waypoint, velocity):
        waypoints[waypoint].twist.twist.linear.x = velocity

    def distance(self, waypoints, wp1, wp2):
        dist = 0
        dl = lambda a, b: math.sqrt((a.x-b.x)**2 + (a.y-b.y)**2  + (a.z-b.z)**2)
        for i in range(wp1, wp2+1):
            dist += dl(waypoints[wp1].pose.pose.position, waypoints[i].pose.pose.position)
            wp1 = i
        return dist


if __name__ == '__main__':
    try:
        WaypointUpdater()
    except rospy.ROSInterruptException:
        rospy.logerr('Could not start waypoint updater node.')
