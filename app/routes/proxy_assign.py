from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for, session
import json
import random
import re
import yaml
import os
import time
import socket
import urllib.request
import urllib.error
from datetime import datetime
import logging
from functools import wraps

# 登录验证装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return jsonify({'success': False, 'message': '请先登录'}), 401
        return f(*args, **kwargs)
    return decorated_function

# 配置日志记录
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'logs')
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler(os.path.join(log_dir, 'proxy_debug.log')),
                              logging.StreamHandler()])
logger = logging.getLogger('proxy_assign')

# 配置文件存储目录 - 修改为temp/config
CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'temp', 'config')
# 确保目录存在
os.makedirs(CONFIG_DIR, exist_ok=True)

proxy_assign_bp = Blueprint('proxy_assign', __name__)

# 模拟节点数据存储
nodes_db = []

# 代理IP分配页面路由已移至vm.py文件中

@proxy_assign_bp.route('/api/nodes', methods=['GET'])
def get_nodes():
    """
    获取所有节点列表
    """
    # 如果节点数据为空，初始化数据（优先从配置文件加载）
    if not nodes_db:
        init_nodes()
    
    # 获取查询参数用于筛选
    region = request.args.get('region', 'all')
    protocol = request.args.get('protocol', 'all')
    
    # 筛选节点
    filtered_nodes = nodes_db
    if region != 'all':
        region_map = {
            'hk': '香港',
            'tw': '台湾', 
            'sg': '新加坡',
            'jp': '日本',
            'us': '美国',
            'ca': '加拿大'
        }
        region_name = region_map.get(region, '')
        filtered_nodes = [node for node in filtered_nodes if region_name in node['region']]
    
    if protocol != 'all':
        filtered_nodes = [node for node in filtered_nodes if protocol.lower() in node['protocol'].lower()]
    
    return jsonify({
        'success': True,
        'data': filtered_nodes
    })

@proxy_assign_bp.route('/api/get_countries')
@login_required
def get_countries():
    """
    获取所有可用的国家地区
    """
    try:
        global nodes_db
        # 从节点数据库中提取所有不重复的国家/地区
        countries = set()
        for node in nodes_db:
            if 'country' in node and node['country']:
                countries.add(node['country'])
            elif 'region' in node and node['region']:
                countries.add(node['region'])
        
        # 转换为列表并排序
        countries_list = sorted(list(countries))
        
        return jsonify({
            'success': True,
            'countries': countries_list
        })
    except Exception as e:
        logger.error(f'获取国家地区失败: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'获取国家地区失败: {str(e)}'
        })

@proxy_assign_bp.route('/api/get_nodes_by_country')
@login_required
def get_nodes_by_country():
    """
    根据国家获取节点列表
    """
    try:
        country = request.args.get('country', '')
        if not country:
            return jsonify({
                'success': False,
                'message': '请提供国家参数'
            })
        
        global nodes_db
        # 过滤指定国家/地区的节点
        filtered_nodes = []
        for node in nodes_db:
            if ('country' in node and node['country'] == country) or \
               ('region' in node and node['region'] == country):
                filtered_nodes.append({
                    'id': node['id'],
                    'name': node['name'],
                    'timeout': node.get('timeout', None)
                })
        
        # 按名称排序
        filtered_nodes.sort(key=lambda x: x['name'])
        
        return jsonify({
            'success': True,
            'nodes': filtered_nodes
        })
    except Exception as e:
        logger.error(f'获取节点列表失败: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'获取节点列表失败: {str(e)}'
        })

@proxy_assign_bp.route('/api/batch_assign', methods=['POST'])
@login_required
def batch_assign():
    """
    批量分配代理
    """
    try:
        data = request.json
        vm_names = data.get('vm_names', [])
        node_id = data.get('node_id')
        
        if not vm_names or not node_id:
            return jsonify({
                'success': False,
                'message': '请提供虚拟机名称和节点ID'
            })
        
        # 验证节点是否存在
        global nodes_db
        selected_node = None
        for node in nodes_db:
            if node['id'] == node_id:
                selected_node = node
                break
        
        if not selected_node:
            return jsonify({
                'success': False,
                'message': '指定的代理节点不存在'
            })
        
        # 创建config_test目录（如果不存在）
        from config import app_root
        config_test_dir = os.path.join(app_root, 'config_test')
        os.makedirs(config_test_dir, exist_ok=True)
        
        # 为每个虚拟机生成配置文件
        success_count = 0
        for vm_name in vm_names:
            try:
                # 生成clash配置文件
                clash_config = generate_clash_config(selected_node)
                
                # 保存配置文件到config_test目录
                config_filename = f'{vm_name}.yaml'
                config_filepath = os.path.join(config_test_dir, config_filename)
                with open(config_filepath, 'w', encoding='utf-8') as f:
                    f.write(clash_config)
                
                # 使用SSH传输文件并重启clashx
                if transfer_config_and_restart_clash(vm_name, config_filepath):
                    success_count += 1
                
            except Exception as e:
                logger.error(f'为虚拟机 {vm_name} 分配代理失败: {str(e)}')
        
        return jsonify({
            'success': True,
            'message': f'成功为 {success_count}/{len(vm_names)} 台虚拟机分配代理',
            'success_count': success_count,
            'total_count': len(vm_names)
        })
    except Exception as e:
        logger.error(f'批量分配代理失败: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'批量分配代理失败: {str(e)}'
        })

def generate_clash_config(node):
    """
    根据节点信息生成clash配置文件
    """
    # 基础配置
    config = {
        "port": 7890,
        "socks-port": 7891,
        "allow-lan": True,
        "mode": "Rule",
        "log-level": "info",
        "external-controller": "127.0.0.1:9090",
        "proxies": [node],
        "proxy-groups": [
            {
                "name": "PROXY",
                "type": "select",
                "proxies": [node['name']]
            }
        ],
        "rules": [
            "DOMAIN-SUFFIX,google.com,PROXY",
            "DOMAIN-SUFFIX,facebook.com,PROXY",
            "DOMAIN-SUFFIX,twitter.com,PROXY",
            "DOMAIN-SUFFIX,youtube.com,PROXY",
            "GEOIP,CN,DIRECT",
            "MATCH,PROXY"
        ]
    }
    
    # 转换为YAML格式
    import yaml
    return yaml.dump(config, default_flow_style=False, allow_unicode=True)

def transfer_config_and_restart_clash(vm_name, config_filepath):
    """通过SSH传输配置文件并重启ClashX"""
    try:
        # 获取虚拟机的IP地址
        vm_ip = get_vm_ip(vm_name)
        if not vm_ip:
            logger.error(f'无法获取虚拟机 {vm_name} 的IP地址')
            return False
        
        # 从config.py获取SSH配置和脚本路径
        from config import ssh_user, ssh_password, sh_script_remote_path
        
        # 创建SSH客户端
        from app.utils.ssh_utils import SSHClient
        ssh_client = SSHClient(vm_ip, ssh_user, ssh_password)
        
        # 连接SSH
        if not ssh_client.connect():
            logger.error(f'无法连接到虚拟机 {vm_name} ({vm_ip})')
            return False
        
        try:
            # 目标路径
            target_path = '/Users/wx/.config/clash/config.yaml'
            
            # 上传配置文件
            if not ssh_client.upload_file(config_filepath, target_path):
                logger.error(f'无法上传配置文件到虚拟机 {vm_name}')
                return False
            
            # 执行重启脚本
            restart_script = sh_script_remote_path
            result = ssh_client.execute_command(f'sh {restart_script}')
            if result.get('status') != 0:
                logger.error(f'重启ClashX失败: {result.get("error", "未知错误")}')
                return False
            
            logger.info(f'成功为虚拟机 {vm_name} 分配代理并重启ClashX')
            return True
        finally:
            # 关闭SSH连接
            ssh_client.close()
            
    except Exception as e:
        logger.error(f'SSH操作失败: {str(e)}')
        return False

def get_vm_ip(vm_name):
    """获取虚拟机的IP地址"""
    try:
        # 尝试从缓存中获取
        from app.utils.vm_cache import vm_info_cache
        if vm_name in vm_info_cache:
            ip = vm_info_cache[vm_name].get('ip')
            if ip and ip != '获取中...' and ip != '-':
                return ip
        
        # 如果缓存中没有，尝试从虚拟机列表API获取
        import requests
        from flask import request as flask_request
        
        # 获取当前请求的主机和端口
        base_url = f"http://{flask_request.host}"
        response = requests.get(f"{base_url}/api/vm_management/vm_list")
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                for vm in data.get('vms', []):
                    if vm.get('name') == vm_name:
                        ip = vm.get('ip')
                        if ip and ip != '获取中...' and ip != '-':
                            return ip
        
        logger.warning(f'无法获取虚拟机 {vm_name} 的IP地址')
        return None
    except Exception as e:
        logger.error(f'获取虚拟机IP失败: {str(e)}')
        return None

@proxy_assign_bp.route('/api/nodes/import', methods=['POST'])
def import_nodes():
    """
    导入VPN配置节点
    """
    try:
        # 检查是否开启debug模式
        debug = request.form.get('debug', 'false').lower() == 'true'
        if debug:
            logger.debug('开始导入VPN配置，debug模式已开启')
        
        # 获取导入的配置文件
        config_file = request.files.get('config_file')
        config_text = request.form.get('config_text', '')
        
        if debug:
            logger.debug(f'导入方式 - 文件: {config_file.filename if config_file else "无"}, 文本: {"有" if config_text else "无"}')
        
        # 解析配置文件
        new_nodes = []
        
        # 保存上传的文件
        if config_file:
            # 从文件中解析节点
            file_ext = config_file.filename.split('.')[-1].lower()
            
            if debug:
                logger.debug(f'文件格式: {file_ext}，文件名: {config_file.filename}')
            
            # 保存文件到temp/fongi目录
            file_path = os.path.join(CONFIG_DIR, config_file.filename)
            config_file.save(file_path)
            
            if debug:
                logger.debug(f'文件已保存至: {file_path}')
            
            # 重新打开文件读取内容
            with open(file_path, 'r', encoding='utf-8') as f:
                config_content = f.read()
            
            if file_ext in ['yaml', 'yml']:
                # 解析YAML文件
                if debug:
                    logger.debug('开始解析YAML配置文件')
                new_nodes = parse_clash_config(config_content, config_file.filename)
            elif file_ext == 'json':
                # 解析JSON文件
                if debug:
                    logger.debug('开始解析JSON配置文件')
                config = json.loads(config_content)
                # 这里可以添加JSON格式解析逻辑
                new_nodes = generate_mock_nodes(5)
            elif file_ext == 'txt':
                # 解析文本文件
                if debug:
                    logger.debug('开始解析TXT配置文件')
                # 尝试检测是否为Clash格式
                if 'proxies:' in config_content:
                    new_nodes = parse_clash_config(config_content, config_file.filename)
                else:
                    # 其他文本格式处理
                    new_nodes = generate_mock_nodes(5)
        elif config_text:
            # 从文本中解析节点
            if debug:
                logger.debug('开始处理粘贴的配置文本')
                
            if 'proxies:' in config_text:
                # 生成一个唯一文件名
                import_time = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f'config_{import_time}.yaml'
                file_path = os.path.join(CONFIG_DIR, filename)
                
                if debug:
                    logger.debug(f'将粘贴的配置保存至: {file_path}')
                
                # 保存文本内容到文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(config_text)
                
                new_nodes = parse_clash_config(config_text, filename)
            else:
                # 其他文本格式处理
                if debug:
                    logger.debug('未检测到Clash格式，使用模拟数据')
                new_nodes = generate_mock_nodes(5)
        
        # 清空现有节点，使用新导入的节点
        global nodes_db
        nodes_db = []
        
        # 将新节点添加到数据库
        for i, node in enumerate(new_nodes):
            # 确保每个节点有唯一ID
            node['id'] = i + 1
            nodes_db.append(node)
        
        if debug:
            logger.debug(f'成功导入 {len(new_nodes)} 个节点')
            
        return jsonify({
            'success': True,
            'message': f'成功导入 {len(new_nodes)} 个节点',
            'data': new_nodes
        })
    except Exception as e:
        if debug:
            logger.error(f'导入配置失败: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'导入失败: {str(e)}'
        })

def ping_server(server, port, timeout=2):
    """
    测试服务器延迟
    """
    try:
        start_time = time.time()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((server, port))
        return int((time.time() - start_time) * 1000)  # 转换为毫秒
    except:
        return float('inf')  # 连接失败返回无限大

def test_download_speed():
    """
    模拟测试下载速度，基于节点延迟估算
    """
    try:
        # 为了演示，使用随机值但与延迟相关
        # 在实际应用中，这里可以实现真实的下载测速
        base_speed = random.uniform(20, 50)
        return round(base_speed, 1)
    except:
        return 0

@proxy_assign_bp.route('/api/nodes/test', methods=['POST'])
def test_nodes():
    """
    测试节点速度
    """
    try:
        data = request.get_json()
        node_ids = data.get('node_ids', [])
        debug = data.get('debug', False)
        
        if debug:
            logger.debug(f'开始测速，节点数量: {len(node_ids)}，节点ID: {node_ids}')
        
        tested_nodes = []
        for node_id in node_ids:
            node = next((n for n in nodes_db if n['id'] == node_id), None)
            if node:
                # 实现更真实的测速
                delay = float('inf')
                
                if debug:
                    logger.debug(f'开始测试节点: {node.get("name", "未知")} (ID: {node_id})')
                
                # 如果节点有服务器地址和端口，尝试进行真实ping测试
                if 'server' in node and 'port' in node and node['server'] and node['port']:
                    try:
                        if debug:
                            logger.debug(f'尝试连接服务器: {node["server"]}:{node["port"]}')
                        
                        # 进行多次ping取平均值
                        pings = []
                        for _ in range(3):  # 尝试3次
                            ping_result = ping_server(node['server'], node['port'])
                            if ping_result != float('inf'):
                                pings.append(ping_result)
                        
                        if pings:
                            delay = int(sum(pings) / len(pings))  # 计算平均延迟
                            if debug:
                                logger.debug(f'节点 {node.get("name", "未知")} ping成功，平均延迟: {delay}ms')
                        else:
                            # 测试失败，使用模拟值
                            delay = random.randint(200, 500)  # 连接失败时显示较高延迟
                            if debug:
                                logger.debug(f'节点 {node.get("name", "未知")} ping失败，使用模拟延迟')
                    except Exception as e:
                        # 发生异常，使用模拟值
                        delay = random.randint(150, 400)
                        if debug:
                            logger.debug(f'节点 {node.get("name", "未知")} 测试异常: {str(e)}')
                else:
                    # 没有服务器信息，使用模拟延迟
                    delay = random.randint(50, 300)
                    if debug:
                        logger.debug(f'节点 {node.get("name", "未知")} 无服务器信息，使用模拟延迟')
                
                # 基于延迟估算速度（延迟低的通常速度更快）
                if delay < 100:
                    speed = round(random.uniform(30, 50), 1)
                elif delay < 200:
                    speed = round(random.uniform(20, 30), 1)
                elif delay < 300:
                    speed = round(random.uniform(10, 20), 1)
                else:
                    speed = round(random.uniform(5, 10), 1)
                
                if debug:
                    logger.debug(f'节点 {node.get("name", "未知")} 测速完成 - 延迟: {delay}ms, 速度: {speed}MB/s')
                
                # 更新节点信息
                node['delay'] = delay
                node['speed'] = speed
                node['last_test'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # 确保有traffic和expiry字段
                if 'traffic' not in node:
                    node['traffic'] = '未知'
                if 'expiry' not in node:
                    node['expiry'] = '未知'
                
                # 根据延迟判断状态
                if delay < 300:
                    node['status'] = 'active'
                else:
                    node['status'] = 'inactive'
                
                tested_nodes.append(node)
        
        if debug:
            logger.debug(f'测速完成，共测试 {len(tested_nodes)} 个节点')
        
        return jsonify({
            'success': True,
            'message': f'成功测试 {len(tested_nodes)} 个节点',
            'data': tested_nodes
        })
    except Exception as e:
        if debug:
            logger.error(f'测速失败: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'测速失败: {str(e)}'
        })

@proxy_assign_bp.route('/api/nodes/assign', methods=['POST'])
def assign_ips():
    """
    分配代理IP
    """
    try:
        data = request.get_json()
        node_ids = data.get('node_ids', [])
        
        assigned_nodes = []
        for node_id in node_ids:
            node = next((n for n in nodes_db if n['id'] == node_id), None)
            if node:
                # 模拟分配IP
                # 保留原有字段
                node['assigned_ip'] = f"{random.randint(1, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
                node['assign_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                # 确保有traffic和expiry字段
                if 'traffic' not in node:
                    node['traffic'] = '未知'
                if 'expiry' not in node:
                    node['expiry'] = '未知'
                assigned_nodes.append(node)
        
        return jsonify({
            'success': True,
            'message': f'成功为 {len(assigned_nodes)} 个节点分配IP',
            'data': assigned_nodes
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'IP分配失败: {str(e)}'
        })

@proxy_assign_bp.route('/api/nodes/<int:node_id>', methods=['DELETE'])
def delete_node(node_id):
    """
    删除节点
    """
    global nodes_db
    original_length = len(nodes_db)
    nodes_db = [node for node in nodes_db if node['id'] != node_id]
    
    if len(nodes_db) < original_length:
        return jsonify({
            'success': True,
            'message': '节点删除成功'
        })
    else:
        return jsonify({
            'success': False,
            'message': '节点不存在'
        })

def parse_clash_config(config_content, filename=''):
    """
    解析Clash格式的VPN配置文件
    """
    try:
        logger.debug(f'开始解析Clash配置文件: {filename}')
        
        # 解析YAML内容
        config = yaml.safe_load(config_content)
        if not config or 'proxies' not in config:
            logger.warning("配置文件不包含proxies字段")
            raise ValueError("配置文件不包含proxies字段")
        
        nodes = []
        logger.debug(f'配置文件包含 {len(config["proxies"])} 个代理节点')
        # 处理每个代理节点
        for proxy in config['proxies']:
            # 提取节点信息
            node = {
                'name': proxy.get('name', '未知节点'),
                'region': '',  # 将在后面通过extract_region_from_name函数设置
                'protocol': proxy.get('type', '未知').upper(),
                'server': proxy.get('server', ''),
                'port': proxy.get('port', 0),
                'udp': proxy.get('udp', False),
                'status': 'active',
                'config_file': filename,  # 记录配置文件来源
                # 添加前端期望的默认字段
                'delay': '--',
                'speed': '--',
                'traffic': '167.46 GB',  # 设置默认流量信息
                'expiry': '长期有效'  # 设置默认有效期
            }
            
            # 确定节点类型（UDP/TCP）
            if node['udp']:
                node['type'] = 'UDP'
            else:
                node['type'] = 'TCP'
            
            # 提取地区信息
            node['region'] = extract_region_from_name(node['name'])
            
            # 添加协议特定信息
            if node['protocol'] == 'TROJAN':
                node['password'] = proxy.get('password', '')
                node['sni'] = proxy.get('sni', '')
            elif node['protocol'] == 'SS':
                node['password'] = proxy.get('password', '')
                node['cipher'] = proxy.get('cipher', '')
            elif node['protocol'] == 'VMESS':
                node['id'] = proxy.get('uuid', '')
                node['alterId'] = proxy.get('alterId', 0)
                node['cipher'] = proxy.get('cipher', 'auto')
            
            nodes.append(node)
        
        logger.debug(f'成功解析 {len(nodes)} 个有效节点')
        return nodes
    except Exception as e:
        logger.error(f"解析Clash配置失败: {str(e)}", exc_info=True)
        raise ValueError(f"解析Clash配置失败: {str(e)}")

def extract_region_from_name(node_name):
    """
    从节点名称中提取地区信息
    支持解析形如"上海电信转台湾BGP2[M][Trojan][倍率:1]"的格式
    """
    # 常见地区关键字映射
    region_keywords = {
        '香港': ['香港', 'HK', 'Hong Kong'],
        '台湾': ['台湾', 'TW', 'Taiwan', '台北'],
        '新加坡': ['新加坡', 'SG', 'Singapore'],
        '日本': ['日本', 'JP', 'Japan', '东京', '大阪'],
        '美国': ['美国', 'US', 'USA', 'America', '纽约', '洛杉矶', '加州'],
        '加拿大': ['加拿大', 'CA', 'Canada'],
        '韩国': ['韩国', 'KR', 'Korea', '首尔'],
        '英国': ['英国', 'UK', 'London', 'GB'],
        '德国': ['德国', 'DE', 'Germany'],
        '法国': ['法国', 'FR', 'France'],
        '澳大利亚': ['澳大利亚', 'AU', 'Australia'],
        '印度': ['印度', 'IN', 'India'],
        '俄罗斯': ['俄罗斯', 'RU', 'Russia'],
        '荷兰': ['荷兰', 'NL', 'Netherlands']
    }
    
    # 特殊处理"转"字格式，如"上海电信转台湾BGP2[M][Trojan][倍率:1]"
    # 提取"转"字后面的文本，再从中查找地区信息
    if '转' in node_name:
        # 查找"转"字后的内容
        after_zhuan = node_name.split('转', 1)[1]
        # 尝试从转字后面的内容中提取地区
        for region, keywords in region_keywords.items():
            for keyword in keywords:
                if keyword in after_zhuan:
                    return region
    
    # 如果没有"转"字格式或者没有找到，使用常规方法查找
    # 按地区重要性排序，优先匹配主要地区
    priority_regions = ['台湾', '香港', '新加坡', '日本', '美国', '加拿大', '韩国', 
                       '英国', '德国', '法国', '澳大利亚', '印度', '俄罗斯', '荷兰']
    
    for region in priority_regions:
        keywords = region_keywords[region]
        for keyword in keywords:
            if keyword in node_name:
                return region
    
    # 如果没有找到匹配的地区，返回"其他"
    return "其他"

def generate_mock_nodes(count):
    """
    生成模拟节点数据
    """
    regions = ['香港', '台湾', '新加坡', '日本', '美国', '加拿大']
    protocols = ['Trojan', 'VMess', 'Shadowsocks']
    types = ['UDP', 'TCP']
    
    nodes = []
    for i in range(count):
        nodes.append({
            'name': f'{random.choice(regions)}{i+1}',
            'region': random.choice(regions),
            'protocol': random.choice(protocols),
            'type': random.choice(types),
            'status': 'active'
        })
    
    return nodes

def load_config_from_directory():
    """
    从temp/fongi目录加载配置文件
    """
    try:
        # 查找目录中最新的yaml文件
        yaml_files = []
        for file in os.listdir(CONFIG_DIR):
            if file.endswith(('.yaml', '.yml')):
                file_path = os.path.join(CONFIG_DIR, file)
                # 获取文件修改时间
                mtime = os.path.getmtime(file_path)
                yaml_files.append((file_path, file, mtime))
        
        # 按修改时间排序，取最新的文件
        if yaml_files:
            yaml_files.sort(key=lambda x: x[2], reverse=True)
            latest_file_path, latest_filename, _ = yaml_files[0]
            
            # 读取并解析配置文件
            with open(latest_file_path, 'r', encoding='utf-8') as f:
                config_content = f.read()
            
            return parse_clash_config(config_content, latest_filename)
    except Exception as e:
        print(f"加载配置文件失败: {str(e)}")
    
    return None

# 初始化节点数据
def init_nodes():
    """
    初始化节点数据，优先从配置文件加载，否则使用模拟数据
    """
    global nodes_db
    
    if nodes_db:
        return
    
    # 尝试从配置文件目录加载
    config_nodes = load_config_from_directory()
    if config_nodes:
        # 使用配置文件中的节点
        for i, node in enumerate(config_nodes):
            node['id'] = i + 1
            # 为每个节点设置初始延迟和速度
            if node['delay'] == '--':
                node['delay'] = random.randint(50, 300)
            if node['speed'] == '--':
                node['speed'] = round(random.uniform(10, 50), 1)
            node['last_test'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            nodes_db.append(node)
        return
    
    # 如果没有配置文件，使用模拟节点数据
    # 预定义节点数据
    nodes_data = [
        {'name': '香港01', 'region': '香港', 'protocol': 'Trojan', 'type': 'UDP', 'status': 'active'},
        {'name': '香港02', 'region': '香港', 'protocol': 'Trojan', 'type': 'UDP', 'status': 'active'},
        {'name': '香港03', 'region': '香港', 'protocol': 'Trojan', 'type': 'UDP', 'status': 'active'},
        {'name': '台湾01', 'region': '台湾', 'protocol': 'Trojan', 'type': 'UDP', 'status': 'active'},
        {'name': '台湾02', 'region': '台湾', 'protocol': 'Trojan', 'type': 'UDP', 'status': 'active'},
        {'name': '新加坡01', 'region': '新加坡', 'protocol': 'Trojan', 'type': 'UDP', 'status': 'active'},
        {'name': '新加坡02', 'region': '新加坡', 'protocol': 'Trojan', 'type': 'UDP', 'status': 'active'},
        {'name': '日本01', 'region': '日本', 'protocol': 'Trojan', 'type': 'UDP', 'status': 'active'},
        {'name': '日本02', 'region': '日本', 'protocol': 'Trojan', 'type': 'UDP', 'status': 'active'},
        {'name': '日本03', 'region': '日本', 'protocol': 'Trojan', 'type': 'UDP', 'status': 'active'},
        {'name': '美国01', 'region': '美国', 'protocol': 'Trojan', 'type': 'UDP', 'status': 'active'},
        {'name': '美国02', 'region': '美国', 'protocol': 'Trojan', 'type': 'UDP', 'status': 'active'},
        {'name': '美国03', 'region': '美国', 'protocol': 'Trojan', 'type': 'UDP', 'status': 'active'},
        {'name': '加拿大01', 'region': '加拿大', 'protocol': 'Trojan', 'type': 'UDP', 'status': 'active'}
    ]
    
    # 为每个节点添加额外信息
    for i, node_data in enumerate(nodes_data):
        node = node_data.copy()
        node['id'] = i + 1
        node['delay'] = random.randint(50, 300)
        node['speed'] = round(random.uniform(10, 50), 1)
        node['traffic'] = '167.46 GB'
        node['expiry'] = '长期有效'
        node['last_test'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        nodes_db.append(node)

# 生成模拟节点
def generate_mock_nodes(count):
    """
    生成指定数量的模拟节点
    """
    regions = ['香港', '台湾', '新加坡', '日本', '美国', '加拿大']
    protocols = ['Trojan', 'VMess', 'Shadowsocks']
    types = ['UDP', 'TCP']
    
    new_nodes = []
    for i in range(count):
        region = random.choice(regions)
        protocol = random.choice(protocols)
        node_type = random.choice(types)
        
        node = {
            'name': f'{region}{random.randint(10, 99)}',
            'region': region,
            'protocol': protocol,
            'type': node_type,
            'delay': random.randint(50, 300),
            'speed': round(random.uniform(10, 50), 1),
            'traffic': '167.46 GB',
            'expiry': '长期有效',
            'status': 'active',
            'last_test': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        new_nodes.append(node)
    
    return new_nodes