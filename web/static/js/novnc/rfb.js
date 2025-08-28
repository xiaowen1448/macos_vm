// 简化的RFB客户端实现
(function(global) {
    'use strict';

    // RFB客户端类
    function RFB(target, url, options) {
        this.target = target;
        this.url = url;
        this.options = options || {};
        this.connected = false;
        this.websocket = null;
        this.canvas = null;
        this.ctx = null;
        this.eventListeners = {};
        
        this.init();
        
        // 自动开始连接
        setTimeout(() => {
            this.connect();
        }, 100);
    }

    RFB.prototype.init = function() {
        // 创建canvas元素
        this.canvas = document.createElement('canvas');
        this.canvas.width = 800;
        this.canvas.height = 600;
        this.canvas.style.border = '1px solid #ccc';
        this.canvas.style.display = 'block';
        this.canvas.style.margin = '10px auto';
        this.canvas.style.backgroundColor = '#000';
        
        // 清空目标容器并添加canvas
        if (typeof this.target === 'string') {
            this.target = document.getElementById(this.target);
        }
        this.target.innerHTML = '';
        this.target.appendChild(this.canvas);
        
        this.ctx = this.canvas.getContext('2d');
        
        // 显示连接状态
        this.showStatus('准备连接VNC服务器...');
    };

    RFB.prototype.showStatus = function(message) {
        this.ctx.fillStyle = '#f0f0f0';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        
        this.ctx.fillStyle = '#333';
        this.ctx.font = '16px Arial';
        this.ctx.textAlign = 'center';
        this.ctx.fillText(message, this.canvas.width / 2, this.canvas.height / 2);
    };

    // 添加事件监听器方法
    RFB.prototype.addEventListener = function(event, callback) {
        if (!this.eventListeners[event]) {
            this.eventListeners[event] = [];
        }
        this.eventListeners[event].push(callback);
    };

    // 触发事件
    RFB.prototype.dispatchEvent = function(event, data) {
        if (this.eventListeners[event]) {
            this.eventListeners[event].forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error('事件回调执行失败:', error);
                }
            });
        }
    };

    RFB.prototype.connect = function() {
        try {
            // 模拟连接过程
            this.showStatus('正在连接VNC服务器...');
            
            // 模拟连接成功
            setTimeout(() => {
                this.showStatus('VNC连接已建立');
                this.connected = true;
                
                // 触发连接事件
                this.dispatchEvent('connect');
                
                // 显示虚拟桌面
                this.drawVirtualDesktop();
                
            }, 1500);
            
        } catch (error) {
            console.error('VNC连接失败:', error);
            this.showStatus('VNC连接失败: ' + error.message);
            
            this.dispatchEvent('disconnect', { clean: false, error: error });
        }
    };

    RFB.prototype.disconnect = function() {
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }
        
        this.connected = false;
        this.showStatus('VNC连接已断开');
        
        this.dispatchEvent('disconnect', { clean: true });
    };

    // 绘制虚拟桌面
    RFB.prototype.drawVirtualDesktop = function() {
        // 绘制一个简单的桌面背景
        this.ctx.fillStyle = '#2c3e50';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        
        // 绘制一些窗口模拟
        this.ctx.fillStyle = '#ecf0f1';
        this.ctx.fillRect(50, 50, 300, 200);
        this.ctx.strokeStyle = '#34495e';
        this.ctx.strokeRect(50, 50, 300, 200);
        
        // 窗口标题栏
        this.ctx.fillStyle = '#3498db';
        this.ctx.fillRect(50, 50, 300, 30);
        
        // 窗口标题
        this.ctx.fillStyle = '#fff';
        this.ctx.font = '14px Arial';
        this.ctx.textAlign = 'left';
        this.ctx.fillText('虚拟机桌面 - 模拟显示', 60, 70);
        
        // 状态信息
        this.ctx.fillStyle = '#27ae60';
        this.ctx.font = '16px Arial';
        this.ctx.textAlign = 'center';
        this.ctx.fillText('VNC连接已建立', this.canvas.width / 2, this.canvas.height - 50);
        this.ctx.fillText('可以使用控制按钮进行操作', this.canvas.width / 2, this.canvas.height - 30);
    };

    // 发送凭据方法
    RFB.prototype.sendCredentials = function(credentials) {
        console.log('发送VNC凭据:', credentials);
        // 模拟凭据验证成功
        setTimeout(() => {
            this.showStatus('凭据验证成功');
        }, 500);
    };

    RFB.prototype.sendKey = function(keysym, down) {
        console.log('发送按键:', keysym, down ? '按下' : '释放');
        // 这里应该通过WebSocket发送按键事件到VNC服务器
        
        // 在画布上显示按键反馈
        if (this.connected && this.ctx) {
            this.ctx.fillStyle = 'rgba(255, 255, 0, 0.3)';
            this.ctx.fillRect(10, 10, 100, 30);
            this.ctx.fillStyle = '#000';
            this.ctx.font = '12px Arial';
            this.ctx.textAlign = 'left';
            this.ctx.fillText('按键: ' + keysym, 15, 30);
        }
    };

    RFB.prototype.sendCtrlAltDel = function() {
        console.log('发送Ctrl+Alt+Del');
        
        // 在画布上显示Ctrl+Alt+Del反馈
        if (this.connected && this.ctx) {
            this.ctx.fillStyle = 'rgba(255, 0, 0, 0.5)';
            this.ctx.fillRect(this.canvas.width / 2 - 75, this.canvas.height / 2 - 15, 150, 30);
            this.ctx.fillStyle = '#fff';
            this.ctx.font = '16px Arial';
            this.ctx.textAlign = 'center';
            this.ctx.fillText('Ctrl+Alt+Del', this.canvas.width / 2, this.canvas.height / 2 + 5);
            
            // 2秒后清除显示
            setTimeout(() => {
                this.drawVirtualDesktop();
            }, 2000);
        }
        
        // 发送特殊按键组合
        this.sendKey(0xffe3, true);  // Ctrl
        this.sendKey(0xffe9, true);  // Alt
        this.sendKey(0xffff, true);  // Del
        
        setTimeout(() => {
            this.sendKey(0xffff, false); // Del
            this.sendKey(0xffe9, false); // Alt
            this.sendKey(0xffe3, false); // Ctrl
        }, 100);
    };

    // 导出到全局
    global.RFB = RFB;

})(window);