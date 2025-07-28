#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(funcName)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler('create_templates_debug.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 定义所有需要的模板文件
templates = {
    'wuma.html': {
        'title': '虚拟机五码管理',
        'icon': 'fas fa-key',
        'active_menu': 'wuma_page',
        'content_title': '五码管理',
        'content_description': '管理虚拟机的五码信息，包括序列号、主板序列号、系统UUID等。'
    },
    'mupan.html': {
        'title': '虚拟机母盘管理',
        'icon': 'fas fa-hdd',
        'active_menu': 'mupan_page',
        'content_title': '母盘管理',
        'content_description': '管理虚拟机的母盘模板，包括模板创建、更新、删除等操作。'
    },
    'encrypt_code.html': {
        'title': '代码加密',
        'icon': 'fas fa-lock',
        'active_menu': 'encrypt_code_page',
        'content_title': '代码加密',
        'content_description': '对代码文件进行加密处理，保护知识产权。'
    },
    'encrypt_wuma.html': {
        'title': '五码加密',
        'icon': 'fas fa-shield-alt',
        'active_menu': 'encrypt_wuma_page',
        'content_title': '五码加密',
        'content_description': '对五码信息进行加密存储，确保数据安全。'
    },
    'encrypt_id.html': {
        'title': 'ID加密',
        'icon': 'fas fa-user-secret',
        'active_menu': 'encrypt_id_page',
        'content_title': 'ID加密',
        'content_description': '对用户ID和身份信息进行加密处理。'
    },
    'proxy_assign.html': {
        'title': '代理IP分配',
        'icon': 'fas fa-network-wired',
        'active_menu': 'proxy_assign_page',
        'content_title': '代理IP分配',
        'content_description': '管理代理IP的分配和使用情况。'
    },
    'soft_version.html': {
        'title': '版本查看',
        'icon': 'fas fa-info-circle',
        'active_menu': 'soft_version_page',
        'content_title': '版本查看',
        'content_description': '查看虚拟机软件的版本信息和更新状态。'
    },
    'soft_env.html': {
        'title': '环境变量',
        'icon': 'fas fa-cogs',
        'active_menu': 'soft_env_page',
        'content_title': '环境变量',
        'content_description': '管理虚拟机的环境变量配置。'
    }
}

def create_template_content(template_info):
    """生成模板内容"""
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{template_info['title']} - macOS VM</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body {{
            background-color: #f8f9fa;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }}
        
        .sidebar {{
            background: white;
            box-shadow: 2px 0 5px rgba(0,0,0,0.1);
            min-height: 100vh;
            position: fixed;
            top: 0;
            left: 0;
            z-index: 1000;
            width: 280px;
        }}
        
        .accordion-button:not(.collapsed) {{
            background-color: #e7f3ff;
            color: #0d6efd;
        }}
        
        .nav-link {{
            color: #495057;
            padding: 8px 16px;
            border-radius: 4px;
            margin: 2px 0;
            transition: all 0.2s;
        }}
        
        .nav-link:hover {{
            background-color: #f8f9fa;
            color: #0d6efd;
        }}
        
        .nav-link.active {{
            background-color: #0d6efd;
            color: white;
        }}
        
        .card {{
            border: none;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            border-radius: 10px;
        }}
        
        .card-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 10px 10px 0 0 !important;
            padding: 20px;
        }}
    </style>
</head>
<body>
    <!-- 顶部导航栏 -->
    <div class="navbar navbar-expand-lg navbar-light bg-white shadow-sm" style="position: fixed; top: 0; left: 280px; right: 0; z-index: 1000;">
        <div class="container-fluid">
            <span class="navbar-brand mb-0 h1">
                <i class="{template_info['icon']} me-2"></i>{template_info['title']}
            </span>
            <div class="d-flex">
                <div class="dropdown me-3">
                    <button class="btn btn-outline-secondary dropdown-toggle" type="button" id="langDropdown" data-bs-toggle="dropdown" aria-expanded="false">
                        语言
                    </button>
                    <ul class="dropdown-menu" aria-labelledby="langDropdown">
                        <li><a class="dropdown-item" href="?lang=zh">中文</a></li>
                        <li><a class="dropdown-item" href="?lang=en">English</a></li>
                    </ul>
                </div>
                <a href="{{{{ url_for('logout') }}}}" class="btn btn-outline-secondary">登出</a>
            </div>
        </div>
    </div>
    
    <div class="container-fluid" style="margin-left: 280px; margin-top: 80px;">
        <div class="row">
            <!-- 左侧菜单 -->
            <nav class="col-md-3 col-lg-2 sidebar bg-white p-3">
                <h5 class="mb-4"><span style="color:#000; font-style:italic; font-weight:bold;">macos_vm</span></h5>
                <div class="accordion" id="accordionMenu">
                    <div class="accordion-item">
                        <h2 class="accordion-header" id="headingVM">
                            <button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#collapseVM" aria-expanded="true" aria-controls="collapseVM">
                                虚拟机管理
                            </button>
                        </h2>
                        <div id="collapseVM" class="accordion-collapse collapse show" aria-labelledby="headingVM" data-bs-parent="#accordionMenu">
                            <div class="accordion-body p-0">
                                <ul class="nav flex-column">
                                    <li class="nav-item">
                                        <a class="nav-link" href="{{{{ url_for('clone_vm_page') }}}}" onclick="handleCloneClick()">虚拟机批量克隆</a>
                                    </li>
                                    <li class="nav-item">
                                        <a class="nav-link" href="{{{{ url_for('vm_management_page') }}}}" onclick="handleVMManagementClick()">虚拟机克隆列表</a>
                                    </li>
                                    <li class="nav-item">
                                        <a class="nav-link" href="{{{{ url_for('vm_info_page') }}}}" onclick="handleVMInfoClick()">虚拟机成品信息</a>
                                    </li>
                                    <li class="nav-item">
                                        <a class="nav-link" href="{{{{ url_for('vm_script_page') }}}}" onclick="handleVMScriptClick()">虚拟机脚本管理</a>
                                    </li>
                                    <li class="nav-item">
                                        <a class="nav-link" href="{{{{ url_for('vm_trust_page') }}}}" onclick="handleVMTrustClick()">虚拟机互信管理</a>
                                    </li>
                                </ul>
                            </div>
                        </div>
                    </div>
                    <div class="accordion-item">
                        <h2 class="accordion-header" id="headingBoot">
                            <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapseBoot" aria-expanded="false" aria-controls="collapseBoot">
                                母盘及五码管理
                            </button>
                        </h2>
                        <div id="collapseBoot" class="accordion-collapse collapse" aria-labelledby="headingBoot" data-bs-parent="#accordionMenu">
                            <div class="accordion-body p-0">
                                <ul class="nav flex-column">
                                    <li class="nav-item">
                                        <a class="nav-link" href="{{{{ url_for('wuma_page') }}}}" onclick="handleWumaClick()">虚拟机五码管理</a>
                                    </li>
                                    <li class="nav-item">
                                        <a class="nav-link" href="{{{{ url_for('mupan_page') }}}}" onclick="handleMupanClick()">虚拟机母盘管理</a>
                                    </li>
                                </ul>
                            </div>
                        </div>
                    </div>
                    <div class="accordion-item">
                        <h2 class="accordion-header" id="headingEncrypt">
                            <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapseEncrypt" aria-expanded="false" aria-controls="collapseEncrypt">
                                数据加密功能
                            </button>
                        </h2>
                        <div id="collapseEncrypt" class="accordion-collapse collapse" aria-labelledby="headingEncrypt" data-bs-parent="#accordionMenu">
                            <div class="accordion-body p-0">
                                <ul class="nav flex-column">
                                    <li class="nav-item">
                                        <a class="nav-link" href="{{{{ url_for('encrypt_code_page') }}}}" onclick="handleEncryptCodeClick()">代码加密</a>
                                    </li>
                                    <li class="nav-item">
                                        <a class="nav-link" href="{{{{ url_for('encrypt_wuma_page') }}}}" onclick="handleEncryptWumaClick()">五码加密</a>
                                    </li>
                                    <li class="nav-item">
                                        <a class="nav-link" href="{{{{ url_for('encrypt_id_page') }}}}" onclick="handleEncryptIdClick()">id加密</a>
                                    </li>
                                </ul>
                            </div>
                        </div>
                    </div>
                    <div class="accordion-item">
                        <h2 class="accordion-header" id="headingProxy">
                            <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapseProxy" aria-expanded="false" aria-controls="collapseProxy">
                                代理ip配置
                            </button>
                        </h2>
                        <div id="collapseProxy" class="accordion-collapse collapse" aria-labelledby="headingProxy" data-bs-parent="#accordionMenu">
                            <div class="accordion-body p-0">
                                <ul class="nav flex-column">
                                    <li class="nav-item">
                                        <a class="nav-link" href="{{{{ url_for('proxy_assign_page') }}}}" onclick="handleProxyAssignClick()">代理ip分配</a>
                                    </li>
                                </ul>
                            </div>
                        </div>
                    </div>
                    <div class="accordion-item">
                        <h2 class="accordion-header" id="headingSoft">
                            <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapseSoft" aria-expanded="false" aria-controls="collapseSoft">
                                虚拟机软件管理
                            </button>
                        </h2>
                        <div id="collapseSoft" class="accordion-collapse collapse" aria-labelledby="headingSoft" data-bs-parent="#accordionMenu">
                            <div class="accordion-body p-0">
                                <ul class="nav flex-column">
                                    <li class="nav-item">
                                        <a class="nav-link" href="{{{{ url_for('soft_version_page') }}}}" onclick="handleSoftVersionClick()">版本查看</a>
                                    </li>
                                    <li class="nav-item">
                                        <a class="nav-link" href="{{{{ url_for('soft_env_page') }}}}" onclick="handleSoftEnvClick()">环境变量</a>
                                    </li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            </nav>
            
            <!-- 右侧内容区域 -->
            <div class="col-md-9 col-lg-10">
                <div class="card">
                    <div class="card-header">
                        <div class="d-flex justify-content-between align-items-center">
                            <h4 class="mb-0">
                                <i class="{template_info['icon']} me-2"></i>{template_info['content_title']}
                            </h4>
                            <button class="btn btn-primary" onclick="refreshData()">
                                <i class="fas fa-sync-alt me-2"></i>刷新数据
                            </button>
                        </div>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-md-12">
                                <h5>{template_info['content_title']}</h5>
                                <p class="text-muted">{template_info['content_description']}</p>
                                
                                <div class="alert alert-info">
                                    <i class="fas fa-info-circle me-2"></i>
                                    此页面正在开发中，更多功能即将推出。
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // 菜单处理函数
        function handleCloneClick() {{
            ensureMenuExpanded('collapseVM', 'collapseVM');
        }}

        function handleVMManagementClick() {{
            ensureMenuExpanded('collapseVM', 'collapseVM');
        }}

        function handleVMInfoClick() {{
            ensureMenuExpanded('collapseVM', 'collapseVM');
        }}

        function handleVMScriptClick() {{
            ensureMenuExpanded('collapseVM', 'collapseVM');
        }}

        function handleVMTrustClick() {{
            ensureMenuExpanded('collapseVM', 'collapseVM');
        }}

        function handleWumaClick() {{
            ensureMenuExpanded('collapseBoot', 'collapseBoot');
        }}

        function handleMupanClick() {{
            ensureMenuExpanded('collapseBoot', 'collapseBoot');
        }}

        function handleEncryptCodeClick() {{
            ensureMenuExpanded('collapseEncrypt', 'collapseEncrypt');
        }}

        function handleEncryptWumaClick() {{
            ensureMenuExpanded('collapseEncrypt', 'collapseEncrypt');
        }}

        function handleEncryptIdClick() {{
            ensureMenuExpanded('collapseEncrypt', 'collapseEncrypt');
        }}

        function handleProxyAssignClick() {{
            ensureMenuExpanded('collapseProxy', 'collapseProxy');
        }}

        function handleSoftVersionClick() {{
            ensureMenuExpanded('collapseSoft', 'collapseSoft');
        }}

        function handleSoftEnvClick() {{
            ensureMenuExpanded('collapseSoft', 'collapseSoft');
        }}

        // 通用函数：确保菜单展开并设置链接激活状态
        function ensureMenuExpanded(menuId, linkContainerId) {{
            const menuCollapse = document.getElementById(menuId);
            const menuButton = document.getElementById(menuId.replace('collapse', 'heading')).querySelector('.accordion-button');
            
            if (menuCollapse && menuButton) {{
                // 移除折叠类，添加展开类
                menuCollapse.classList.remove('collapse');
                menuCollapse.classList.add('show');
                menuButton.setAttribute('aria-expanded', 'true');
                menuButton.classList.remove('collapsed');
            }}
            
            // 设置当前链接为激活状态
            const links = document.querySelectorAll(`#${{linkContainerId}} .nav-link`);
            links.forEach(link => link.classList.remove('active'));
            event.target.classList.add('active');
        }}

        function refreshData() {{
            // 刷新数据的逻辑
            console.log('刷新数据');
        }}
    </script>
</body>
</html>'''

def main():
    """主函数"""
    logger.info("开始创建模板文件")
    templates_dir = 'templates'
    
    # 确保templates目录存在
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
        logger.info(f"创建templates目录: {templates_dir}")
    else:
        logger.debug(f"templates目录已存在: {templates_dir}")
    
    # 创建所有模板文件
    created_count = 0
    skipped_count = 0
    
    for filename, template_info in templates.items():
        filepath = os.path.join(templates_dir, filename)
        
        # 检查文件是否已存在
        if os.path.exists(filepath):
            logger.debug(f"文件 {filename} 已存在，跳过...")
            skipped_count += 1
            continue
        
        # 创建模板文件
        logger.debug(f"创建模板文件: {filename}")
        content = create_template_content(template_info)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"已创建模板文件: {filename}")
        created_count += 1
    
    logger.info(f"模板文件创建完成 - 创建: {created_count}, 跳过: {skipped_count}")
    print("所有模板文件创建完成！")

if __name__ == '__main__':
    main() 