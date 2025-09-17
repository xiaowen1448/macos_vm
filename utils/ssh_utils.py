#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSH工具类 - 使用paramiko实现SSH和SCP功能
替代系统的ssh和scp命令，提供统一的SSH操作接口
"""

import os
import stat
import logging
import paramiko
from typing import Tuple, Optional
from scp import SCPClient

logger = logging.getLogger(__name__)

class SSHClient:
    """SSH客户端工具类"""
    
    def __init__(self, hostname: str, username: str, password: str = None, port: int = 22, timeout: int = 10):
        """
        初始化SSH客户端
        
        Args:
            hostname: 主机地址
            username: 用户名
            password: 密码（可选，优先使用密钥认证）
            port: SSH端口，默认22
            timeout: 连接超时时间，默认10秒
        """
        self.hostname = hostname
        self.username = username
        self.password = password
        self.port = port
        self.timeout = timeout
        self.ssh_client = None
        self.connected = False
    
    def connect(self) -> Tuple[bool, str]:
        """
        建立SSH连接
        
        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 优先尝试密钥认证，然后是密码认证
            connect_kwargs = {
                'hostname': self.hostname,
                'username': self.username,
                'port': self.port,
                'timeout': self.timeout,
                'look_for_keys': True,
                'allow_agent': True
            }
            
            if self.password:
                connect_kwargs['password'] = self.password
            
            self.ssh_client.connect(**connect_kwargs)
            self.connected = True
            logger.debug(f"SSH连接成功: {self.username}@{self.hostname}:{self.port}")
            return True, "SSH连接成功"
            
        except paramiko.AuthenticationException:
            error_msg = "SSH认证失败，请检查用户名、密码或密钥"
            logger.error(f"SSH认证失败: {self.hostname}")
            return False, error_msg
        except paramiko.SSHException as e:
            error_msg = f"SSH连接异常: {str(e)}"
            logger.error(f"SSH连接异常: {self.hostname} - {str(e)}")
            return False, error_msg
        except Exception as e:
            error_msg = f"SSH连接失败: {str(e)}"
            logger.error(f"SSH连接失败: {self.hostname} - {str(e)}")
            return False, error_msg
    
    def execute_command(self, command: str, timeout: int = 30) -> Tuple[bool, str, str, int]:
        """
        执行SSH命令
        
        Args:
            command: 要执行的命令
            timeout: 命令执行超时时间
            
        Returns:
            Tuple[bool, str, str, int]: (是否成功, 标准输出, 标准错误, 退出码)
        """
        if not self.connected or not self.ssh_client:
            return False, "", "SSH未连接", -1
        
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(command, timeout=timeout)
            
            # 获取退出码
            exit_status = stdout.channel.recv_exit_status()
            
            # 读取输出
            stdout_data = stdout.read().decode('utf-8', errors='ignore').strip()
            stderr_data = stderr.read().decode('utf-8', errors='ignore').strip()
            
            success = exit_status == 0
            logger.debug(f"SSH命令执行完成: {command} (退出码: {exit_status})")
            
            return success, stdout_data, stderr_data, exit_status
            
        except Exception as e:
            error_msg = f"执行SSH命令失败: {str(e)}"
            logger.error(f"SSH命令执行异常: {command} - {str(e)}")
            return False, "", error_msg, -1
    
    def upload_file(self, local_path: str, remote_path: str) -> Tuple[bool, str]:
        """
        上传文件到远程主机
        
        Args:
            local_path: 本地文件路径
            remote_path: 远程文件路径
            
        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        if not self.connected or not self.ssh_client:
            return False, "SSH未连接"
        
        if not os.path.exists(local_path):
            return False, f"本地文件不存在: {local_path}"
        
        try:
            with SCPClient(self.ssh_client.get_transport()) as scp:
                scp.put(local_path, remote_path)
            
            logger.debug(f"文件上传成功: {local_path} -> {remote_path}")
            return True, "文件上传成功"
            
        except Exception as e:
            error_msg = f"文件上传失败: {str(e)}"
            logger.error(f"SCP上传异常: {local_path} -> {remote_path} - {str(e)}")
            return False, error_msg
    
    def download_file(self, remote_path: str, local_path: str) -> Tuple[bool, str]:
        """
        从远程主机下载文件
        
        Args:
            remote_path: 远程文件路径
            local_path: 本地文件路径
            
        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        if not self.connected or not self.ssh_client:
            return False, "SSH未连接"
        
        try:
            # 确保本地目录存在
            local_dir = os.path.dirname(local_path)
            if local_dir and not os.path.exists(local_dir):
                os.makedirs(local_dir, exist_ok=True)
            
            with SCPClient(self.ssh_client.get_transport()) as scp:
                scp.get(remote_path, local_path)
            
            logger.debug(f"文件下载成功: {remote_path} -> {local_path}")
            return True, "文件下载成功"
            
        except Exception as e:
            error_msg = f"文件下载失败: {str(e)}"
            logger.error(f"SCP下载异常: {remote_path} -> {local_path} - {str(e)}")
            return False, error_msg
    
    def check_file_exists(self, remote_path: str) -> bool:
        """
        检查远程文件是否存在
        
        Args:
            remote_path: 远程文件路径
            
        Returns:
            bool: 文件是否存在
        """
        success, stdout, stderr, exit_code = self.execute_command(f'test -f "{remote_path}" && echo "exists"')
        return success and stdout.strip() == "exists"
    
    def create_directory(self, remote_path: str, mode: int = 0o755) -> Tuple[bool, str]:
        """
        在远程主机创建目录
        
        Args:
            remote_path: 远程目录路径
            mode: 目录权限，默认755
            
        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        success, stdout, stderr, exit_code = self.execute_command(f'mkdir -p "{remote_path}"')
        if success:
            # 设置目录权限
            self.execute_command(f'chmod {oct(mode)[2:]} "{remote_path}"')
            return True, "目录创建成功"
        else:
            return False, f"目录创建失败: {stderr}"
    
    def set_file_permissions(self, remote_path: str, mode: int) -> Tuple[bool, str]:
        """
        设置远程文件权限
        
        Args:
            remote_path: 远程文件路径
            mode: 文件权限
            
        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        success, stdout, stderr, exit_code = self.execute_command(f'chmod {oct(mode)[2:]} "{remote_path}"')
        if success:
            return True, "权限设置成功"
        else:
            return False, f"权限设置失败: {stderr}"
    
    def close(self):
        """
        关闭SSH连接
        """
        if self.ssh_client:
            self.ssh_client.close()
            self.connected = False
            logger.debug(f"SSH连接已关闭: {self.hostname}")
    
    def __enter__(self):
        """上下文管理器入口"""
        success, message = self.connect()
        if not success:
            raise Exception(f"SSH连接失败: {message}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()


def setup_ssh_trust(hostname: str, username: str, password: str) -> Tuple[bool, str]:
    """
    设置SSH互信（公钥认证）
    
    Args:
        hostname: 主机地址
        username: 用户名
        password: 密码
        
    Returns:
        Tuple[bool, str]: (是否成功, 消息)
    """
    try:
        # 1. 生成SSH密钥对（如果不存在）
        ssh_key_path = os.path.expanduser('~/.ssh/id_rsa')
        ssh_pub_key_path = os.path.expanduser('~/.ssh/id_rsa.pub')
        
        # 确保.ssh目录存在
        ssh_dir = os.path.expanduser('~/.ssh')
        if not os.path.exists(ssh_dir):
            os.makedirs(ssh_dir, mode=0o700)
        
        # 生成密钥对（如果不存在）
        if not os.path.exists(ssh_key_path):
            key = paramiko.RSAKey.generate(2048)
            key.write_private_key_file(ssh_key_path)
            
            # 设置私钥文件权限
            os.chmod(ssh_key_path, stat.S_IRUSR | stat.S_IWUSR)
            
            # 生成公钥文件
            with open(ssh_pub_key_path, 'w') as f:
                f.write(f"{key.get_name()} {key.get_base64()} generated-by-paramiko\n")
            
            logger.debug("SSH密钥对生成成功")
        
        # 读取公钥
        if not os.path.exists(ssh_pub_key_path):
            return False, "SSH公钥文件不存在"
        
        with open(ssh_pub_key_path, 'r') as f:
            public_key = f.read().strip()
        
        # 2. 连接到远程主机并设置公钥认证
        with SSHClient(hostname, username, password) as ssh:
            # 创建.ssh目录
            ssh.create_directory('~/.ssh', 0o700)
            
            # 添加公钥到authorized_keys
            success, stdout, stderr, exit_code = ssh.execute_command(
                f'echo "{public_key}" >> ~/.ssh/authorized_keys'
            )
            
            if not success:
                return False, f"添加公钥失败: {stderr}"
            
            # 设置authorized_keys权限
            ssh.set_file_permissions('~/.ssh/authorized_keys', 0o600)
            
            # 验证公钥是否添加成功
            success, stdout, stderr, exit_code = ssh.execute_command('cat ~/.ssh/authorized_keys')
            if success and public_key.split()[1] in stdout:
                logger.info(f"SSH互信设置成功: {hostname}")
                return True, "SSH互信设置成功"
            else:
                return False, "SSH互信验证失败"
                
    except Exception as e:
        error_msg = f"设置SSH互信时发生错误: {str(e)}"
        logger.error(f"SSH互信设置异常: {hostname} - {str(e)}")
        return False, error_msg


def check_ssh_connectivity(hostname: str, username: str, password: str = None, timeout: int = 10) -> bool:
    """
    检查SSH连通性
    
    Args:
        hostname: 主机地址
        username: 用户名
        password: 密码（可选）
        timeout: 超时时间
        
    Returns:
        bool: 是否连通
    """
    try:
        with SSHClient(hostname, username, password, timeout=timeout) as ssh:
            success, stdout, stderr, exit_code = ssh.execute_command('echo "ssh_test"', timeout=5)
            return success and stdout.strip() == 'ssh_test'
    except Exception as e:
        logger.debug(f"SSH连通性检查失败: {hostname} - {str(e)}")
        return False


def check_ssh_trust_status(hostname: str, username: str, timeout: int = 10) -> bool:
    """
    检查SSH互信状态
    
    Args:
        hostname: 主机地址
        username: 用户名
        timeout: 超时时间
        
    Returns:
        bool: 是否已建立互信
    """
    try:
        # 尝试无密码连接
        with SSHClient(hostname, username, timeout=timeout) as ssh:
            success, stdout, stderr, exit_code = ssh.execute_command('echo "ssh_trust_test"', timeout=5)
            return success and stdout.strip() == 'ssh_trust_test'
    except Exception as e:
        logger.debug(f"SSH互信状态检查失败: {hostname} - {str(e)}")
        return False