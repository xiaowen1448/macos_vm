#import <Foundation/Foundation.h>
#import <AppKit/AppKit.h>
#import <sys/socket.h>
#import <netinet/in.h>
#import <arpa/inet.h>
#import <unistd.h>

// HTTP服务器类
@interface HTTPServer : NSObject
@property (nonatomic, assign) UInt16 port;
@property (nonatomic, assign) int serverSocket;
@property (nonatomic, assign) BOOL isRunning;

- (instancetype)initWithPort:(UInt16)port;
- (void)start;
- (void)stop;
- (void)listenForConnections;
- (void)handleConnection:(int)clientSocket;
- (NSData *)handleRequest:(NSString *)request;
- (NSData *)createResponse:(int)status body:(NSDictionary *)body;
@end

// AppleScript运行器类
@interface ScriptRunner : NSObject
+ (void)runScript:(NSString *)scriptPath arguments:(NSArray *)arguments completion:(void(^)(NSString *output, NSError *error))completion;
@end

// 应用程序代理类
@interface AppDelegate : NSObject <NSApplicationDelegate>
@property (nonatomic, strong) HTTPServer *httpServer;
@property (nonatomic, strong) NSStatusItem *statusItem;
@end

// HTTP服务器实现
@implementation HTTPServer

- (instancetype)initWithPort:(UInt16)port {
    self = [super init];
    if (self) {
        _port = port;
        _serverSocket = -1;
        _isRunning = NO;
    }
    return self;
}

- (void)start {
    // 创建socket
    self.serverSocket = socket(AF_INET, SOCK_STREAM, 0);
    if (self.serverSocket == -1) {
        NSLog(@"Failed to create socket: %s", strerror(errno));
        return;
    }
    
    // 设置socket选项
    int opt = 1;
    setsockopt(self.serverSocket, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
    
    // 绑定socket
    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(self.port);
    addr.sin_addr.s_addr = INADDR_ANY;
    
    if (bind(self.serverSocket, (struct sockaddr *)&addr, sizeof(addr)) == -1) {
        NSLog(@"Failed to bind socket: %s", strerror(errno));
        return;
    }
    
    // 监听连接
    if (listen(self.serverSocket, 5) == -1) {
        NSLog(@"Failed to listen on socket: %s", strerror(errno));
        return;
    }
    
    self.isRunning = YES;
    NSLog(@"HTTP server started on port %d", self.port);
    
    // 在后台线程监听连接
    dispatch_async(dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT, 0), ^{
        [self listenForConnections];
    });
}

- (void)stop {
    self.isRunning = NO;
    if (self.serverSocket != -1) {
        close(self.serverSocket);
        self.serverSocket = -1;
    }
}

- (void)listenForConnections {
    while (self.isRunning) {
        struct sockaddr_in clientAddr;
        socklen_t addrLen = sizeof(clientAddr);
        
        int clientSocket = accept(self.serverSocket, (struct sockaddr *)&clientAddr, &addrLen);
        if (clientSocket != -1) {
            dispatch_async(dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT, 0), ^{
                [self handleConnection:clientSocket];
            });
        }
    }
}

- (void)handleConnection:(int)clientSocket {
    @autoreleasepool {
        char buffer[4096];
        ssize_t bytesRead = recv(clientSocket, buffer, sizeof(buffer) - 1, 0);
        
        if (bytesRead > 0) {
            buffer[bytesRead] = '\0';
            NSString *request = [NSString stringWithUTF8String:buffer];
            NSData *response = [self handleRequest:request];
            
            send(clientSocket, response.bytes, response.length, 0);
        }
        
        close(clientSocket);
    }
}

- (NSData *)handleRequest:(NSString *)request {
    NSArray *lines = [request componentsSeparatedByString:@"\r\n"];
    NSString *firstLine = [lines firstObject];
    NSArray *parts = [firstLine componentsSeparatedByString:@" "];
    
    if (parts.count < 2) {
        return [self createResponse:400 body:@{@"error": @"Invalid request"}];
    }
    
    NSString *path = parts[1];
    
    if ([path hasPrefix:@"/run"]) {
        // 解析查询参数
        NSURL *url = [NSURL URLWithString:[NSString stringWithFormat:@"http://localhost%@", path]];
        NSURLComponents *components = [NSURLComponents componentsWithURL:url resolvingAgainstBaseURL:NO];
        
        NSString *scriptPath = nil;
        NSArray *arguments = @[];
        
        for (NSURLQueryItem *item in components.queryItems) {
            if ([item.name isEqualToString:@"path"]) {
                scriptPath = item.value;
            } else if ([item.name isEqualToString:@"args"]) {
                arguments = [item.value componentsSeparatedByString:@","];
            }
        }
        
        if (!scriptPath) {
            return [self createResponse:400 body:@{@"error": @"Script path is required"}];
        }
        
        // 使用信号量等待异步操作完成
        dispatch_semaphore_t semaphore = dispatch_semaphore_create(0);
        __block NSString *output = nil;
        __block NSError *error = nil;
        
        [ScriptRunner runScript:scriptPath arguments:arguments completion:^(NSString *result, NSError *err) {
            output = result;
            error = err;
            dispatch_semaphore_signal(semaphore);
        }];
        
        dispatch_semaphore_wait(semaphore, dispatch_time(DISPATCH_TIME_NOW, 10 * NSEC_PER_SEC));
        
        if (error) {
            return [self createResponse:500 body:@{@"error": error.localizedDescription}];
        } else {
            return [self createResponse:200 body:@{@"result": output ?: @""}];
        }
    } else if ([path hasPrefix:@"/script"]) {
        // 简化的API，使用脚本名称
        NSURL *url = [NSURL URLWithString:[NSString stringWithFormat:@"http://localhost%@", path]];
        NSURLComponents *components = [NSURLComponents componentsWithURL:url resolvingAgainstBaseURL:NO];
        
        NSString *scriptName = nil;
        for (NSURLQueryItem *item in components.queryItems) {
            if ([item.name isEqualToString:@"name"]) {
                scriptName = item.value;
                break;
            }
        }
        
        if (!scriptName) {
            return [self createResponse:400 body:@{@"error": @"Script name is required"}];
        }
        
        // 构建脚本路径 - 尝试多个位置
        NSString *scriptPath = nil;
        
        // 1. 尝试应用程序目录
        NSString *appPath = [[NSBundle mainBundle] bundlePath];
        NSString *appDir = [appPath stringByDeletingLastPathComponent];
        NSString *appDirScript = [appDir stringByAppendingPathComponent:scriptName];
        
        // 2. 尝试当前工作目录
        NSString *currentDir = [[NSFileManager defaultManager] currentDirectoryPath];
        NSString *currentDirScript = [currentDir stringByAppendingPathComponent:scriptName];
        
        // 3. 尝试用户桌面
        NSString *desktopPath = [NSSearchPathForDirectoriesInDomains(NSDesktopDirectory, NSUserDomainMask, YES) firstObject];
        NSString *desktopScript = [desktopPath stringByAppendingPathComponent:scriptName];
        
        NSLog(@"Looking for script in multiple locations:");
        NSLog(@"  App dir: %@", appDirScript);
        NSLog(@"  Current dir: %@", currentDirScript);
        NSLog(@"  Desktop: %@", desktopScript);
        
        // 检查文件是否存在
        NSFileManager *fm = [NSFileManager defaultManager];
        if ([fm fileExistsAtPath:appDirScript]) {
            scriptPath = appDirScript;
            NSLog(@"✅ Found script in app directory");
        } else if ([fm fileExistsAtPath:currentDirScript]) {
            scriptPath = currentDirScript;
            NSLog(@"✅ Found script in current directory");
        } else if ([fm fileExistsAtPath:desktopScript]) {
            scriptPath = desktopScript;
            NSLog(@"✅ Found script on desktop");
        } else {
            NSLog(@"❌ Script not found in any location");
            return [self createResponse:404 body:@{@"error": [NSString stringWithFormat:@"Script '%@' not found in any location", scriptName]}];
        }
        
        dispatch_semaphore_t semaphore = dispatch_semaphore_create(0);
        __block NSString *output = nil;
        __block NSError *error = nil;
        
        [ScriptRunner runScript:scriptPath arguments:@[] completion:^(NSString *result, NSError *err) {
            output = result;
            error = err;
            dispatch_semaphore_signal(semaphore);
        }];
        
        dispatch_semaphore_wait(semaphore, dispatch_time(DISPATCH_TIME_NOW, 10 * NSEC_PER_SEC));
        
        if (error) {
            return [self createResponse:500 body:@{@"error": error.localizedDescription}];
        } else {
            return [self createResponse:200 body:@{@"result": output ?: @""}];
        }
    } else {
        return [self createResponse:404 body:@{@"error": @"Not found"}];
    }
}

- (NSData *)createResponse:(int)status body:(NSDictionary *)body {
    NSString *statusText = @"OK";
    if (status == 404) statusText = @"Not Found";
    else if (status == 400) statusText = @"Bad Request";
    else if (status == 500) statusText = @"Internal Server Error";
    
    NSError *error = nil;
    NSData *jsonData = [NSJSONSerialization dataWithJSONObject:body options:0 error:&error];
    
    if (error) {
        NSString *errorResponse = @"HTTP/1.1 500 Internal Server Error\r\nContent-Length: 0\r\n\r\n";
        return [errorResponse dataUsingEncoding:NSUTF8StringEncoding];
    }
    
    NSString *headers = [NSString stringWithFormat:@"HTTP/1.1 %d %@\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: %lu\r\nConnection: close\r\n\r\n", status, statusText, (unsigned long)jsonData.length];
    
    NSMutableData *response = [NSMutableData data];
    [response appendData:[headers dataUsingEncoding:NSUTF8StringEncoding]];
    [response appendData:jsonData];
    
    return response;
}

@end

// AppleScript运行器实现
@implementation ScriptRunner

+ (void)runScript:(NSString *)scriptPath arguments:(NSArray *)arguments completion:(void(^)(NSString *output, NSError *error))completion {
    NSFileManager *fm = [NSFileManager defaultManager];
    
    if (![fm fileExistsAtPath:scriptPath]) {
        NSError *error = [NSError errorWithDomain:@"ScriptRunner" code:1 userInfo:@{NSLocalizedDescriptionKey: @"Script file not found"}];
        completion(nil, error);
        return;
    }
    
    if (![fm isReadableFileAtPath:scriptPath]) {
        NSError *error = [NSError errorWithDomain:@"ScriptRunner" code:2 userInfo:@{NSLocalizedDescriptionKey: @"Script file not readable"}];
        completion(nil, error);
        return;
    }
    
    NSTask *task = [[NSTask alloc] init];
    [task setLaunchPath:@"/usr/bin/osascript"];
    
    NSMutableArray *args = [NSMutableArray arrayWithObject:scriptPath];
    [args addObjectsFromArray:arguments];
    [task setArguments:args];
    
    NSPipe *outPipe = [[NSPipe alloc] init];
    NSPipe *errPipe = [[NSPipe alloc] init];
    [task setStandardOutput:outPipe];
    [task setStandardError:errPipe];
    
    [task setTerminationHandler:^(NSTask *completedTask) {
        NSData *outData = [[outPipe fileHandleForReading] readDataToEndOfFile];
        NSData *errData = [[errPipe fileHandleForReading] readDataToEndOfFile];
        
        NSString *output = [[NSString alloc] initWithData:outData encoding:NSUTF8StringEncoding];
        NSString *errorOutput = [[NSString alloc] initWithData:errData encoding:NSUTF8StringEncoding];
        
        if (completedTask.terminationStatus != 0 && errorOutput.length > 0) {
            NSError *error = [NSError errorWithDomain:@"ScriptRunner" code:completedTask.terminationStatus userInfo:@{NSLocalizedDescriptionKey: errorOutput}];
            completion(nil, error);
        } else {
            completion([output stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]], nil);
        }
    }];
    
    @try {
        [task launch];
    } @catch (NSException *exception) {
        NSError *error = [NSError errorWithDomain:@"ScriptRunner" code:3 userInfo:@{NSLocalizedDescriptionKey: exception.reason}];
        completion(nil, error);
    }
}

@end

// 应用程序代理实现
@implementation AppDelegate

- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    // 设置激活策略为辅助应用（状态栏应用）
    [NSApp setActivationPolicy:NSApplicationActivationPolicyAccessory];
    
    // 启动HTTP服务器
    self.httpServer = [[HTTPServer alloc] initWithPort:8787];
    [self.httpServer start];
    
    // 设置状态栏
    [self setupStatusBar];
    
    NSLog(@"ScptRunner started successfully on macOS 10.12");
}

- (void)applicationWillTerminate:(NSNotification *)notification {
    [self.httpServer stop];
    if (self.statusItem) {
        [[NSStatusBar systemStatusBar] removeStatusItem:self.statusItem];
    }
}

- (void)setupStatusBar {
    self.statusItem = [[NSStatusBar systemStatusBar] statusItemWithLength:NSVariableStatusItemLength];
    
    if (self.statusItem.button) {
        [self.statusItem.button setTitle:@"ScptRunner"];
        [self.statusItem.button setImage:[NSImage imageNamed:@"NSStatusAvailable"]];
        [self.statusItem.button setImagePosition:NSImageLeft];
    }
    
    // 创建菜单
    NSMenu *menu = [[NSMenu alloc] init];
    
    // 服务器状态菜单项
    NSMenuItem *statusMenuItem = [[NSMenuItem alloc] initWithTitle:@"服务器运行中 (端口: 8787)" action:nil keyEquivalent:@""];
    [statusMenuItem setEnabled:NO];
    [menu addItem:statusMenuItem];
    
    [menu addItem:[NSMenuItem separatorItem]];
    
    // 测试API菜单项
    NSMenuItem *testMenuItem = [[NSMenuItem alloc] initWithTitle:@"测试API" action:@selector(testAPI) keyEquivalent:@"t"];
    [testMenuItem setTarget:self];
    [menu addItem:testMenuItem];
    
    // 打开应用文件夹菜单项
    NSMenuItem *openMenuItem = [[NSMenuItem alloc] initWithTitle:@"打开应用文件夹" action:@selector(openAppFolder) keyEquivalent:@"o"];
    [openMenuItem setTarget:self];
    [menu addItem:openMenuItem];
    
    [menu addItem:[NSMenuItem separatorItem]];
    
    // 退出菜单项
    NSMenuItem *quitMenuItem = [[NSMenuItem alloc] initWithTitle:@"退出" action:@selector(terminate:) keyEquivalent:@"q"];
    [menu addItem:quitMenuItem];
    
    [self.statusItem setMenu:menu];
}

- (void)testAPI {
    NSURL *url = [NSURL URLWithString:@"http://localhost:8787/script?name=test_script.scpt"];
    NSURLSessionDataTask *task = [[NSURLSession sharedSession] dataTaskWithURL:url completionHandler:^(NSData *data, NSURLResponse *response, NSError *error) {
        dispatch_async(dispatch_get_main_queue(), ^{
            if (data && !error) {
                NSString *result = [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
                NSAlert *alert = [[NSAlert alloc] init];
                [alert setMessageText:@"API测试结果"];
                [alert setInformativeText:result ?: @"无结果"];
                [alert addButtonWithTitle:@"确定"];
                [alert runModal];
            } else {
                NSAlert *alert = [[NSAlert alloc] init];
                [alert setMessageText:@"API测试失败"];
                [alert setInformativeText:error.localizedDescription ?: @"未知错误"];
                [alert addButtonWithTitle:@"确定"];
                [alert runModal];
            }
        });
    }];
    [task resume];
}

- (void)openAppFolder {
    NSString *currentPath = [[NSFileManager defaultManager] currentDirectoryPath];
    NSURL *url = [NSURL fileURLWithPath:currentPath];
    [[NSWorkspace sharedWorkspace] openURL:url];
}

- (void)terminate:(id)sender {
    [NSApp terminate:nil];
}

@end

// 主函数
int main(int argc, const char * argv[]) {
    @autoreleasepool {
        NSApplication *app = [NSApplication sharedApplication];
        AppDelegate *delegate = [[AppDelegate alloc] init];
        [app setDelegate:delegate];
        
        NSLog(@"Starting ScptRunner for macOS 10.12...");
        
        return NSApplicationMain(argc, argv);
    }
} 