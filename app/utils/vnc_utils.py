
import threading
import subprocess
import base64
import sys
import socket
import os
import psutil
import time
import threading
from pathlib import *
from flask import Flask, request
from flask_socketio import SocketIO, emit
from config import *
from app.utils.ssh_utils import *
from app.utils.vm_utils import *
from app.utils.common_utils import *
# 蓝图导入将在需要时在函数内部动态导入，避免循环导入

# 导入日志工具和全局logger
from app.utils.log_utils import logger 
from app.utils.vm_cache import *
from app.utils.im_utils import *

app = Flask(__name__, template_folder='web/templates', static_folder='web/static', static_url_path='/static')

# 初始化SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')



# 旧的VNC WebSocket代理代码（保留以防需要）
vnc_connections = {}
# 存储websockify进程信息的字典
websockify_processes = {}


def find_vnc_session_by_ip(client_ip):
    """根据客户端IP查找VNC会话"""
    for session_id, connection in vnc_connections.items():
        if connection.get('client_ip') == client_ip:
            return session_id
    return None


@socketio.on('vnc_connect')
def handle_vnc_connect(data):
    """处理VNC WebSocket连接"""
    try:
        client_ip = data.get('client_ip')
        if not client_ip:
            emit('vnc_error', {'message': '客户端IP不能为空'})
            return

        logger.info(f"WebSocket VNC连接请求: {client_ip}")

        # 查找VMX文件和VNC配置
        vmx_file = find_vmx_file_by_ip(client_ip)
        if not vmx_file:
            emit('vnc_error', {'message': f'未找到客户端IP {client_ip} 对应的虚拟机配置文件'})
            return

        vnc_config = read_vnc_config_from_vmx(vmx_file)
        if not vnc_config:
            emit('vnc_error', {'message': '虚拟机未启用VNC或配置不完整'})
            return

        # 创建VNC代理连接
        session_id = request.sid
        vnc_host = 'localhost'
        vnc_port = int(vnc_config['port'])

        try:
            # 创建到VNC服务器的socket连接
            vnc_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # 设置连接超时为10秒
            vnc_socket.settimeout(10.0)
            logger.info(f"尝试连接VNC服务器: {vnc_host}:{vnc_port}")
            vnc_socket.connect((vnc_host, vnc_port))
            logger.info(f"VNC socket连接成功: {vnc_host}:{vnc_port}")

            # 存储连接信息
            vnc_connections[session_id] = {
                'socket': vnc_socket,
                'config': vnc_config,
                'vmx_file': vmx_file,
                'client_ip': client_ip
            }

            # 启动数据转发线程
            thread = threading.Thread(target=vnc_proxy_worker, args=(session_id, vnc_socket))
            thread.daemon = True
            thread.start()

            emit('vnc_connected', {
                'host': vnc_host,
                'port': vnc_port,
                'password': vnc_config['password']
            })

            logger.info(f"VNC WebSocket连接成功: {client_ip} -> {vnc_host}:{vnc_port}")

        except Exception as e:
            logger.error(f"VNC socket连接失败: {str(e)}")
            emit('vnc_error', {'message': f'VNC连接失败: {str(e)}'})

    except Exception as e:
        logger.error(f"VNC WebSocket处理失败: {str(e)}")
        emit('vnc_error', {'message': str(e)})


@socketio.on('vnc_data')
def handle_vnc_data(data):
    """处理VNC数据传输"""
    session_id = request.sid
    if session_id in vnc_connections:
        try:
            vnc_socket = vnc_connections[session_id]['socket']
            # 解码并转发WebSocket数据到VNC服务器
            raw_data = base64.b64decode(data['data'])
            logger.debug(f"转发VNC数据: {len(raw_data)} 字节, 内容: {raw_data.hex()}")
            vnc_socket.send(raw_data)
        except Exception as e:
            logger.error(f"VNC数据转发失败: {str(e)}")
            emit('vnc_error', {'message': f'数据传输失败: {str(e)}'})
    else:
        logger.warning(f"收到数据但VNC连接不存在: {session_id}")
        emit('vnc_error', {'message': 'VNC连接不存在'})


@socketio.on('disconnect')
def handle_disconnect():
    """处理WebSocket断开连接"""
    session_id = request.sid
    if session_id in vnc_connections:
        try:
            vnc_connections[session_id]['socket'].close()
            del vnc_connections[session_id]
            logger.info(f"VNC连接已断开: {session_id}")
        except Exception as e:
            logger.error(f"断开VNC连接时出错: {str(e)}")



def has_vnc_config(vmx_path):
    """检查VMX文件中是否包含VNC配置"""
    try:
        # 动态导入以避免循环导入问题
        from app.utils.vm_utils import read_vmx_file_smart
        content, encoding = read_vmx_file_smart(vmx_path)
        if content is None:
            logger.error(f"读取VMX文件 {vmx_path} 时出错")
            return False
        # 检查是否包含VNC配置
        return 'RemoteDisplay.vnc.enabled' in content and 'RemoteDisplay.vnc.port' in content
    except Exception as e:
        logger.error(f"读取VMX文件 {vmx_path} 时出错: {str(e)}")
        return False



def read_vnc_config_from_vmx(vmx_path):
    """从VMX文件中读取VNC配置"""
    try:
        # 动态导入以避免循环导入问题
        from app.utils.vm_utils import read_vmx_file_smart
        vnc_config = {'port': None, 'password': None}

        content, encoding = read_vmx_file_smart(vmx_path)
        if content is None:
            return None

        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('RemoteDisplay.vnc.port'):
                # 提取端口号
                parts = line.split('=')
                if len(parts) == 2:
                    port_value = parts[1].strip().strip('"')
                    vnc_config['port'] = port_value
            elif line.startswith('RemoteDisplay.vnc.password'):
                # 提取密码
                parts = line.split('=')
                if len(parts) == 2:
                    password_value = parts[1].strip().strip('"')
                    vnc_config['password'] = password_value

        # 检查是否获取到了必要的配置
        if vnc_config['port'] and vnc_config['password']:
            return vnc_config
        else:
            return None
    except Exception as e:
        logger.error(f"读取VMX文件 {vmx_path} 的VNC配置时出错: {str(e)}")
        return None



def vnc_proxy_worker(session_id, vnc_socket):
    """VNC代理工作线程，将VNC服务器数据转发到WebSocket"""
    try:
        # 设置socket超时为5秒，给RFB握手更多时间
        vnc_socket.settimeout(5.0)

        logger.info(f"VNC代理工作线程启动: {session_id}")
        logger.info(f"VNC socket状态: {vnc_socket.getsockname()} -> {vnc_socket.getpeername()}")

        while session_id in vnc_connections:
            try:
                # 从VNC服务器接收数据
                data = vnc_socket.recv(4096)
                if not data:
                    logger.info(f"VNC服务器关闭连接: {session_id}")
                    break

                logger.debug(f"VNC代理收到数据: {len(data)} 字节, 内容: {data.hex()}")

                # 分析RFB协议数据
                if len(data) >= 12 and data.startswith(b'RFB '):
                    version = data[:12].decode('ascii', errors='ignore')
                    logger.info(f"RFB版本握手: {version.strip()}")
                elif len(data) == 1:
                    logger.info(f"RFB安全类型选择: {data[0]}")
                elif len(data) == 2 and data[0] in [1, 2]:
                    logger.info(f"RFB安全类型数量: {data[0]}, 类型: {data[1]}")
                elif len(data) == 16:
                    logger.info(f"RFB认证挑战: {data.hex()}")
                elif len(data) == 4:
                    result = int.from_bytes(data, 'big')
                    if result == 0:
                        logger.info("RFB认证成功")
                    else:
                        logger.warning(f"RFB认证失败: {result}")

                # 将数据编码为base64并发送到WebSocket
                encoded_data = base64.b64encode(data).decode('utf-8')
                socketio.emit('vnc_data', {'data': encoded_data}, room=session_id)

            except socket.timeout:
                # 超时是正常的，继续循环
                continue
            except ConnectionResetError:
                logger.info(f"VNC连接被重置: {session_id}")
                break
            except OSError as e:
                if e.winerror == 10053:  # 连接被主机软件中止
                    logger.warning(f"VNC连接被服务器中止: {session_id}, 错误码: {e.winerror}")
                    # 尝试重新连接
                    socketio.emit('vnc_reconnect_needed', {'reason': 'connection_aborted'}, room=session_id)
                else:
                    logger.error(f"VNC代理网络错误: {str(e)}, 错误码: {getattr(e, 'winerror', 'N/A')}")
                break
            except Exception as e:
                logger.error(f"VNC代理数据接收失败: {str(e)}")
                break

    except Exception as e:
        logger.error(f"VNC代理工作线程异常: {str(e)}")
    finally:
        # 清理连接
        logger.info(f"清理VNC连接: {session_id}")
        if session_id in vnc_connections:
            try:
                vnc_connections[session_id]['socket'].close()
                del vnc_connections[session_id]
            except:
                pass
        socketio.emit('vnc_disconnected', room=session_id)


def start_websockify(vm_name, vnc_port):
    """启动websockify进程（使用虚拟机名称）"""
    try:
        # 为每个虚拟机分配一个唯一的WebSocket端口
        websocket_port = get_available_websocket_port()
        if not websocket_port:
            logger.error("无法分配WebSocket端口")
            return None

        # 停止之前的websockify进程（如果存在）
        stop_websockify(vm_name)

        # 构建websockify命令
        cmd = [
            sys.executable, '-m', 'websockify',
            '--web', os.path.join(os.path.dirname(__file__), '../..', 'web', 'static'),
            f'{websocket_port}',
            f'localhost:{vnc_port}'
        ]

        logger.info(f"启动websockify命令: {' '.join(cmd)}")
        logger.info(f"web目录路径: {os.path.join(os.path.dirname(__file__), '../..', 'web', 'static')}")

        # 检查websockify是否安装
        try:
            check_cmd = [sys.executable, '-m', 'websockify', '--help']
            check_process = subprocess.run(
                check_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                timeout=5
            )
            if check_process.returncode != 0:
                logger.error(f"websockify未安装或无法运行: {check_process.stderr.decode('utf-8', errors='ignore').strip()}")
                return None
        except Exception as check_e:
            logger.error(f"检查websockify安装时出错: {str(check_e)}")

        # 启动websockify进程
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )

        # 存储进程信息（使用虚拟机名称作为键）
        websockify_processes[vm_name] = {
            'process': process,
            'websocket_port': websocket_port,
            'vnc_port': vnc_port,
            'start_time': time.time()
        }

        # 等待一小段时间确保进程启动
        time.sleep(1)

        # 检查进程是否正常运行
        if process.poll() is None:
            logger.info(f"websockify进程启动成功: PID={process.pid}, WebSocket端口={websocket_port}")
            return websocket_port
        else:
            # 读取错误输出以获取详细信息
            stdout, stderr = process.communicate(timeout=2)
            stdout_str = stdout.decode('utf-8', errors='ignore').strip()
            stderr_str = stderr.decode('utf-8', errors='ignore').strip()
            
            logger.error(f"websockify进程启动失败: 返回码={process.returncode}")
            if stdout_str:
                logger.error(f"websockify标准输出: {stdout_str}")
            if stderr_str:
                logger.error(f"websockify错误输出: {stderr_str}")
            
            if vm_name in websockify_processes:
                del websockify_processes[vm_name]
            return None

    except Exception as e:
        logger.error(f"启动websockify失败: {str(e)}")
        return None


def stop_websockify(identifier):
    """停止指定标识符的websockify进程（支持client_ip或vm_name）"""
    try:
        if identifier in websockify_processes:
            process_info = websockify_processes[identifier]
            process = process_info['process']
            websocket_port = process_info.get('websocket_port', 'unknown')

            logger.info(
                f"准备停止标识符 {identifier} 的websockify进程: PID={process.pid}, WebSocket端口={websocket_port}")

            if process.poll() is None:  # 进程仍在运行
                logger.info(f"终止websockify进程: PID={process.pid}")
                process.terminate()

                # 等待进程结束
                try:
                    process.wait(timeout=5)
                    logger.info(f"websockify进程已正常结束: PID={process.pid}")
                except subprocess.TimeoutExpired:
                    logger.warning(f"websockify进程未能正常结束，强制终止: PID={process.pid}")
                    process.kill()
                    logger.info(f"websockify进程已强制终止: PID={process.pid}")
            else:
                logger.info(f"websockify进程已经结束: PID={process.pid}")

            del websockify_processes[identifier]
            logger.info(f"websockify进程信息已清理: {identifier}, 释放WebSocket端口={websocket_port}")
        else:
            logger.info(f"客户端 {identifier} 没有运行中的websockify进程")

    except Exception as e:
        logger.error(f"停止websockify进程失败: {str(e)}")

def stop_websockify_by_vm_name(vm_name):
    """根据虚拟机名称停止对应的websockify进程"""
    try:
        logger.info(f"尝试根据虚拟机名称 {vm_name} 停止websockify进程")
        
        # 查找与该虚拟机名称相关的所有可能的websockify进程
        # 1. 首先尝试通过vmx文件查找IP
        vmx_file = find_vmx_file_by_name(vm_name)
        if vmx_file:
            # 获取虚拟机IP
            vm_ip = get_vm_ip_from_vmx(vmx_file)
            if vm_ip and vm_ip in websockify_processes:
                # 如果找到对应的IP，使用stop_websockify函数停止
                stop_websockify(vm_ip)
                return True
        
        # 2. 如果无法通过IP找到，尝试使用psutil查找包含虚拟机名称信息的websockify进程
        killed_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # 检查是否是websockify进程，并且命令行中包含虚拟机名称相关信息
                if proc.info['cmdline'] and any('websockify' in str(arg) for arg in proc.info['cmdline']):
                    cmdline_str = ' '.join(str(arg) for arg in proc.info['cmdline'])
                    # 如果命令行中包含虚拟机名称的部分信息，尝试终止该进程
                    if vm_name in cmdline_str:
                        pid = proc.info['pid']
                        logger.info(f"发现与虚拟机 {vm_name} 相关的websockify进程: PID={pid}")
                        
                        # 终止进程
                        proc.terminate()
                        try:
                            proc.wait(timeout=5)
                            killed_processes.append(pid)
                            logger.info(f"websockify进程已正常结束: PID={pid}")
                        except subprocess.TimeoutExpired:
                            logger.warning(f"websockify进程未能正常结束，强制终止: PID={pid}")
                            proc.kill()
                            killed_processes.append(pid)
            except Exception as e:
                logger.error(f"检查进程时出错: {str(e)}")
        
        # 3. 清理websockify_processes字典中的相关条目（如果有）
        # 由于我们没有直接的映射关系，这里暂时无法精确清理
        
        if killed_processes:
            logger.info(f"已停止 {len(killed_processes)} 个与虚拟机 {vm_name} 相关的websockify进程")
            return True
        else:
            logger.info(f"未找到与虚拟机 {vm_name} 相关的websockify进程")
            return False
    except Exception as e:
        logger.error(f"根据虚拟机名称停止websockify进程失败: {str(e)}")
        return False


def cleanup_all_websockify():
    """清理所有websockify进程和资源"""
    try:
        logger.info("开始清理所有websockify进程...")

        # 停止所有已知的websockify进程
        client_ips = list(websockify_processes.keys())
        for client_ip in client_ips:
            stop_websockify(client_ip)

        # 清空进程字典
        websockify_processes.clear()

        # 使用psutil查找并终止所有websockify进程
        killed_processes = []

        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # 检查是否是websockify进程
                if proc.info['cmdline'] and any('websockify' in str(arg) for arg in proc.info['cmdline']):
                    pid = proc.info['pid']
                    logger.info(f"发现websockify进程: PID={pid}, 命令行={proc.info['cmdline']}")

                    # 终止进程
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                        killed_processes.append(pid)
                        logger.info(f"成功终止websockify进程: PID={pid}")
                    except psutil.TimeoutExpired:
                        proc.kill()
                        killed_processes.append(pid)
                        logger.warning(f"强制终止websockify进程: PID={pid}")

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # 释放端口（通过终止占用6080+端口的进程）
        for port in range(6080, 6180):  # 检查常用的WebSocket端口范围
            try:
                for conn in psutil.net_connections():
                    if conn.laddr.port == port and conn.status == 'LISTEN':
                        try:
                            proc = psutil.Process(conn.pid)
                            if 'python' in proc.name().lower() or 'websockify' in ' '.join(proc.cmdline()):
                                logger.info(f"释放端口 {port}，终止进程 PID={conn.pid}")
                                proc.terminate()
                                try:
                                    proc.wait(timeout=3)
                                except psutil.TimeoutExpired:
                                    proc.kill()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
            except Exception:
                continue

        logger.info(f"websockify进程清理完成，共终止 {len(killed_processes)} 个进程")
        return True

    except Exception as e:
        logger.error(f"清理websockify进程失败: {str(e)}")
        return False


def cleanup_all_vnc_connections():
    """清理所有VNC连接和资源"""
    try:
        logger.info("开始清理所有VNC连接...")

        # 清理WebSocket VNC连接
        session_ids = list(vnc_connections.keys())
        for session_id in session_ids:
            try:
                connection = vnc_connections[session_id]
                if 'socket' in connection and connection['socket']:
                    try:
                        # 检查套接字是否仍然有效
                        if hasattr(connection['socket'], 'fileno'):
                            connection['socket'].close()
                    except (OSError, AttributeError) as e:
                        # 忽略套接字已关闭或无效的错误
                        logger.debug(f"套接字已关闭或无效: {str(e)}")
                del vnc_connections[session_id]
                logger.info(f"清理VNC连接: {session_id}")
            except Exception as e:
                logger.error(f"清理VNC连接 {session_id} 失败: {str(e)}")

        # 清空连接字典
        vnc_connections.clear()

        # 清理websockify进程
        cleanup_all_websockify()

        logger.info("所有VNC连接和资源清理完成")
        return True

    except Exception as e:
        logger.error(f"清理VNC连接失败: {str(e)}")
        return False


def get_available_websocket_port():
    """获取可用的WebSocket端口"""
    # 从6080开始尝试端口
    start_port = 6080
    max_attempts = 100

    # 获取已被websockify进程占用的端口
    used_ports = set()
    for client_ip, process_info in websockify_processes.items():
        if 'websocket_port' in process_info:
            used_ports.add(process_info['websocket_port'])

    for i in range(max_attempts):
        port = start_port + i

        # 跳过已被websockify进程占用的端口
        if port in used_ports:
            continue

        try:
            # 检查端口是否被占用
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                logger.info(f"分配WebSocket端口: {port}")
                return port
        except OSError:
            continue

    logger.error(f"无法找到可用的WebSocket端口（尝试了{max_attempts}个端口）")
    return None
