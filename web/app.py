from flask import Flask, render_template, request, redirect, url_for, session, flash
from functools import wraps
import os
import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # 用于会话加密

# 固定账号
USERNAME = 'admin'
PASSWORD = '123456'

# 确保 web/templates/ 目录下有 login.html 和 dashboard.html 文件，否则会报错。
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == USERNAME and password == PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            flash('用户名或密码错误')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # 虚拟机列表假数据
    vm_list = [
        {'name': 'macOS-10.12', 'ip': '192.168.1.101', 'status': '运行中', 'imessage': '...'},
        {'name': 'macOS-10.15', 'ip': '192.168.1.102', 'status': '已关闭', 'imessage': '...'},
        {'name': 'macOS-11.0', 'ip': '192.168.1.103', 'status': '运行中', 'imessage': '...'},
    ]
    # 虚拟机五码管理假数据
    wuma_list = [
        {'name': 'macOS-10.12', 'available': 5, 'used': 2},
        {'name': 'macOS-10.15', 'available': 3, 'used': 1},
        {'name': 'macOS-11.0', 'available': 8, 'used': 4},
    ]
    # 读取 macos_sh 目录下脚本文件
    script_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'macos_sh')
    script_list = []
    if os.path.exists(script_dir):
        for fname in os.listdir(script_dir):
            fpath = os.path.join(script_dir, fname)
            if os.path.isfile(fpath):
                stat = os.stat(fpath)
                mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y/%m/%d %H:%M')
                size = stat.st_size
                script_list.append({'name': fname, 'mtime': mtime, 'size': size})
    script_list.sort(key=lambda x: x['name'])
    return render_template('dashboard.html', username=session.get('username'), vm_list=vm_list, script_list=script_list, wuma_list=wuma_list)

@app.route('/logout')
@login_required
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True) 