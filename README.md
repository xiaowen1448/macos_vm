新版控制台开发登录窗口
<img width="1841" height="972" alt="image" src="https://github.com/user-attachments/assets/4b99351c-f044-488d-91cb-23ab8eee3e67" />


<img width="1839" height="970" alt="image" src="https://github.com/user-attachments/assets/04555bba-b5c0-4a99-8046-68643bdefc6d" />

<img width="1839" height="970" alt="image" src="https://github.com/user-attachments/assets/da34dc0c-8b2d-46bb-8584-8afd5009bb02" />

![Uploading image.png…]()



虚拟机批量克隆，实时和历史日志信息

<img width="1841" height="972" alt="image" src="https://github.com/user-attachments/assets/1c196730-be99-4f26-8d1c-d22b86619d58" />


虚拟机管理界面，增加图标状态监控，开机关机，重启挂起，脚本发送和脚本执行按钮

<img width="1841" height="972" alt="image" src="https://github.com/user-attachments/assets/efa1175c-8f4f-4b99-8b9c-75fda0580918" />

虚拟机脚本管理

<img width="1841" height="972" alt="image" src="https://github.com/user-attachments/assets/f3f3ab8a-2658-4fde-877f-1015fcbb6188" />

虚拟机五码管理

<img width="1841" height="972" alt="image" src="https://github.com/user-attachments/assets/55ba27c1-7551-48ac-9a38-08dd8fdbfa4b" />


# macos_vm

批量克隆增加监控虚拟机功能如下图：

![0dd9b2cb1d55f72bb9d4a9d99421949](https://github.com/user-attachments/assets/58ca7808-06b7-4452-9675-e6d2a8f6697c)

脚本执行完毕输出如下

![image](https://github.com/user-attachments/assets/9628b8f6-f49f-40b0-9636-c38f838783d1)

![image](https://github.com/user-attachments/assets/e8c746ba-3c48-404f-b5e3-f3593ab2560f)




此项目脚本用户批量克隆虚拟机，更改 kbjfrfpoJU值，ju值查看可利用iMessageDebug运行查看

wx@bogon ~ % /Users/wx/Desktop/iMessageDebug ; exit;
SmUUID: failed
**********************iMessage Debug**********************
Credits: ElNono, mdmwii,flux84, sugarface, pokenguyen


              Model: VMware20,1
           Board-id: Mac-AA95B1DDAB278B95
       SerialNumber: VMLbH9Kbb8Q4
      Hardware UUID: 564D9976-62CB-847F-619E-157CB36A4660

          System-ID: failed
                ROM: 564d997662cb
  BoardSerialNumber: hH9hnhV8s2pGYA...

         Gq3489ugfi: 3719cd7c333ab35387fcb32d088d7087fc
          Fyp98tpgj: ba5969a6b702e9d3f7bcc2b7f0d2307a0a
         kbjfrfpoJU: 39feee3569700187b9e15f700427984e20
       oycqAZloTNDm: c3c5004bcba694b857bc5fc61b82ff6915
       abKPld1EcMni: e4eead6a92076fd3104f3e6eede0d51da3

Do you want to save to iMessageDebug.txt? (y/n) 
ju值为： kbjfrfpoJU: 39feee3569700187b9e15f700427984e20

批量实现克隆虚拟机需求，要求实现每台虚拟机ju值为唯一，五码每台为唯一

windows 环境配置
======================================================

VMware® Workstation 环境配置

VMware® Workstation 17 Pro
17.5.1 build-23298084
![image](https://github.com/user-attachments/assets/7fb032b9-26b4-4f01-ae50-4356ffa5823b)

修改完的成品如下图：

vm01

![image](https://github.com/user-attachments/assets/18e10026-c924-4810-834e-b12cc8871b12)

vm02

![image](https://github.com/user-attachments/assets/8b5dcd4e-207a-43f7-b12c-60424f4930c4)

新增低版本10.12克隆
<img width="1832" height="600" alt="image" src="https://github.com/user-attachments/assets/48383dc2-8665-4df7-8b47-f5b95fc2e52a" />


<img width="1635" height="1004" alt="image" src="https://github.com/user-attachments/assets/2be5b48a-8a9b-407b-97f0-b9b7845168e7" />

<img width="1639" height="995" alt="image" src="https://github.com/user-attachments/assets/f06c1e72-9267-4007-92b6-4a804a877cdb" />

初成模型，底层后续实现，客户端和web客户端均可

## 启动方式

### 1. Web浏览器版本
```bash
# 启动Web应用
python app.py

# 或者使用批处理脚本
start.bat
```

### 2. 桌面应用版本 (WebView)
```bash
# 启动桌面WebView应用
python webview_app.py

# 或者使用批处理脚本
start_webview.bat
```

### 3. 依赖测试
```bash
# 测试PyQt5依赖是否正确安装
python test_webview.py
```

## 访问地址
- Web版本: http://127.0.0.1:5000
- 默认用户名: admin
- 默认密码: 123456


<img width="1334" height="846" alt="image" src="https://github.com/user-attachments/assets/7abfcd62-8c8a-40ad-848e-c6d30dd3302e" />

<img width="1841" height="972" alt="image" src="https://github.com/user-attachments/assets/eba205c2-cbe9-419f-9ac4-9a2bfbfc9ce9" />

<img width="1841" height="972" alt="image" src="https://github.com/user-attachments/assets/8fffa2f2-b131-4dd9-8d18-34745540e239" />



技术支持咨询： Telegram：@xiaowen1448
wechat：w8686512








