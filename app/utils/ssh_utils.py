#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSH工具类 - 使用paramiko实现SSH和SCP功能
替代系统的ssh和scp命令，提供统一的SSH操作接口
"""

import os
import stat
import logging
import socket
import time
import sys
import paramiko
import subprocess
from typing import Tuple, Optional
# 导入日志工具和全局logger
from app.utils.log_utils import logger, logging
from app.utils.vm_cache import vm_cache, VMStatusCache
from scp import SCPClient
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from config import *

# 导入日志工具
from app.utils.log_utils import get_logger

logger = get_logger(__name__)

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
        建立SSH连接 - 优先尝试免密认证，失败后尝试密码认证
        
        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 1. 首先尝试纯免密认证
           # logger.debug(f"[SSH] 尝试免密认证连接到 {self.username}@{self.hostname}:{self.port}")
            try:
                connect_kwargs = {
                    'hostname': self.hostname,
                    'username': self.username,
                    'port': self.port,
                    'timeout': self.timeout,
                    'look_for_keys': True,
                    'allow_agent': True,
                    'password': None  # 明确不使用密码
                }
                self.ssh_client.connect(**connect_kwargs)
                self.connected = True
             #   logger.debug(f"[SSH] 免密认证成功: {self.username}@{self.hostname}:{self.port}")
                return True, "SSH免密连接成功"
            except paramiko.AuthenticationException:
               # logger.debug(f"[SSH] 免密认证失败，尝试密码认证: {self.hostname}")
                # 免密失败，关闭当前client重新创建
                if self.ssh_client:
                    self.ssh_client.close()
                self.ssh_client = paramiko.SSHClient()
                self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 2. 免密失败后，尝试密码认证
            if self.password:
               # logger.debug(f"[SSH] 尝试密码认证连接到 {self.username}@{self.hostname}:{self.port}")
                connect_kwargs = {
                    'hostname': self.hostname,
                    'username': self.username,
                    'port': self.port,
                    'timeout': self.timeout,
                    'password': self.password,
                    'look_for_keys': False,  # 密码认证时不查找密钥
                    'allow_agent': False
                }
                self.ssh_client.connect(**connect_kwargs)
                self.connected = True
             #   logger.debug(f"[SSH] 密码认证成功: {self.username}@{self.hostname}:{self.port}")
                return True, "SSH密码连接成功"
            else:
              #  logger.error(f"[SSH] 免密认证失败且未提供密码: {self.hostname}")
                return False, "免密认证失败且未提供密码"
            
        except paramiko.AuthenticationException:
            error_msg = "SSH密码认证失败，请检查用户名和密码"
          #  logger.error(f"[SSH] 密码认证失败: {self.hostname}")
            return False, error_msg
        except paramiko.SSHException as e:
            error_msg = f"SSH连接异常: {str(e)}"
           # logger.error(f"[SSH] 连接异常: {self.hostname} - {str(e)}")
            return False, error_msg
        except Exception as e:
            error_msg = f"SSH连接失败: {str(e)}"
           # logger.error(f"[SSH] 连接失败: {self.hostname} - {str(e)}")
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
           # logger.debug(f"SSH命令执行完成: {command} (退出码: {exit_status})")
            
            return success, stdout_data, stderr_data, exit_status
            
        except Exception as e:
            error_msg = f"执行SSH命令失败: {str(e)}"
           # logger.error(f"SSH命令执行异常: {command} - {str(e)}")
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
            
         #   logger.debug(f"文件下载成功: {remote_path} -> {local_path}")
            return True, "文件下载成功"
            
        except Exception as e:
            error_msg = f"文件下载失败: {str(e)}"
          #  logger.error(f"SCP下载异常: {remote_path} -> {local_path} - {str(e)}")
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
          #  logger.debug(f"SSH连接已关闭: {self.hostname}")
    
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
       # logger.debug(f"SSH连通性检查失败: {hostname} - {str(e)}")
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



def send_file_via_sftp(local_path, remote_path, ip, username, timeout=30):
    """使用paramiko SFTP发送文件到远程主机"""
    try:
        # 创建SSH客户端
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            # 首先尝试密钥认证
            ssh.connect(ip, username=username, timeout=timeout, look_for_keys=True, allow_agent=True)
        except paramiko.AuthenticationException:
            # 密钥认证失败，尝试密码认证并自动设置互信
            logger.info(f"密钥认证失败，尝试密码认证: {ip}")
            try:
                ssh.connect(ip, username=username, password=vm_password, timeout=timeout)
                logger.info(f"密码认证成功，开始设置SSH互信: {ip}")

                # 设置SSH互信
                success, message = setup_ssh_trust(ip, username, vm_password)
                if success:
                    logger.info(f"SSH互信设置成功: {ip}")
                    # 清理缓存
                    vm_cache.clear_cache(get_vm_name_by_ip(ip), 'online_status')
                else:
                    logger.warning(f"SSH互信设置失败: {ip} - {message}")
            except Exception as pwd_e:
                ssh.close()
                return False, f"密码认证也失败: {str(pwd_e)}"

        # 创建SFTP客户端
        sftp = ssh.open_sftp()

        # 确保远程目录存在
        remote_dir = os.path.dirname(remote_path)
        if remote_dir:
            try:
                sftp.mkdir(remote_dir)
            except IOError:
                # 目录可能已存在，忽略错误
                pass

        # 传输文件
        sftp.put(local_path, remote_path)

        # 关闭连接
        sftp.close()
        ssh.close()

        return True, "文件传输成功"

    except ImportError:
        return False, "需要安装paramiko库: pip install paramiko"
    except Exception as e:
        return False, f"SFTP传输失败: {str(e)}"


def check_ssh_status(ip):
    """检查SSH连接状态"""
    if not ip:
        return 'offline'

    try:
        # 简单的ping测试
        result = subprocess.run(['ping', '-n', '1', ip], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return 'online'
        else:
            return 'offline'

    except Exception as e:
        logger.info(f"[DEBUG] SSH状态检查失败: {str(e)}")
        return 'offline'


def check_ssh_port_open(ip, port=22):
    """检查SSH端口是否开放 - 增强版（修复Windows环境下的检测问题）"""
    # 导入必要的模块

    
    if not ip:
        logger.debug("IP地址为空，无法检查SSH端口")
        return False

    logger.info(f"开始检查SSH端口 {port} 是否开放: {ip}")
    
    # 增加尝试次数，提高检测准确性
    max_attempts = 5  # 增加到5次尝试
    success_count = 0
    
    for attempt in range(max_attempts):
        sock = None
        try:
            # 创建socket连接 - 添加更多参数确保稳定性
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # 禁用Nagle算法，提高实时性
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            # 增加超时时间，特别是在Windows环境下
            timeout = 10 if attempt == 0 else 6
            sock.settimeout(timeout)
            logger.debug(f"尝试 #{attempt+1}/{max_attempts}，超时设置: {timeout}秒")

            # 尝试连接SSH端口
            start_time = time.time()
            result = sock.connect_ex((ip, port))
            elapsed = time.time() - start_time
            
            if result == 0:
                success_count += 1
                logger.info(f"✅ SSH端口 {port} 检测成功 (尝试 {attempt+1}/{max_attempts}, 耗时: {elapsed:.3f}秒): {ip}")
                # 只要有一次成功就认为端口开放（修复之前的严格逻辑）
                return True
            else:
                logger.debug(f"❌ SSH端口 {port} 检测失败 (尝试 {attempt+1}/{max_attempts}, 错误码: {result}, 耗时: {elapsed:.3f}秒): {ip}")
                
            # 短暂延迟后重试，避免过快重试
            time.sleep(0.8)

        except socket.timeout:
            logger.debug(f"⌛ SSH端口检测超时 (尝试 {attempt+1}/{max_attempts}): {ip}")
            time.sleep(0.8)
        except Exception as e:
            logger.debug(f"❗ SSH端口检测异常 (尝试 {attempt+1}/{max_attempts}): {str(e)}")
            time.sleep(0.8)
        finally:
            if sock:
                try:
                    sock.close()
                except:
                    pass
    
    # 如果所有尝试都失败，最后进行一次直接连接测试作为验证
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(8)
        result = sock.connect_ex((ip, port))
        if result == 0:
            logger.info(f"✅ 最终验证：SSH端口 {port} 开放: {ip}")
            return True
    except Exception as e:
        logger.debug(f"最终验证异常: {str(e)}")
    finally:
        if sock:
            try:
                sock.close()
            except:
                pass
    
    logger.info(f"❌ SSH端口 {port} 在 {max_attempts} 次尝试后仍未开放: {ip}")
    return False


def check_ssh_trust_status_old(ip, username=vm_username):
    """旧的SSH互信状态检查实现（已弃用）"""
    # 使用新的SSH工具类实现
    from app.utils.ssh_utils import check_ssh_trust_status as new_check_ssh_trust_status
    return new_check_ssh_trust_status(ip, username)



def execute_chmod_scripts(ip, username, script_names=None):
    """远程执行chmod +x命令"""
    logger.info(f"开始为IP {ip} 的用户 {username} 添加脚本执行权限")
    try:
        # 创建SSH客户端
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # 连接到远程主机（使用SSH互信，无需密码）
        logger.debug(f"尝试连接到 {ip}")
        ssh.connect(ip, username=username, timeout=10)
        logger.debug("SSH连接成功")

        # 根据传入的脚本名决定执行方式
        if script_names and len(script_names) > 0:
            # 为指定脚本添加执行权限
            for script_name in script_names:
                # 确保脚本名以.sh结尾
                if script_name.endswith('.sh'):
                    commands = [f"cd {sh_script_remote_path}"]  # 切换到用户脚本上传目录
                    commands.append(f"chmod +x {sh_script_remote_path}{script_name}")
                else:
                    commands = [f"cd {scpt_script_remote_path}"]  # 切换到用户脚本上传目录
                    commands.append(f"chmod +x {scpt_script_remote_path}{script_name}")
            # 列出指定脚本的权限
            script_list = " ".join([name if name.endswith('.sh') else name + '.sh' for name in script_names])
            commands.append(f"ls -la {sh_script_remote_path}{script_list} 2>/dev/null || echo '没有找到指定的脚本文件'")

            logger.debug(f"为指定脚本添加执行权限: {script_names}")
        else:
            # 为所有sh脚本添加执行权限
            commands = [
                f"cd {sh_script_remote_path}",  # 切换到用户家目录
                f"chmod +x {sh_script_remote_path}*.sh",  # 为所有sh脚本添加执行权限
                f"ls -la {sh_script_remote_path}*.sh 2>/dev/null || echo '没有找到.sh文件'"  # 列出所有sh文件及其权限
            ]
        # logger.debug("为所有.sh文件添加执行权限")

        results = []
        for cmd in commands:
            #  logger.debug(f"执行命令: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()

            logger.debug(f"命令 '{cmd}' 执行状态: {exit_status}")
            if output:
                logger.debug(f"输出: {output}")
            if error:
                logger.debug(f"错误: {error}")

            results.append({
                'command': cmd,
                'exit_status': exit_status,
                'output': output,
                'error': error
            })

        ssh.close()

        # 检查执行结果
        chmod_commands = [r for r in results if r['command'].startswith('chmod')]
        ls_result = results[-1]  # 最后一个命令是ls

        # 检查所有chmod命令是否成功
        failed_chmods = [r for r in chmod_commands if r['exit_status'] != 0]

        if not failed_chmods:
            logger.info("chmod命令执行成功")
            if script_names and len(script_names) > 0:
                message = f"成功为指定脚本添加执行权限: {', '.join(script_names)}\n"
            else:
                message = "成功为目录下的所有.sh文件添加执行权限\n"

            if ls_result['output'] and ls_result['output'] != '没有找到.sh文件' and ls_result[
                'output'] != '没有找到指定的脚本文件':
                message += f"文件列表:\n{ls_result['output']}"
            else:
                message += "未找到指定的脚本文件"
            return True, message
        else:
            logger.error(f"部分chmod命令执行失败: {failed_chmods}")
            error_messages = [f"{r['command']}: {r['error']}" for r in failed_chmods]
            return False, f"部分脚本执行权限设置失败: {'; '.join(error_messages)}"

    except ImportError:
        logger.error("paramiko库未安装")
        return False, "需要安装paramiko库: pip install paramiko"
    except Exception as e:
        logger.error(f"execute_chmod_scripts异常: {str(e)}")
        return False, f"远程执行chmod命令时发生错误: {str(e)}"


