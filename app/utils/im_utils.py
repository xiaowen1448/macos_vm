import os
from datetime import datetime
import sys
import subprocess
from flask_socketio import SocketIO, emit
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
from pathlib import Path
from functools import wraps
from config import *
from app.utils.common_utils import logger
from app.utils.ssh_utils import *

try:
    import paramiko
except ImportError:
    paramiko = None
try:
    import fcntl
except ImportError:
    fcntl = None
try:
    import msvcrt
except ImportError:
    msvcrt = None

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from config import *

app = Flask(__name__, template_folder='web/templates', static_folder='web/static', static_url_path='/static')

# 初始化SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')



def process_batch_im_logout_async(vm_names, session_id):
    """异步处理批量IM注销"""
    try:
        success_count = 0
        failed_count = 0
        results = []

        # 发送开始消息
        socketio.emit('batch_im_logout_start', {
            'session_id': session_id,
            'total_count': len(vm_names)
        })

        def process_single_vm(vm_name):
            nonlocal success_count, failed_count
            try:
                logger.info(f"执行虚拟机 {vm_name} 的IM注销操作")

                # 发送处理中消息
                socketio.emit('batch_im_logout_progress', {
                    'session_id': session_id,
                    'vm_name': vm_name,
                    'status': 'processing',
                    'message': '正在处理...'
                })

                # 获取虚拟机IP
                vm_ip = get_vm_ip(vm_name)
                if not vm_ip or not is_valid_ip(vm_ip):
                    failed_count += 1
                    result = {
                        'vm_name': vm_name,
                        'result': 'IM_SUCESSFULL',  # IP获取失败视为未注销
                        'message': '虚拟机IP获取失败或无效'
                    }
                    socketio.emit('batch_im_logout_progress', {
                        'session_id': session_id,
                        'vm_name': vm_name,
                        'status': 'failed',
                        'result': 'IM_SUCESSFULL',
                        'message': '虚拟机IP获取失败或无效'
                    })
                    return result

                # 调用客户端8787端口API执行IM注销脚本
                script_name = 'logout_imessage.scpt'
                script_api_url = f"http://{vm_ip}:8787/run?path={scpt_script_remote_path}{script_name}"

                try:
                    logger.info(f"调用客户端API执行IM注销: {script_api_url}")
                    response = requests.get(script_api_url, timeout=90)  # 延长超时时间

                    if response.status_code == 200:
                        try:
                            # 尝试解析JSON响应
                            response_data = response.json()
                            result_status = response_data.get('result', 'IM_SUCESSFULL')
                        except:
                            # 如果不是JSON，根据文本内容判断
                            output = response.text.strip()
                            if 'IM_ERROR' in output:
                                result_status = 'IM_ERROR'
                            else:
                                result_status = 'IM_SUCESSFULL'

                        logger.info(f"虚拟机 {vm_name} IM注销完成: {result_status}")

                        if result_status == 'IM_ERROR':
                            success_count += 1  # IM_ERROR表示已注销
                        else:
                            failed_count += 1  # IM_SUCESSFULL表示未注销

                        result = {
                            'vm_name': vm_name,
                            'result': result_status,
                            'message': f'IM注销操作完成'
                        }

                        socketio.emit('batch_im_logout_progress', {
                            'session_id': session_id,
                            'vm_name': vm_name,
                            'status': 'completed',
                            'result': result_status,
                            'message': 'IM注销操作完成'
                        })

                        return result
                    else:
                        failed_count += 1
                        result = {
                            'vm_name': vm_name,
                            'result': 'IM_SUCESSFULL',
                            'message': f'IM注销失败: HTTP {response.status_code}'
                        }
                        socketio.emit('batch_im_logout_progress', {
                            'session_id': session_id,
                            'vm_name': vm_name,
                            'status': 'failed',
                            'result': 'IM_SUCESSFULL',
                            'message': f'IM注销失败: HTTP {response.status_code}'
                        })
                        return result

                except requests.exceptions.Timeout:
                    failed_count += 1
                    result = {
                        'vm_name': vm_name,
                        'result': 'IM_SUCESSFULL',
                        'message': 'IM注销超时'
                    }
                    socketio.emit('batch_im_logout_progress', {
                        'session_id': session_id,
                        'vm_name': vm_name,
                        'status': 'failed',
                        'result': 'IM_SUCESSFULL',
                        'message': 'IM注销超时'
                    })
                    return result
                except requests.exceptions.ConnectionError:
                    failed_count += 1
                    result = {
                        'vm_name': vm_name,
                        'result': 'IM_SUCESSFULL',
                        'message': '无法连接到客户端8787端口'
                    }
                    socketio.emit('batch_im_logout_progress', {
                        'session_id': session_id,
                        'vm_name': vm_name,
                        'status': 'failed',
                        'result': 'IM_SUCESSFULL',
                        'message': '无法连接到客户端8787端口'
                    })
                    return result
                except Exception as api_error:
                    failed_count += 1
                    result = {
                        'vm_name': vm_name,
                        'result': 'IM_SUCESSFULL',
                        'message': f'API调用异常: {str(api_error)}'
                    }
                    socketio.emit('batch_im_logout_progress', {
                        'session_id': session_id,
                        'vm_name': vm_name,
                        'status': 'failed',
                        'result': 'IM_SUCESSFULL',
                        'message': f'API调用异常: {str(api_error)}'
                    })
                    return result

            except Exception as e:
                failed_count += 1
                result = {
                    'vm_name': vm_name,
                    'result': 'IM_SUCESSFULL',
                    'message': str(e)
                }
                socketio.emit('batch_im_logout_progress', {
                    'session_id': session_id,
                    'vm_name': vm_name,
                    'status': 'failed',
                    'result': 'IM_SUCESSFULL',
                    'message': str(e)
                })
                logger.error(f"虚拟机 {vm_name} IM注销失败: {str(e)}")
                return result

        # 使用线程池并发处理
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(process_single_vm, vm_names))

        # 发送完成消息
        socketio.emit('batch_im_logout_complete', {
            'session_id': session_id,
            'success_count': success_count,
            'failed_count': failed_count,
            'results': results
        })

    except Exception as e:
        logger.error(f"批量IM注销异步处理失败: {str(e)}")
        socketio.emit('batch_im_logout_error', {
            'session_id': session_id,
            'message': f'批量IM注销处理失败: {str(e)}'
        })



def process_batch_im_status_async(vm_names, session_id):
    """异步处理批量IM状态查询"""
    try:
        results = []

        # 发送开始消息
        socketio.emit('batch_im_status_start', {
            'session_id': session_id,
            'total_count': len(vm_names)
        })

        def process_single_vm(vm_name):
            try:
                logger.info(f"查询虚拟机 {vm_name} 的IM状态")

                # 发送处理中消息
                socketio.emit('batch_im_status_progress', {
                    'session_id': session_id,
                    'vm_name': vm_name,
                    'status': 'processing',
                    'message': '正在查询...'
                })

                # 获取虚拟机IP
                vm_ip = get_vm_ip(vm_name)
                if not vm_ip or not is_valid_ip(vm_ip):
                    result = {
                        'vm_name': vm_name,
                        'result': 'IM_ERROR',  # IP获取失败视为未激活
                        'message': '虚拟机IP获取失败或无效'
                    }
                    socketio.emit('batch_im_status_progress', {
                        'session_id': session_id,
                        'vm_name': vm_name,
                        'status': 'failed',
                        'result': 'IM_ERROR',
                        'message': '虚拟机IP获取失败或无效'
                    })
                    return result

                # 调用客户端8787端口API执行IM状态查询脚本
                script_name = 'login_status_imessage.scpt'
                script_api_url = f"http://{vm_ip}:8787/run?path={scpt_script_remote_path}{script_name}"

                try:
                    logger.info(f"调用客户端API查询IM状态: {script_api_url}")
                    response = requests.get(script_api_url, timeout=90)  # 延长超时时间

                    if response.status_code == 200:
                        try:
                            # 尝试解析JSON响应
                            response_data = response.json()
                            result_status = response_data.get('result', 'IM_ERROR')
                        except:
                            # 如果不是JSON，根据文本内容判断
                            output = response.text.strip()
                            if 'IM_SUCESSFULL' in output:
                                result_status = 'IM_SUCESSFULL'
                            else:
                                result_status = 'IM_ERROR'

                        logger.info(f"虚拟机 {vm_name} IM状态查询成功: {result_status}")

                        result = {
                            'vm_name': vm_name,
                            'result': result_status,
                            'message': 'IM状态查询完成'
                        }

                        socketio.emit('batch_im_status_progress', {
                            'session_id': session_id,
                            'vm_name': vm_name,
                            'status': 'completed',
                            'result': result_status,
                            'message': 'IM状态查询完成'
                        })

                        return result
                    else:
                        result = {
                            'vm_name': vm_name,
                            'result': 'IM_ERROR',
                            'message': f'查询失败: HTTP {response.status_code}'
                        }
                        socketio.emit('batch_im_status_progress', {
                            'session_id': session_id,
                            'vm_name': vm_name,
                            'status': 'failed',
                            'result': 'IM_ERROR',
                            'message': f'查询失败: HTTP {response.status_code}'
                        })
                        return result

                except requests.exceptions.Timeout:
                    result = {
                        'vm_name': vm_name,
                        'result': 'IM_ERROR',
                        'message': '查询超时'
                    }
                    socketio.emit('batch_im_status_progress', {
                        'session_id': session_id,
                        'vm_name': vm_name,
                        'status': 'failed',
                        'result': 'IM_ERROR',
                        'message': '查询超时'
                    })
                    return result
                except requests.exceptions.ConnectionError:
                    result = {
                        'vm_name': vm_name,
                        'result': 'IM_ERROR',
                        'message': '无法连接到客户端8787端口'
                    }
                    socketio.emit('batch_im_status_progress', {
                        'session_id': session_id,
                        'vm_name': vm_name,
                        'status': 'failed',
                        'result': 'IM_ERROR',
                        'message': '无法连接到客户端8787端口'
                    })
                    return result
                except Exception as api_error:
                    result = {
                        'vm_name': vm_name,
                        'result': 'IM_ERROR',
                        'message': f'API调用异常: {str(api_error)}'
                    }
                    socketio.emit('batch_im_status_progress', {
                        'session_id': session_id,
                        'vm_name': vm_name,
                        'status': 'failed',
                        'result': 'IM_ERROR',
                        'message': f'API调用异常: {str(api_error)}'
                    })
                    return result

            except Exception as e:
                result = {
                    'vm_name': vm_name,
                    'result': 'IM_ERROR',
                    'message': '查询失败: ' + str(e)
                }
                socketio.emit('batch_im_status_progress', {
                    'session_id': session_id,
                    'vm_name': vm_name,
                    'status': 'failed',
                    'result': 'IM_ERROR',
                    'message': '查询失败: ' + str(e)
                })
                logger.error(f"虚拟机 {vm_name} IM状态查询失败: {str(e)}")
                return result

        # 使用线程池并发处理
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(process_single_vm, vm_names))

        # 发送完成消息
        socketio.emit('batch_im_status_complete', {
            'session_id': session_id,
            'results': results
        })

    except Exception as e:
        logger.error(f"批量IM状态查询异步处理失败: {str(e)}")
        socketio.emit('batch_im_status_error', {
            'session_id': session_id,
            'message': f'批量IM状态查询处理失败: {str(e)}'
        })
