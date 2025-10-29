
import os
import subprocess
import paramiko
from datetime import datetime
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from config import logger, vm_base_dir

def find_vm_file(vm_name):
    """查找虚拟机文件"""
    try:
        # 如果vm_name已经是完整路径，直接检查是否存在
        if vm_name.endswith('.vmx') and os.path.exists(vm_name):
            return vm_name

        # 如果是完整路径但文件不存在，记录警告
        if vm_name.endswith('.vmx'):
            return None
            
        vm_dir = vm_base_dir
        if os.path.exists(vm_dir):
            # 首先尝试精确匹配
            for root, dirs, files in os.walk(vm_dir):
                for file in files:
                    if file.endswith('.vmx') and file == f"{vm_name}.vmx":
                        return os.path.join(root, file)
            
            # 如果精确匹配失败，尝试模糊匹配
            for root, dirs, files in os.walk(vm_dir):
                for file in files:
                    if file.endswith('.vmx') and vm_name.lower() in file.lower():
                        return os.path.join(root, file)
        return None

    except Exception as e:
        logger.error(f"查找虚拟机文件失败: {str(e)}")
        return None

def get_vm_ip(vm_name):
    """获取虚拟机IP地址，优先用vmrun getGuestIPAddress"""
    try:
        # 1. 通过vmrun getGuestIPAddress
        vm_file = find_vm_file(vm_name)
        if vm_file:
            vmrun_path = get_vmrun_path()
            
            if os.path.exists(vmrun_path):
                try:
                    cmd = [vmrun_path, 'getGuestIPAddress', vm_file, '-wait']
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    
                    if result.returncode == 4294967295:
                        return None

                    if result.returncode == 0:
                        ip = result.stdout.strip()
                        if is_valid_ip(ip):
                            return ip
                        else:
                            logger.warning(f"vmrun返回的IP格式无效: {ip}")
                    else:
                        logger.warning(f"vmrun命令执行失败，返回码: {result.returncode}, 错误: {result.stderr}")
                except Exception as e:
                    logger.error(f"未获取IP地址,虚拟机正在启动中!")
            else:
                logger.warning(f"vmrun路径不存在: {vmrun_path}")
        else:
            logger.warning(f"未找到虚拟机文件: {vm_name}")

        # 2. 兜底：从VMX文件读取
        if vm_file and os.path.exists(vm_file):
            logger.debug(f"尝试从VMX文件读取IP: {vm_file}")
            try:
                with open(vm_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    lines = content.split('\n')
                    for line in lines:
                        if 'ip=' in line.lower() or 'ipaddress=' in line.lower():
                            ip = line.split('=')[1].strip().strip('"')
                            if is_valid_ip(ip):
                                return ip
                            else:
                                logger.warning(f"VMX文件中的IP格式无效: {ip}")
            except Exception as e:
                logger.error(f"从VMX文件读取IP失败: {str(e)}")

        logger.warning(f"无法获取虚拟机 {vm_name} 的IP地址")
        return None
    except Exception as e:
        logger.error(f"获取虚拟机IP失败: {str(e)}")
        return None

def is_valid_ip(ip):
    """验证IP地址格式"""
    if not ip:
        return False

    try:
        parts = ip.split('.')
        if len(parts) != 4:
            return False

        for part in parts:
            if not part.isdigit():
                return False
            num = int(part)
            if num < 0 or num > 255:
                return False

        return True
    except:
        return False

def ping_vm_ip(ip_address, timeout=3):
    """检测虚拟机IP是否存活"""
    try:
        if os.name == 'nt':  # Windows
            cmd = ['ping', '-n', '1', '-w', str(timeout * 1000), ip_address]
        else:  # Linux/Mac
            cmd = ['ping', '-c', '1', '-W', str(timeout), ip_address]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 2)
        return result.returncode == 0
    except Exception as e:
        logger.debug(f"Ping {ip_address} 失败: {str(e)}")
        return False

def check_ssh_connectivity(ip_address, username, timeout=10):
    """检查SSH连通性 - 使用app.utils.ssh_utils中的实现"""
    try:
        # 从app.utils.ssh_utils导入check_ssh_connectivity函数
        from app.utils.ssh_utils import check_ssh_connectivity as ssh_check_connectivity
        return ssh_check_connectivity(ip_address, username, timeout=timeout)
    except Exception as e:
        logger.error(f"调用SSH连通性检查失败: {str(e)}")
        return False

def check_ssh_connectivity_old(ip_address, username, timeout=10):
    """旧的SSH连通性检测实现（已弃用）"""
    try:
        # 使用新的SSH工具类实现
        from app.utils.ssh_utils import check_ssh_connectivity as new_check_ssh_connectivity
        return new_check_ssh_connectivity(ip_address, username, timeout=timeout)
    except Exception as e:
        logger.error(f"调用SSH连通性检查失败: {str(e)}")
        return False

def get_vmrun_path():
    """获取vmrun工具路径"""
    try:
        from ..config import vmrun_path
        return vmrun_path
    except ImportError:
        # 默认路径
        default_path = "C:\\Program Files (x86)\\VMware\\VMware Workstation\\vmrun.exe"
        return default_path



def execute_remote_script(ip, username, script_name):
    """通过SSH互信执行目录脚本并获取输出"""
    try:
        # 构建详细的SSH调用日志
        ssh_log = []
        ssh_log.append(f"[SSH] 开始连接到远程主机: {ip}")
        ssh_log.append(f"[SSH] 用户名: {username}")
        ssh_log.append(f"[SSH] 目标脚本: {script_name}")

        # 创建SSH客户端
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_log.append("[SSH] SSH客户端创建成功")

        # 通过SSH互信连接到远程主机（无需密码）
        ssh_log.append(f"[SSH] 正在建立SSH连接...")
        try:
            ssh.connect(ip, username=username, timeout=10, look_for_keys=True, allow_agent=True)
            ssh_log.append("[SSH] SSH连接建立成功")
        except paramiko.AuthenticationException:
            # 密钥认证失败，尝试密码认证并自动设置互信
            ssh_log.append("[SSH] 密钥认证失败，尝试密码认证")
            try:
                ssh.connect(ip, username=username, password=vm_password, timeout=10)
                ssh_log.append("[SSH] 密码认证成功，开始设置SSH互信")

                # 设置SSH互信
                success, message = setup_ssh_trust(ip, username, vm_password)
                if success:
                    ssh_log.append("[SSH] SSH互信设置成功")
                    # 清理缓存
                    vm_name = get_vm_name_by_ip(ip)
                    if vm_name:
                        vm_cache.clear_cache(vm_name, 'online_status')
                else:
                    ssh_log.append(f"[SSH] SSH互信设置失败: {message}")
            except Exception as pwd_e:
                ssh_log.append(f"[SSH] 密码认证也失败: {str(pwd_e)}")
                ssh.close()
                return False, f"SSH连接失败: {str(pwd_e)}", "\n".join(ssh_log)

        # 检查脚本是否存在
        check_command = f"ls -la {script_name}"
        #  ssh_log.append(f"[SSH] 检查脚本是否存在: {check_command}")
        stdin, stdout, stderr = ssh.exec_command(check_command)
        check_output = stdout.read().decode().strip()
        check_error = stderr.read().decode().strip()

        if not check_output:
            ssh_log.append(f"[SSH] 脚本不存在: {script_name}")
            ssh.close()
            return False, f"脚本 {script_name} 不存在", "\n".join(ssh_log)

        ssh_log.append(f"[SSH] 脚本存在: {check_output}")

        # 检查脚本执行权限
        chmod_command = f"chmod +x {script_name}"
        ssh_log.append(f"[SSH] 添加执行权限: {chmod_command}")
        stdin, stdout, stderr = ssh.exec_command(chmod_command)
        chmod_error = stderr.read().decode().strip()
        if chmod_error:
            ssh_log.append(f"[SSH] 添加执行权限失败: {chmod_error}")
        else:
            ssh_log.append("[SSH] 执行权限添加成功")

        # 执行家目录脚本命令
        command = f"{script_name}"
        ssh_log.append(f"[SSH] 执行脚本命令: {command}")

        stdin, stdout, stderr = ssh.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()

        ssh_log.append(f"[SSH] 脚本执行完成，退出状态: {exit_status}")

        if output:
            ssh_log.append(f"[SSH] 脚本输出长度: {len(output)} 字符")
        if error:
            ssh_log.append(f"[SSH] 脚本错误输出长度: {len(error)} 字符")

        ssh.close()
        ssh_log.append("[SSH] SSH连接已关闭")

        # 构建完整的执行日志
        full_log = "\n".join(ssh_log)

        if exit_status == 0:
            # logger.info(f"脚本 {script_name} 执行成功，输出长度: {len(output)}")
            return True, output, full_log
        else:
            error_msg = error if error else f"脚本 {script_name} 执行失败，退出状态: {exit_status}"
            # logger.error(f"脚本 {script_name} 执行失败: {error_msg}")
            return False, error_msg, full_log

    except ImportError:
        # logger.error("paramiko库未安装")
        return False, "需要安装paramiko库: pip install paramiko", "paramiko库未安装"
    except Exception as e:
        #  logger.error(f"execute_remote_script异常: {str(e)}")
        error_msg = f"通过SSH互信执行脚本时发生错误: {str(e)}"
        return False, error_msg, f"[SSH] 连接异常: {str(e)}"

