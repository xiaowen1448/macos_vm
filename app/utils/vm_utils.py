
def find_vm_file(vm_name):
    """查找虚拟机文件"""
    try:
        # 如果vm_name已经是完整路径，直接检查是否存在
        if vm_name.endswith('.vmx') and os.path.exists(vm_name):
            # logger.debug(f"虚拟机文件路径有效: {vm_name}")
            return vm_name

        # 如果是完整路径但文件不存在，记录警告
        if vm_name.endswith('.vmx'):
            # logger.warning(f"虚拟机文件不存在: {vm_name}")
            return None
        vm_dir = vm_base_dir
        if os.path.exists(vm_dir):
            for root, dirs, files in os.walk(vm_dir):
                for file in files:
                    if file.endswith('.vmx') and vm_name in file:
                        return os.path.join(root, file)
        return None

    except Exception as e:
        logger.error(f"查找虚拟机文件失败: {str(e)}")
        return None



def get_vm_ip(vm_name):
    """获取虚拟机IP地址，优先用vmrun getGuestIPAddress"""
    # logger.debug(f"开始获取虚拟机 {vm_name} 的IP地址")
    try:
        # 1. 通过vmrun getGuestIPAddress
        vm_file = find_vm_file(vm_name)
        if vm_file:
            # logger.debug(f"找到虚拟机文件: {vm_file}")
            vmrun_path = get_vmrun_path()
            # logger.debug(f"使用备用vmrun路径: {vmrun_path}")

            if os.path.exists(vmrun_path):
                try:
                    cmd = [vmrun_path, 'getGuestIPAddress', vm_file, '-wait']
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    # 记录命令结束时间
                    end_time = datetime.now()
                    if result.stderr:
                        logger.info(f"[DEBUG] getGuestIPAddress命令错误: {result.stderr}")
                    # 检查特定的错误码4294967295，但不执行强制重启
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
                            # logger.debug(f"从VMX文件找到IP配置: {ip}")
                            if is_valid_ip(ip):
                                # logger.info(f"从VMX文件成功获取IP: {ip}")
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
    # 使用新的SSH工具类实现
    from utils.ssh_utils import check_ssh_connectivity as new_check_ssh_connectivity
    return new_check_ssh_connectivity(ip_address, username, timeout=timeout)

