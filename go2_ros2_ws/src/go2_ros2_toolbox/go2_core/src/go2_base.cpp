#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <geometry_msgs/msg/point_stamped.hpp>
#include <geometry_msgs/msg/twist.hpp>
#include <tf2_ros/transform_broadcaster.h>
#include <geometry_msgs/msg/transform_stamped.hpp>
#include <nav_msgs/msg/odometry.hpp>
#include <tf2/LinearMath/Matrix3x3.h>
#include <tf2/LinearMath/Quaternion.h>
#include <mutex>
#include <cmath>
#include <algorithm>
#include <array>

// For real robot
#include "unitree_api/msg/request.hpp"
#include "common/ros2_sport_client.h"

using namespace std::chrono_literals;

class Go2Base : public rclcpp::Node {
public:
    Go2Base() : Node("go2_base") {
        // 初始化运动客户端
        sport_client_ = std::make_shared<SportClient>();
        
        // 创建TF广播器
        tf_broadcaster_ = std::make_unique<tf2_ros::TransformBroadcaster>(*this);
        
        // 订阅机器人位姿
        pose_sub_ = create_subscription<geometry_msgs::msg::PoseStamped>(
            "/utlidar/robot_pose", 10,
            [this](const geometry_msgs::msg::PoseStamped::SharedPtr msg) {
                handlePose(msg);
            });
            
        // 订阅速度命令
        cmd_vel_sub_ = create_subscription<geometry_msgs::msg::Twist>(
            "/cmd_vel", 10,
            [this](const geometry_msgs::msg::Twist::SharedPtr msg) {
                handleVelocity(msg);
            });
        
        // 创建里程计发布者
        odom_pub_ = create_publisher<nav_msgs::msg::Odometry>("/odom", 10);
        
        // 运动指令发布
        sport_pub_ = create_publisher<unitree_api::msg::Request>("/api/sport/request", 10);
    }

private:
    // 处理位姿消息
    void handlePose(const geometry_msgs::msg::PoseStamped::SharedPtr msg) {
        // 创建TF变换
        geometry_msgs::msg::TransformStamped t;
        
        // 设置变换的时间戳和坐标系
        t.header.stamp = this->now();
        t.header.frame_id = "odom";
        t.child_frame_id = "base_link";
        
        // 设置位置
        t.transform.translation.x = msg->pose.position.x;
        t.transform.translation.y = msg->pose.position.y;
        t.transform.translation.z = msg->pose.position.z;
        
        // 设置旋转
        t.transform.rotation = msg->pose.orientation;
        
        // 发布变换
        tf_broadcaster_->sendTransform(t);

        // 构造并发布Odometry消息
        nav_msgs::msg::Odometry odom_msg;
        odom_msg.header.stamp = t.header.stamp;
        odom_msg.header.frame_id = t.header.frame_id;
        odom_msg.child_frame_id = t.child_frame_id;
        odom_msg.pose.pose = msg->pose;
        // twist默认为0
        odom_pub_->publish(odom_msg);
    }

    // 处理速度命令
    void handleVelocity(const geometry_msgs::msg::Twist::SharedPtr msg) {
        // 直接转发速度命令
        unitree_api::msg::Request req;
        sport_client_->Move(req, 
                          msg->linear.x,
                          msg->linear.y,
                          msg->angular.z);
        sport_pub_->publish(req);
        
        if (msg->linear.x == 0 && msg->linear.y == 0 && msg->angular.z == 0) {
            stopRobot();
        }
    }

    // 停止机器人
    void stopRobot() {
        unitree_api::msg::Request req;
        sport_client_->StopMove(req);
        sport_pub_->publish(req);
    }

    // 成员变量
    std::shared_ptr<SportClient> sport_client_;
    std::unique_ptr<tf2_ros::TransformBroadcaster> tf_broadcaster_;
    
    // ROS接口
    rclcpp::Subscription<geometry_msgs::msg::PoseStamped>::SharedPtr pose_sub_;
    rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr cmd_vel_sub_;
    rclcpp::Publisher<nav_msgs::msg::Odometry>::SharedPtr odom_pub_;
    rclcpp::Publisher<unitree_api::msg::Request>::SharedPtr sport_pub_;
};

int main(int argc, char** argv) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<Go2Base>());
    rclcpp::shutdown();
    return 0;
} 