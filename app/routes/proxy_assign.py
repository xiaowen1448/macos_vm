from flask import Blueprint, render_template, request, jsonify
import json
import random
from datetime import datetime

proxy_assign_bp = Blueprint('proxy_assign', __name__)

# 模拟节点数据存储
nodes_db = []

@proxy_assign_bp.route('/proxy_assign')
def proxy_assign():
    """
    代理IP分配页面
    """
    return render_template('proxy_assign.html')

@proxy_assign_bp.route('/api/nodes', methods=['GET'])
def get_nodes():
    """
    获取所有节点列表
    """
    # 如果节点数据为空，初始化模拟数据
    if not nodes_db:
        init_mock_nodes()
    
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

@proxy_assign_bp.route('/api/nodes/import', methods=['POST'])
def import_nodes():
    """
    导入VPN配置节点
    """
    try:
        # 获取导入的配置文件
        config_file = request.files.get('config_file')
        config_text = request.form.get('config_text', '')
        
        # 模拟解析配置文件
        # 实际应用中需要根据不同的VPN配置格式进行解析
        new_nodes = []
        
        if config_file:
            # 模拟从文件中解析节点
            file_ext = config_file.filename.split('.')[-1].lower()
            if file_ext in ['json', 'yaml', 'yml', 'txt']:
                # 这里应该根据文件类型进行相应的解析
                # 目前仅模拟解析结果
                new_nodes = generate_mock_nodes(10)
        elif config_text:
            # 模拟从文本中解析节点
            new_nodes = generate_mock_nodes(5)
        
        # 将新节点添加到数据库
        for node in new_nodes:
            # 确保每个节点有唯一ID
            node['id'] = len(nodes_db) + 1
            nodes_db.append(node)
        
        return jsonify({
            'success': True,
            'message': f'成功导入 {len(new_nodes)} 个节点',
            'data': new_nodes
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'导入失败: {str(e)}'
        })

@proxy_assign_bp.route('/api/nodes/test', methods=['POST'])
def test_nodes():
    """
    测试节点速度
    """
    try:
        data = request.get_json()
        node_ids = data.get('node_ids', [])
        
        tested_nodes = []
        for node_id in node_ids:
            node = next((n for n in nodes_db if n['id'] == node_id), None)
            if node:
                # 模拟测速
                node['delay'] = random.randint(50, 300)
                node['speed'] = round(random.uniform(10, 50), 1)
                node['last_test'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                tested_nodes.append(node)
        
        return jsonify({
            'success': True,
            'message': f'成功测试 {len(tested_nodes)} 个节点',
            'data': tested_nodes
        })
    except Exception as e:
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
                node['assigned_ip'] = f"{random.randint(1, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
                node['assign_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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

# 初始化模拟节点数据
def init_mock_nodes():
    """
    初始化模拟节点数据
    """
    global nodes_db
    
    if nodes_db:
        return
    
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