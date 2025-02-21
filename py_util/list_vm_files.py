import os

def find_vmx_files(directory):
    """遍历目录及其子目录，查找所有 .vmx 文件"""
    vmx_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".vmx"):
                vmx_files.append(os.path.join(root, file))
    return vmx_files
