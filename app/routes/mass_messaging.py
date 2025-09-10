from flask import Blueprint, request, jsonify, render_template
from functools import wraps
import os
import subprocess
import time
import logging
import requests
import json
import sqlite3
from config import vm_username, project_root, script_remote_path, send_imessage

# 创建蓝图
mass_messaging_bp = Blueprint('mass_messaging', __name__)

# 创建logger实例
logger = logging.getLogger(__name__)

# 登录验证装饰器（需要从主应用导入）
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 这里应该实现登录验证逻辑
        # 暂时跳过验证，实际使用时需要从主应用导入
        return f(*args, **kwargs)
    return decorated_function

@mass_messaging_bp.route('/mass_messaging')
@login_required
def mass_messaging_page():
    """群发管理页面"""
    return render_template('mass_messaging.html')

# 群发管理API路由
@mass_messaging_bp.route('/api/mass_messaging/templates', methods=['GET'])
@login_required
def api_get_templates():
    """获取发送模板列表 - 扫描txt和file目录，同名文件作为同一模板"""
    try:
        templates = []
        # 获取项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        template_dir = os.path.join(project_root, 'web', 'config', 'im_default', 'txt')
        attachment_dir = os.path.join(project_root, 'web', 'config', 'im_default', 'file')
        
        # 获取所有模板名称（从txt目录扫描）
        template_names = set()
        if os.path.exists(template_dir):
            for filename in os.listdir(template_dir):
                if filename.endswith('_imessage.txt') and filename != '.gitkeep':
                    template_name = filename.replace('_imessage.txt', '')
                    template_names.add(template_name)
        
        # 从file目录扫描，添加只有附件没有文本的模板
        if os.path.exists(attachment_dir):
            for filename in os.listdir(attachment_dir):
                if filename.endswith(('_imessage.png', '_imessage.jpg', '_imessage.jpeg', '_imessage.gif', '_imessage.mp4', '_imessage.mov')) and filename != '.gitkeep':
                    # 提取模板名称
                    for ext in ['_imessage.png', '_imessage.jpg', '_imessage.jpeg', '_imessage.gif', '_imessage.mp4', '_imessage.mov']:
                        if filename.endswith(ext):
                            template_name = filename.replace(ext, '')
                            template_names.add(template_name)
                            break
        
        # 为每个模板名称构建完整的模板信息
        for i, template_name in enumerate(sorted(template_names), 1):
            template_info = {
                'id': i,
                'name': template_name,
                'content': '',
                'attachment': None,
                'attachment_name': None,
                'has_attachment': False,
                'type': 'custom'
            }
            
            # 读取文本内容
            txt_path = os.path.join(template_dir, f"{template_name}_imessage.txt")
            if os.path.exists(txt_path):
                try:
                    with open(txt_path, 'r', encoding='utf-8') as f:
                        template_info['content'] = f.read().strip()
                except Exception as e:
                    logger.error(f"读取模板文件失败 {txt_path}: {str(e)}")
                    template_info['content'] = '读取失败'
            
            # 查找对应的附件文件
            if os.path.exists(attachment_dir):
                for att_file in os.listdir(attachment_dir):
                    if att_file.startswith(f"{template_name}_imessage.") and att_file != '.gitkeep':
                        template_info['attachment'] = att_file
                        template_info['attachment_name'] = att_file
                        template_info['has_attachment'] = True
                        break
            
            templates.append(template_info)
        
        logger.info(f"成功加载 {len(templates)} 个模板")
        return jsonify({'success': True, 'data': templates})
        
    except Exception as e:
        logger.error(f"获取模板列表失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@mass_messaging_bp.route('/api/get_emoji_list')
@login_required
def api_get_emoji_list():
    """获取表情包列表"""
    try:
        emoji_file_path = os.path.join(project_root, 'app', 'emoji_wrapped.txt')
        
        if not os.path.exists(emoji_file_path):
            return jsonify({
                'success': False,
                'message': '表情包文件不存在'
            })
        
        with open(emoji_file_path, 'r', encoding='utf-8') as f:
            emoji_list = [line.strip() for line in f.readlines() if line.strip()]
        
        return jsonify({
            'success': True,
            'emojis': emoji_list
        })
        
    except Exception as e:
        logger.error(f"获取表情包列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取表情包列表失败: {str(e)}'
        })

@mass_messaging_bp.route('/api/mass_messaging/download_chat_db', methods=['POST'])
@login_required
def api_download_chat_db():
    """下载远端客户端的chat.db文件到本地db目录，使用虚拟机名称作为文件名"""
    try:
        data = request.get_json()
        client_ip = data.get('client_ip')
        vm_name = data.get('vm_name')
        
        if not client_ip:
            return jsonify({'success': False, 'message': '客户端IP不能为空'})
        
        if not vm_name:
            return jsonify({'success': False, 'message': '虚拟机名称不能为空'})
        
        # 获取项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        db_dir = os.path.join(project_root, 'db')
        vm_db_dir = os.path.join(db_dir, vm_name)
        
        # 确保虚拟机专用目录存在
        os.makedirs(vm_db_dir, exist_ok=True)
        
        # 定义本地文件路径
        local_chat_db = os.path.join(vm_db_dir, f'{vm_name}.db')
        local_chat_shm = os.path.join(vm_db_dir, f'{vm_name}.db-shm')
        local_chat_wal = os.path.join(vm_db_dir, f'{vm_name}.db-wal')
        
        # 定义远端文件路径
        remote_base_path = '/Users/wx/Library/Messages'
        remote_files = [
            ('chat.db', local_chat_db),
            ('chat.db-shm', local_chat_shm),
            ('chat.db-wal', local_chat_wal)
        ]
        
        downloaded_files = []
        
        # 下载所有相关文件
        for remote_file, local_file in remote_files:
            remote_path = f'{remote_base_path}/{remote_file}'
            
            scp_command = [
                'scp',
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'UserKnownHostsFile=/dev/null',
                f'{vm_username}@{client_ip}:{remote_path}',
                local_file
            ]
            
            logger.info(f"尝试下载文件: {remote_file}")
            
            try:
                result = subprocess.run(
                    scp_command,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode == 0 and os.path.exists(local_file) and os.path.getsize(local_file) > 0:
                    downloaded_files.append(remote_file)
                    logger.info(f"文件下载成功: {remote_file} -> {local_file}, 大小: {os.path.getsize(local_file)} bytes")
                else:
                    logger.warning(f"文件下载失败或不存在: {remote_file}, 返回码: {result.returncode}")
                    if result.stderr:
                        logger.warning(f"SCP错误信息: {result.stderr.strip()}")
                    # 删除可能创建的空文件
                    if os.path.exists(local_file):
                        logger.debug(f"删除空文件: {local_file}")
                        os.remove(local_file)
                        
            except subprocess.TimeoutExpired:
                logger.warning(f"下载文件超时: {remote_file}")
                if os.path.exists(local_file):
                    os.remove(local_file)
            except Exception as e:
                logger.warning(f"下载文件异常: {remote_file}, 错误: {str(e)}")
                if os.path.exists(local_file):
                    os.remove(local_file)
        
        # 检查是否至少下载了主数据库文件
        if 'chat.db' not in downloaded_files:
            logger.error(f"主数据库文件chat.db下载失败，已下载文件: {downloaded_files}")
            return jsonify({'success': False, 'message': f'主数据库文件chat.db下载失败'})
        
        # 记录下载完成后的目录状态
        logger.info(f"下载完成，虚拟机目录: {vm_db_dir}")
        if os.path.exists(vm_db_dir):
            files_in_dir = os.listdir(vm_db_dir)
            logger.info(f"目录中的文件: {files_in_dir}")
        else:
            logger.error(f"虚拟机目录不存在: {vm_db_dir}")
        
        # 记录下载成功的文件详情
        logger.info(f"下载成功的文件列表: {downloaded_files}")
        for file_name in downloaded_files:
            if file_name == 'chat.db':
                file_path = local_chat_db
            elif file_name == 'chat.db-shm':
                file_path = local_chat_shm
            elif file_name == 'chat.db-wal':
                file_path = local_chat_wal
            else:
                continue
            
            # if os.path.exists(file_path):
            #     logger.info(f"文件存在确认: {file_path}, 大小: {os.path.getsize(file_path)} bytes")
            # else:
            #     logger.warning(f"文件不存在: {file_path}")
        
        # 如果存在WAL文件，进行数据库合并
        if 'chat.db-wal' in downloaded_files:
            try:
                logger.info(f"开始合并WAL数据库: {vm_name}")
                
                # 检查WAL文件是否真实存在
                if not os.path.exists(local_chat_wal):
                    logger.error(f"WAL文件不存在，无法合并: {local_chat_wal}")
                    return jsonify({'success': False, 'message': f'WAL文件不存在: {local_chat_wal}'})
                
                # 直接执行WAL数据库合并
                logger.info(f"开始执行WAL数据库合并: {vm_name}")
                
                conn = sqlite3.connect(local_chat_db)
                cursor = conn.cursor()
                
                # 执行WAL检查点，将WAL文件的内容合并到主数据库
                result = cursor.execute('PRAGMA wal_checkpoint(FULL)')
                checkpoint_result = result.fetchone()
                logger.info(f"WAL检查点结果: {checkpoint_result}")
                
                conn.commit()
                conn.close()
                
                logger.info(f"数据库WAL合并完成: {vm_name}")
                
                # 检查合并后的文件状态
               # logger.info(f"合并后文件状态:")
                # for file_path in [local_chat_db, local_chat_shm, local_chat_wal]:
                #     if os.path.exists(file_path):
                #         logger.info(f"文件存在: {file_path}, 大小: {os.path.getsize(file_path)} bytes")
                #     else:
                #         logger.info(f"文件不存在: {file_path}")
                        
            except Exception as e:
                logger.error(f"数据库合并失败: {str(e)}")
                return jsonify({'success': False, 'message': f'数据库合并失败: {str(e)}'})
        
        # 返回成功信息
        file_size = os.path.getsize(local_chat_db) if os.path.exists(local_chat_db) else 0
        return jsonify({
            'success': True,
            'message': f'{vm_name} 的数据库文件下载并处理完成',
            'file_path': local_chat_db,
            'file_size': file_size,
            'vm_name': vm_name,
            'downloaded_files': downloaded_files
        })
            
    except subprocess.TimeoutExpired:
        logger.error("下载chat.db文件超时")
        return jsonify({'success': False, 'message': '下载超时，请检查网络连接'})
    except Exception as e:
         logger.error(f"下载chat.db文件时发生错误: {str(e)}")
         return jsonify({'success': False, 'message': f'下载失败: {str(e)}'})

@mass_messaging_bp.route('/api/mass_messaging/get_message_records', methods=['GET'])
@login_required
def api_get_message_records():
    """解析chat.db数据库并返回发信记录数据，根据虚拟机名称查询对应的数据库文件"""
    try:
        # 获取虚拟机名称参数
        vm_name = request.args.get('vm_name')
        
        if not vm_name:
            return jsonify({'success': False, 'message': '虚拟机名称不能为空'})
        
        # 获取项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        db_dir = os.path.join(project_root, 'db')
        vm_db_dir = os.path.join(db_dir, vm_name)
        
        # 根据新的目录结构构建数据库文件路径
        db_path = os.path.join(vm_db_dir, f'{vm_name}.db')
        
        # 检查数据库文件是否存在
        if not os.path.exists(db_path):
            return jsonify({'success': False, 'message': f'{vm_name} 的chat.db文件不存在，请先下载数据库文件'})
        
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查询发信记录数据
        # 根据imessage数据库表结构文档，构建查询语句
        query = """
        SELECT 
            m.ROWID as message_id,
            h.id as contact_id,
            m.text as message_content,
            m.service as service_type,
            CASE 
                WHEN m.is_sent = 1 THEN '是'
                ELSE '否'
            END as is_sent,
            CASE 
                WHEN m.is_delivered = 1 THEN '是'
                ELSE '否'
            END as is_delivered,
            CASE 
                WHEN m.is_read = 1 THEN '是'
                ELSE '否'
            END as is_read,
            datetime(m.date/1000000000 + strftime('%s', '2001-01-01'), 'unixepoch', 'localtime') as send_time,
            m.account as sender_account
        FROM message m
        LEFT JOIN handle h ON m.handle_id = h.ROWID
        ORDER BY m.date DESC
        LIMIT 1000
        """
        
        cursor.execute(query)
        records = cursor.fetchall()
        
        # 构建返回数据
        message_records = []
        for record in records:
            message_records.append({
                'message_id': record[0] or '',
                'contact_id': record[1] or '',
                'message_content': record[2] or '',
                'service_type': record[3] or '',
                'is_sent': record[4],
                'is_delivered': record[5],
                'is_read': record[6],
                'send_time': record[7] or '',
                'sender_account': record[8] or ''
            })
        
        conn.close()
        
        logger.info(f"成功获取发信记录，共{len(message_records)}条")
        return jsonify({
            'success': True,
            'message': f'成功获取发信记录，共{len(message_records)}条',
            'records': message_records
        })
        
    except sqlite3.Error as e:
        logger.error(f"数据库查询错误: {str(e)}")
        return jsonify({'success': False, 'message': f'数据库查询错误: {str(e)}'})
    except Exception as e:
        logger.error(f"获取发信记录时发生错误: {str(e)}")
        return jsonify({'success': False, 'message': f'获取发信记录失败: {str(e)}'})

# 手机号模板管理API
@mass_messaging_bp.route('/api/phone_templates', methods=['GET'])
@login_required
def api_get_phone_templates():
    """获取手机号模板列表 - 从phone_unused_dir目录读取"""
    try:
        templates = []
        # 获取项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        # 从配置文件获取phone_unused_dir路径
        from config import phone_unused_dir
        phone_template_dir = os.path.join(project_root, phone_unused_dir)
        
        # 确保目录存在
        if not os.path.exists(phone_template_dir):
            return jsonify({'success': True, 'data': [], 'message': '手机号模板目录不存在'})
        
        # 扫描手机号模板文件
        for filename in os.listdir(phone_template_dir):
            if filename.endswith('.txt') and filename != '.gitkeep':
                template_name = filename.replace('.txt', '')
                file_path = os.path.join(phone_template_dir, filename)
                
                # 读取文件内容获取手机号数量和预览
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        phone_numbers = [line.strip() for line in content.split('\n') if line.strip()]
                        phone_count = len(phone_numbers)
                        
                        # 生成预览内容（显示前3个手机号）
                        preview_content = ', '.join(phone_numbers[:3])
                        if phone_count > 3:
                            preview_content += f' ... (共{phone_count}个)'
                        
                        templates.append({
                            'id': template_name,
                            'name': template_name,
                            'phone_count': phone_count,
                            'preview_content': preview_content,
                            'file_path': filename
                        })
                except Exception as e:
                    logger.error(f"读取手机号模板文件失败 {filename}: {str(e)}")
                    continue
        
        # 按名称排序
        templates.sort(key=lambda x: x['name'])
        
        return jsonify({
            'success': True,
            'data': templates,
            'message': f'成功获取 {len(templates)} 个手机号模板'
        })
        
    except Exception as e:
        logger.error(f"获取手机号模板列表失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@mass_messaging_bp.route('/api/phone_templates', methods=['POST'])
@login_required
def api_upload_phone_template():
    """上传手机号模板"""
    try:
        # 获取表单数据
        template_name = request.form.get('template_name')
        if not template_name:
            return jsonify({'success': False, 'message': '模板名称不能为空'})
        
        # 检查是否有上传的文件
        if 'phone_file' not in request.files:
            return jsonify({'success': False, 'message': '请选择要上传的手机号文件'})
        
        file = request.files['phone_file']
        if file.filename == '':
            return jsonify({'success': False, 'message': '请选择要上传的手机号文件'})
        
        # 获取项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        # 从配置文件获取phone_unused_dir路径
        from config import phone_unused_dir
        phone_template_dir = os.path.join(project_root, phone_unused_dir)
        
        # 确保目录存在
        if not os.path.exists(phone_template_dir):
            os.makedirs(phone_template_dir)
        
        # 保存文件
        filename = f"{template_name}.txt"
        file_path = os.path.join(phone_template_dir, filename)
        
        # 读取并验证文件内容
        content = file.read().decode('utf-8')
        phone_numbers = [line.strip() for line in content.split('\n') if line.strip()]
        
        if len(phone_numbers) == 0:
            return jsonify({'success': False, 'message': '文件中没有有效的手机号'})
        
        # 保存文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(phone_numbers))
        
        logger.info(f"手机号模板上传成功: {template_name}, 包含 {len(phone_numbers)} 个手机号")
        
        return jsonify({
            'success': True,
            'message': f'手机号模板 "{template_name}" 上传成功，包含 {len(phone_numbers)} 个手机号'
        })
        
    except Exception as e:
        logger.error(f"上传手机号模板失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@mass_messaging_bp.route('/api/phone_templates/<template_name>', methods=['DELETE'])
@login_required
def api_delete_phone_template(template_name):
    """删除手机号模板"""
    try:
        # 获取项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        # 从配置文件获取phone_unused_dir路径
        from config import phone_unused_dir
        phone_template_dir = os.path.join(project_root, phone_unused_dir)
        
        # 构建文件路径
        filename = f"{template_name}.txt"
        file_path = os.path.join(phone_template_dir, filename)
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'message': '手机号模板不存在'})
        
        # 删除文件
        os.remove(file_path)
        
        logger.info(f"手机号模板删除成功: {template_name}")
        
        return jsonify({
            'success': True,
            'message': f'手机号模板 "{template_name}" 删除成功'
        })
        
    except Exception as e:
        logger.error(f"删除手机号模板失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@mass_messaging_bp.route('/api/mass_messaging/templates', methods=['POST'])
@login_required
def api_save_template():
    """保存发送模板"""
    try:
        data = request.get_json()
        template_name = data.get('name', '').strip()
        template_content = data.get('content', '')
        
        if not template_name:
            return jsonify({'success': False, 'message': '模板名称不能为空'})
        
        # 检查模板名称是否重复
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        template_dir = os.path.join(project_root, 'web', 'config', 'im_default', 'txt')
        template_filename = f"{template_name}_imessage.txt"
        template_path = os.path.join(template_dir, template_filename)
        
        if os.path.exists(template_path):
            return jsonify({'success': False, 'message': '模板名称已存在，请修改模板名称'})
        
        # 确保目录存在
        os.makedirs(template_dir, exist_ok=True)
        
        # 保存模板内容
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(template_content)
        
        logger.info(f"模板保存成功: {template_name}")
        return jsonify({'success': True, 'message': '模板保存成功'})
        
    except Exception as e:
        logger.error(f"保存模板失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@mass_messaging_bp.route('/api/mass_messaging/templates/<template_name>', methods=['DELETE'])
@login_required
def api_delete_template(template_name):
    """删除发送模板"""
    try:
        template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'web', 'config', 'im_default', 'txt')
        template_filename = f"{template_name}_imessage.txt"
        template_path = os.path.join(template_dir, template_filename)
        
        if not os.path.exists(template_path):
            return jsonify({'success': False, 'message': '模板不存在'})
        
        # 删除模板文件
        os.remove(template_path)
        
        # 删除对应的附件文件（如果存在）
        attachment_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'web', 'config', 'im_default', 'file')
        if os.path.exists(attachment_dir):
            for filename in os.listdir(attachment_dir):
                if filename.startswith(f"{template_name}_imessage."):
                    attachment_path = os.path.join(attachment_dir, filename)
                    os.remove(attachment_path)
                    logger.info(f"删除附件文件: {filename}")
        
        logger.info(f"删除模板成功: {template_name}")
        return jsonify({'success': True, 'message': '模板删除成功'})
        
    except Exception as e:
        logger.error(f"删除模板失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@mass_messaging_bp.route('/api/mass_messaging/templates/upload', methods=['POST'])
@login_required
def api_upload_template_attachment():
    """上传模板附件"""
    try:
        template_name = request.form.get('template_name', '').strip()
        
        if not template_name:
            return jsonify({'success': False, 'message': '模板名称不能为空'})
        
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '没有选择文件'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': '没有选择文件'})
        
        # 获取文件扩展名
        file_ext = os.path.splitext(file.filename)[1]
        if not file_ext:
            return jsonify({'success': False, 'message': '文件必须有扩展名'})
        
        # 生成附件文件名
        attachment_filename = f"{template_name}_imessage{file_ext}"
        attachment_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'web', 'config', 'im_default', 'file')
        attachment_path = os.path.join(attachment_dir, attachment_filename)
        
        # 检查文件是否已存在
        if os.path.exists(attachment_path):
            return jsonify({'success': False, 'message': '附件文件名已存在，请修改模板名称'})
        
        # 确保目录存在
        os.makedirs(attachment_dir, exist_ok=True)
        
        # 保存文件
        file.save(attachment_path)
        
        logger.info(f"附件上传成功: {attachment_filename}")
        return jsonify({
            'success': True, 
            'message': '附件上传成功',
            'filename': attachment_filename
        })
        
    except Exception as e:
        logger.error(f"上传附件失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})
    
@mass_messaging_bp.route('/api/mass_messaging/send', methods=['POST'])
@login_required
def api_send_mass_message():
    """批量发信 - 将模板文本和附件传输到选中的客户端"""
    # 这个try语句块在原始代码中有对应的except子句
    # 保持原样即可,因为它不是孤立的try语句
    try:
        data = request.get_json()
        template_id = data.get('template_id')
        phone_template_id = data.get('phone_template_id')
        selected_clients = data.get('selected_clients', [])
        
        if not template_id:
            return jsonify({'success': False, 'message': '请选择发信模板'})
        
        if not phone_template_id:
            return jsonify({'success': False, 'message': '请选择手机号模板'})
        
        if not selected_clients:
            return jsonify({'success': False, 'message': '请选择客户端'})
        
        logger.info(f"开始批量发信任务 - 模板ID: {template_id}, 客户端数量: {len(selected_clients)}")
        
        # 获取模板信息
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        template_dir = os.path.join(project_root, 'web', 'config', 'im_default', 'txt')
        attachment_dir = os.path.join(project_root, 'web', 'config', 'im_default', 'file')
        
        # 查找模板文件
        template_content = ''
        template_name = ''
        attachment_file = None
        phone_template_content = ''
        phone_template_name = phone_template_id
        
        # 首先获取所有模板信息以建立ID映射
        template_names = set()
        if os.path.exists(template_dir):
            for filename in os.listdir(template_dir):
                if filename.endswith('_imessage.txt') and filename != '.gitkeep':
                    template_name = filename.replace('_imessage.txt', '')
                    template_names.add(template_name)
        
        if os.path.exists(attachment_dir):
            for filename in os.listdir(attachment_dir):
                if filename.endswith(('_imessage.png', '_imessage.jpg', '_imessage.jpeg', '_imessage.gif', '_imessage.mp4', '_imessage.mov')) and filename != '.gitkeep':
                    for ext in ['_imessage.png', '_imessage.jpg', '_imessage.jpeg', '_imessage.gif', '_imessage.mp4', '_imessage.mov']:
                        if filename.endswith(ext):
                            template_name = filename.replace(ext, '')
                            template_names.add(template_name)
                            break
        
        # 根据模板ID查找对应的模板（ID对应排序后的索引）
        sorted_names = sorted(template_names)
        try:
            template_index = int(template_id) - 1  # ID从1开始，索引从0开始
            if 0 <= template_index < len(sorted_names):
                template_name = sorted_names[template_index]
                
                # 读取模板内容
                txt_path = os.path.join(template_dir, f"{template_name}_imessage.txt")
                if os.path.exists(txt_path):
                    try:
                        with open(txt_path, 'r', encoding='utf-8') as f:
                            template_content = f.read().strip()
                    except Exception as e:
                        logger.error(f"读取模板文件失败 {txt_path}: {str(e)}")
                        return jsonify({'success': False, 'message': f'读取模板文件失败: {str(e)}'})
            else:
                return jsonify({'success': False, 'message': '模板ID无效'})
        except (ValueError, IndexError):
            return jsonify({'success': False, 'message': '模板ID格式错误'})
        
        if not template_content:
            return jsonify({'success': False, 'message': '模板内容为空或读取失败'})
        
        # 读取手机号模板内容 - 从phone_unused_dir目录读取
        from config import phone_unused_dir
        phone_template_dir = os.path.join(project_root, phone_unused_dir)
        phone_template_path = os.path.join(phone_template_dir, f"{phone_template_name}.txt")
        
        if not os.path.exists(phone_template_path):
            return jsonify({'success': False, 'message': '手机号模板文件不存在'})
        
        try:
            with open(phone_template_path, 'r', encoding='utf-8') as f:
                phone_template_content = f.read().strip()
        except Exception as e:
            logger.error(f"读取手机号模板文件失败 {phone_template_path}: {str(e)}")
            return jsonify({'success': False, 'message': f'读取手机号模板文件失败: {str(e)}'})
        
        if not phone_template_content:
            return jsonify({'success': False, 'message': '手机号模板内容为空'})
        
        # 查找对应的附件文件
        if os.path.exists(attachment_dir) and template_name:
            for att_file in os.listdir(attachment_dir):
                if att_file.startswith(f"{template_name}_imessage."):
                    attachment_file = os.path.join(attachment_dir, att_file)
                    break
        
        # 配置SSH传输路径
        from config import appleidtxt_path
        base_path = appleidtxt_path  # '/Users/wx/Documents/'
        text_target_dir = f"{base_path}send_default/"
        attachment_target_dir = f"{base_path}send_default/images/"
        phone_target_dir = f"{base_path}send_default/"
        
        # 执行文件传输
        results = []
        success_count = 0
        
        for client in selected_clients:
            client_ip = client.get('ip')
            if not client_ip:
                results.append({
                    'client_ip': 'unknown',
                    'success': False,
                    'message': '客户端IP地址无效'
                })
                continue
            
            try:
                # 创建临时文件目录
                temp_dir = os.path.join(project_root, 'temp')
                os.makedirs(temp_dir, exist_ok=True)
                
                # 创建临时文本文件
                temp_text_file = os.path.join(temp_dir, f'send_text_{client_ip.replace(".", "_")}.txt')
                with open(temp_text_file, 'w', encoding='utf-8') as f:
                    f.write(template_content)
                
                # 创建临时手机号文件
                temp_phone_file = os.path.join(temp_dir, f'phone_numbers_{client_ip.replace(".", "_")}.txt')
                with open(temp_phone_file, 'w', encoding='utf-8') as f:
                    f.write(phone_template_content)
                
                # 传输文本文件
                text_scp_cmd = [
                    'scp',
                    '-o', 'StrictHostKeyChecking=no',
                    temp_text_file,
                    f"{vm_username}@{client_ip}:{text_target_dir}message_template.txt"
                ]
                
                logger.info(f"传输文本到 {client_ip}: {' '.join(text_scp_cmd)}")
                text_result = subprocess.run(text_scp_cmd, capture_output=True, text=True, timeout=60)
                text_success = text_result.returncode == 0
                
                # 传输手机号文件
                phone_scp_cmd = [
                    'scp',
                    '-o', 'StrictHostKeyChecking=no',
                    temp_phone_file,
                    f"{vm_username}@{client_ip}:{phone_target_dir}phone_numbers.txt"
                ]
                
                logger.info(f"传输手机号到 {client_ip}: {' '.join(phone_scp_cmd)}")
                phone_result = subprocess.run(phone_scp_cmd, capture_output=True, text=True, timeout=60)
                phone_success = phone_result.returncode == 0
                
                attachment_success = True  # 默认附件传输成功
                
                # 如果有附件，传输附件文件
                if attachment_file and os.path.exists(attachment_file):
                    attachment_scp_cmd = [
                        'scp',
                        '-o', 'StrictHostKeyChecking=no',
                        attachment_file,
                        f"{vm_username}@{client_ip}:{attachment_target_dir}attachment.png"
                    ]
                    
                    logger.info(f"传输附件到 {client_ip}: {' '.join(attachment_scp_cmd)}")
                    attachment_result = subprocess.run(attachment_scp_cmd, capture_output=True, text=True, timeout=60)
                    attachment_success = attachment_result.returncode == 0
                    
                    if not attachment_success:
                        logger.error(f"附件传输失败到 {client_ip}: {attachment_result.stderr}")
                
                # 清理临时文件
                try:
                    os.remove(temp_text_file)
                    os.remove(temp_phone_file)
                except Exception as e:
                    logger.warning(f"清理临时文件失败: {str(e)}")
                
                # 记录结果
                if text_success and phone_success and attachment_success:
                    # 文件传输成功后，调用客户端API执行发信脚本
                    script_result = None
                    script_success = False
                    
                    try:
                        # 调用客户端8787端口API执行{send_imessage}脚本
                        script_api_url = f"http://{client_ip}:8787/run?path={script_remote_path}{send_imessage}"
                        
                        logger.info(f"调用客户端API执行发信脚本: {script_api_url}")
                        script_response = requests.get(
                            script_api_url, 
                            timeout=30
                        )
                        script_result=script_response.json()
                       # script_result = json.dumps(script_response.json(), ensure_ascii=False, indent=2)
                        logger.info(f"script_result: {json.dumps(script_response.json(), ensure_ascii=False, indent=2)}")
                        if script_response.status_code == 200:
                            try:
                                # 根据脚本返回.txt中的JSON格式重新判断发信执行结果
                                # 成功格式：包含status、timestamp、message_content等字段
                                # 失败格式：包含error_message和summary字段
                                if 'error_message' in script_result:
                                    # 失败情况
                                    script_success = False
                                    logger.error(f"脚本执行失败 {client_ip}: {script_result.get('error_message', '未知错误')}")
                                elif 'status' in script_result and script_result.get('status') == 'completed':
                                    # 成功情况
                                    script_success = True
                                    logger.info(f"脚本执行成功 {client_ip}: 成功发送 {script_result.get('successful_numbers', 0)} 条消息")
                                else:
                                    # 兼容旧格式或其他格式
                                    script_success = script_result.get('success', False)
                                    logger.warning(f"脚本返回未知格式 {client_ip}: {script_result}")
                                
                                logger.info(f"脚本执行结果 {client_ip}: {script_result}")
                                logger.info(f"脚本返回的原始响应 {client_ip}: {script_response.text}")
                            except ValueError as json_error:
                                logger.error(f"脚本返回非JSON格式数据 {client_ip}: {script_response.text}")
                                script_result = {
                                    'success': False, 
                                    'message': f'脚本返回非JSON格式数据: {script_response.text[:200]}'
                                }
                                script_success = False
                        else:
                            logger.error(f"脚本API调用失败 {client_ip}: HTTP {script_response.status_code}")
                            script_result = {'success': False, 'message': f'API调用失败: HTTP {script_response.status_code}'}
                          
                    except requests.exceptions.Timeout:
                        logger.error(f"脚本执行超时 {client_ip}")
                        script_result = {'success': False, 'message': '脚本执行超时（30秒）'}
                    except requests.exceptions.ConnectionError:
                        logger.error(f"无法连接到客户端API {client_ip}:8787")
                        script_result = {'success': False, 'message': '无法连接到客户端API'}
                    except Exception as e:
                        logger.error(f"脚本执行异常 {client_ip}: {str(e)}")
                        script_result = {'success': False, 'message': f'脚本执行异常: {str(e)}'}
                    
                    # 根据脚本执行结果更新成功计数和结果
                    if script_success:
                        success_count += 1
                        results.append({
                            'client_ip': client_ip,
                            'success': True,
                            'message': '文件传输和发信执行成功',
                            'text_path': f"{text_target_dir}message_template.txt",
                            'phone_path': f"{phone_target_dir}phone_numbers.txt",
                            'attachment_path': f"{attachment_target_dir}attachment.png" if attachment_file else None,
                            'script_result': script_result
                        })
                    else:
                        results.append({
                            'client_ip': client_ip,
                            'success': False,
                            'message': f'文件传输成功，但发信执行失败: {script_result.get("error_message", "未知错误") if script_result else "脚本调用失败"}',
                            'text_path': f"{text_target_dir}message_template.txt",
                            'phone_path': f"{phone_target_dir}phone_numbers.txt",
                            'attachment_path': f"{attachment_target_dir}attachment.png" if attachment_file else None,
                            'script_result': script_result
                        })
                else:
                    error_msg = []
                    if not text_success:
                        error_msg.append(f"文本传输失败: {text_result.stderr.strip()}")
                    if not phone_success:
                        error_msg.append(f"手机号传输失败: {phone_result.stderr.strip()}")
                    if not attachment_success:
                        error_msg.append(f"附件传输失败: {attachment_result.stderr.strip()}")
                    
                    results.append({
                        'client_ip': client_ip,
                        'success': False,
                        'message': '; '.join(error_msg)
                    })
                
            except subprocess.TimeoutExpired:
                logger.error(f"传输到客户端 {client_ip} 超时")
                results.append({
                    'client_ip': client_ip,
                    'success': False,
                    'message': '传输超时（60秒）'
                })
            except Exception as e:
                logger.error(f"处理客户端 {client_ip} 时发生错误: {str(e)}")
                results.append({
                    'client_ip': client_ip,
                    'success': False,
                    'message': f'处理失败: {str(e)}'
                })
        
        # 生成任务ID
        task_id = f"batch_send_{int(time.time())}"
        
        logger.info(f"批量发信任务完成 - 任务ID: {task_id}, 成功: {success_count}/{len(selected_clients)}")
        
        return jsonify({
            'success': True,
            'message': f'批量发信任务完成，成功传输到 {success_count}/{len(selected_clients)} 个客户端',
            'task_id': task_id,
            'results': results,
            'summary': {
                'total_clients': len(selected_clients),
                'success_count': success_count,
                'failed_count': len(selected_clients) - success_count,
                'template_name': template_name,
                'phone_template_name': phone_template_name,
                'has_attachment': attachment_file is not None,
                'text_target_path': text_target_dir,
                'phone_target_path': phone_target_dir,
                'attachment_target_path': attachment_target_dir
            }
        })
    
    except Exception as e:
        logger.error(f"批量发信任务失败: {str(e)}")
        return jsonify({'success': False, 'message': f'批量发信任务失败: {str(e)}'})

@mass_messaging_bp.route('/api/mass_messaging/send_async', methods=['POST'])
@login_required
def api_send_mass_message_async():
    """批量发信异步版本 - 执行文件传输和脚本调用后立即返回，不等待脚本执行结果"""
    try:
        data = request.get_json()
        template_id = data.get('template_id')
        phone_template_id = data.get('phone_template_id')
        selected_clients = data.get('selected_clients', [])
        
        if not template_id:
            return jsonify({'success': False, 'message': '请选择发信模板'})
        
        if not phone_template_id:
            return jsonify({'success': False, 'message': '请选择手机号模板'})
        
        if not selected_clients:
            return jsonify({'success': False, 'message': '请选择客户端'})
        
        logger.info(f"开始批量发信异步任务 - 模板ID: {template_id}, 客户端数量: {len(selected_clients)}")
        
        # 获取模板信息（复用原有逻辑）
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        template_dir = os.path.join(project_root, 'web', 'config', 'im_default', 'txt')
        attachment_dir = os.path.join(project_root, 'web', 'config', 'im_default', 'file')
        
        # 查找模板文件
        template_content = ''
        template_name = ''
        attachment_file = None
        phone_template_content = ''
        phone_template_name = phone_template_id
        
        # 首先获取所有模板信息以建立ID映射
        template_names = set()
        if os.path.exists(template_dir):
            for filename in os.listdir(template_dir):
                if filename.endswith('_imessage.txt') and filename != '.gitkeep':
                    template_name = filename.replace('_imessage.txt', '')
                    template_names.add(template_name)
        
        if os.path.exists(attachment_dir):
            for filename in os.listdir(attachment_dir):
                if filename.endswith(('_imessage.png', '_imessage.jpg', '_imessage.jpeg', '_imessage.gif', '_imessage.mp4', '_imessage.mov')) and filename != '.gitkeep':
                    for ext in ['_imessage.png', '_imessage.jpg', '_imessage.jpeg', '_imessage.gif', '_imessage.mp4', '_imessage.mov']:
                        if filename.endswith(ext):
                            template_name = filename.replace(ext, '')
                            template_names.add(template_name)
                            break
        
        # 根据模板ID查找对应的模板（ID对应排序后的索引）
        sorted_names = sorted(template_names)
        try:
            template_index = int(template_id) - 1  # ID从1开始，索引从0开始
            if 0 <= template_index < len(sorted_names):
                template_name = sorted_names[template_index]
                
                # 读取模板内容
                txt_path = os.path.join(template_dir, f"{template_name}_imessage.txt")
                if os.path.exists(txt_path):
                    try:
                        with open(txt_path, 'r', encoding='utf-8') as f:
                            template_content = f.read().strip()
                    except Exception as e:
                        logger.error(f"读取模板文件失败 {txt_path}: {str(e)}")
                        return jsonify({'success': False, 'message': f'读取模板文件失败: {str(e)}'})
            else:
                return jsonify({'success': False, 'message': '模板ID无效'})
        except (ValueError, IndexError):
            return jsonify({'success': False, 'message': '模板ID格式错误'})
        
        if not template_content:
            return jsonify({'success': False, 'message': '模板内容为空或读取失败'})
        
        # 读取手机号模板内容
        from config import phone_unused_dir
        phone_template_dir = os.path.join(project_root, phone_unused_dir)
        phone_template_path = os.path.join(phone_template_dir, f"{phone_template_name}.txt")
        
        if not os.path.exists(phone_template_path):
            return jsonify({'success': False, 'message': '手机号模板文件不存在'})
        
        try:
            with open(phone_template_path, 'r', encoding='utf-8') as f:
                phone_template_content = f.read().strip()
        except Exception as e:
            logger.error(f"读取手机号模板文件失败 {phone_template_path}: {str(e)}")
            return jsonify({'success': False, 'message': f'读取手机号模板文件失败: {str(e)}'})
        
        if not phone_template_content:
            return jsonify({'success': False, 'message': '手机号模板内容为空'})
        
        # 查找对应的附件文件
        if os.path.exists(attachment_dir) and template_name:
            for att_file in os.listdir(attachment_dir):
                if att_file.startswith(f"{template_name}_imessage."):
                    attachment_file = os.path.join(attachment_dir, att_file)
                    break
        
        # 配置SSH传输路径
        from config import appleidtxt_path
        base_path = appleidtxt_path
        text_target_dir = f"{base_path}send_default/"
        attachment_target_dir = f"{base_path}send_default/images/"
        phone_target_dir = f"{base_path}send_default/"
        
        # 执行文件传输和脚本调用（异步，不等待结果）
        results = []
        success_count = 0
        
        for client in selected_clients:
            client_ip = client.get('ip')
            if not client_ip:
                results.append({
                    'client_ip': 'unknown',
                    'success': False,
                    'message': '客户端IP地址无效'
                })
                continue
            
            try:
                # 创建临时文件目录
                temp_dir = os.path.join(project_root, 'temp')
                os.makedirs(temp_dir, exist_ok=True)
                
                # 创建临时文本文件
                temp_text_file = os.path.join(temp_dir, f'send_text_{client_ip.replace(".", "_")}.txt')
                with open(temp_text_file, 'w', encoding='utf-8') as f:
                    f.write(template_content)
                
                # 创建临时手机号文件
                temp_phone_file = os.path.join(temp_dir, f'phone_numbers_{client_ip.replace(".", "_")}.txt')
                with open(temp_phone_file, 'w', encoding='utf-8') as f:
                    f.write(phone_template_content)
                
                # 传输文本文件
                text_scp_cmd = [
                    'scp',
                    '-o', 'StrictHostKeyChecking=no',
                    temp_text_file,
                    f"{vm_username}@{client_ip}:{text_target_dir}message_template.txt"
                ]
                
                logger.info(f"传输文本到 {client_ip}: {' '.join(text_scp_cmd)}")
                text_result = subprocess.run(text_scp_cmd, capture_output=True, text=True, timeout=60)
                text_success = text_result.returncode == 0
                
                # 传输手机号文件
                phone_scp_cmd = [
                    'scp',
                    '-o', 'StrictHostKeyChecking=no',
                    temp_phone_file,
                    f"{vm_username}@{client_ip}:{phone_target_dir}phone_numbers.txt"
                ]
                
                logger.info(f"传输手机号到 {client_ip}: {' '.join(phone_scp_cmd)}")
                phone_result = subprocess.run(phone_scp_cmd, capture_output=True, text=True, timeout=60)
                phone_success = phone_result.returncode == 0
                
                attachment_success = True  # 默认附件传输成功
                
                # 如果有附件，传输附件文件
                if attachment_file and os.path.exists(attachment_file):
                    attachment_scp_cmd = [
                        'scp',
                        '-o', 'StrictHostKeyChecking=no',
                        attachment_file,
                        f"{vm_username}@{client_ip}:{attachment_target_dir}attachment.png"
                    ]
                    
                    logger.info(f"传输附件到 {client_ip}: {' '.join(attachment_scp_cmd)}")
                    attachment_result = subprocess.run(attachment_scp_cmd, capture_output=True, text=True, timeout=60)
                    attachment_success = attachment_result.returncode == 0
                    
                    if not attachment_success:
                        logger.error(f"附件传输失败到 {client_ip}: {attachment_result.stderr}")
                
                # 清理临时文件
                try:
                    os.remove(temp_text_file)
                    os.remove(temp_phone_file)
                except Exception as e:
                    logger.warning(f"清理临时文件失败: {str(e)}")
                
                # 记录结果
                if text_success and phone_success and attachment_success:
                    # 文件传输成功后，异步调用客户端API执行发信脚本（不等待结果）
                    try:
                        # 调用客户端8787端口API执行{send_imessage}脚本
                        script_api_url = f"http://{client_ip}:8787/run?path={script_remote_path}{send_imessage}"
                        
                        logger.info(f"异步调用客户端API执行发信脚本: {script_api_url}")
                        # 使用异步方式调用，不等待响应
                        import threading
                        def async_script_call():
                            try:
                                requests.get(script_api_url, timeout=5)  # 短超时，不关心结果
                            except:
                                pass  # 忽略所有异常
                        
                        thread = threading.Thread(target=async_script_call)
                        thread.daemon = True
                        thread.start()
                        
                        success_count += 1
                        results.append({
                            'client_ip': client_ip,
                            'success': True,
                            'message': '文件传输成功，脚本已异步执行',
                            'text_path': f"{text_target_dir}message_template.txt",
                            'phone_path': f"{phone_target_dir}phone_numbers.txt",
                            'attachment_path': f"{attachment_target_dir}attachment.png" if attachment_file else None
                        })
                        
                    except Exception as e:
                        logger.error(f"脚本异步调用异常 {client_ip}: {str(e)}")
                        success_count += 1  # 文件传输成功就算成功
                        results.append({
                            'client_ip': client_ip,
                            'success': True,
                            'message': '文件传输成功，脚本调用可能失败',
                            'text_path': f"{text_target_dir}message_template.txt",
                            'phone_path': f"{phone_target_dir}phone_numbers.txt",
                            'attachment_path': f"{attachment_target_dir}attachment.png" if attachment_file else None
                        })
                else:
                    error_msg = []
                    if not text_success:
                        error_msg.append(f"文本传输失败: {text_result.stderr.strip()}")
                    if not phone_success:
                        error_msg.append(f"手机号传输失败: {phone_result.stderr.strip()}")
                    if not attachment_success:
                        error_msg.append(f"附件传输失败: {attachment_result.stderr.strip()}")
                    
                    results.append({
                        'client_ip': client_ip,
                        'success': False,
                        'message': '; '.join(error_msg)
                    })
                
            except subprocess.TimeoutExpired:
                logger.error(f"传输到客户端 {client_ip} 超时")
                results.append({
                    'client_ip': client_ip,
                    'success': False,
                    'message': '传输超时（60秒）'
                })
            except Exception as e:
                logger.error(f"处理客户端 {client_ip} 时发生错误: {str(e)}")
                results.append({
                    'client_ip': client_ip,
                    'success': False,
                    'message': f'处理失败: {str(e)}'
                })
        
        # 生成任务ID
        task_id = f"batch_send_async_{int(time.time())}"
        
        logger.info(f"批量发信异步任务完成 - 任务ID: {task_id}, 成功: {success_count}/{len(selected_clients)}")
        
        return jsonify({
            'success': True,
            'message': f'批量发信任务已执行完毕，成功处理 {success_count}/{len(selected_clients)} 个客户端',
            'task_id': task_id,
            'results': results,
            'summary': {
                'total_clients': len(selected_clients),
                'success_count': success_count,
                'failed_count': len(selected_clients) - success_count,
                'template_name': template_name,
                'phone_template_name': phone_template_name,
                'has_attachment': attachment_file is not None,
                'execution_mode': 'async'
            }
        })
        
    except Exception as e:
        logger.error(f"批量发信异步任务失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@mass_messaging_bp.route('/api/mass_messaging/receipts', methods=['GET'])
@login_required
def api_get_receipts():
    """获取发送回执"""
    try:
        # 这里应该从数据库中获取回执数据
        receipts = [
            {'id': 1, 'phone': '138****1234', 'status': 'success', 'send_time': '2025-01-15 10:30:00', 'content': '测试消息'},
            {'id': 2, 'phone': '139****5678', 'status': 'failed', 'send_time': '2025-01-15 10:30:01', 'content': '测试消息', 'error': '号码无效'}
        ]
        return jsonify({'success': True, 'data': receipts})
    except Exception as e:
        logger.error(f"获取回执失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@mass_messaging_bp.route('/api/mass_messaging/phone_numbers', methods=['GET'])
@login_required
def api_get_phone_numbers():
    """获取手机号码列表"""
    try:
        # 这里应该从数据库或文件中获取手机号码
        phone_numbers = [
            {'id': 1, 'phone': '138****1234', 'status': 'active', 'group': '客户组A'},
            {'id': 2, 'phone': '139****5678', 'status': 'active', 'group': '客户组B'},
            {'id': 3, 'phone': '137****9012', 'status': 'inactive', 'group': '客户组A'}
        ]
        return jsonify({'success': True, 'data': phone_numbers})
    except Exception as e:
        logger.error(f"获取手机号码列表失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})



        
