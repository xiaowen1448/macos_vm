#import <Foundation/Foundation.h>
#import <AppKit/AppKit.h>
#import <sys/socket.h>
#import <netinet/in.h>
#import <arpa/inet.h>
#import <unistd.h>

// 日志管理器类
@interface LogManager : NSObject
+ (instancetype)sharedManager;
- (void)setupLogFile;
- (void)logMessage:(NSString *)message;
- (NSString *)getLogFilePath;
@end

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
            [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"=== HANDLING HTTP CONNECTION ==="]];
            [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Received request: %@", [request componentsSeparatedByString:@"\r\n"][0]]];
            
            NSData *response = [self handleRequest:request];
            
            [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Generated response data length: %lu bytes", (unsigned long)response.length]];
            
            if (response.length > 0) {
                // 显示响应的前200字节用于调试
                NSString *responsePreview = [[NSString alloc] initWithData:[response subdataWithRange:NSMakeRange(0, MIN(200, response.length))] encoding:NSUTF8StringEncoding];
                [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Response preview (first 200 chars): %@", responsePreview ?: @"(unable to decode)"]];
                
                ssize_t bytesSent = send(clientSocket, response.bytes, response.length, 0);
                [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Sent %ld bytes to client (expected %lu)", bytesSent, (unsigned long)response.length]];
                
                if (bytesSent != response.length) {
                    [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"WARNING: Partial send! Expected %lu, sent %ld", (unsigned long)response.length, bytesSent]];
                }
            } else {
                [[LogManager sharedManager] logMessage:@"ERROR: Generated response is empty!"];
            }
            
            [[LogManager sharedManager] logMessage:@"=== END HTTP CONNECTION HANDLING ==="];
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
        
        [[LogManager sharedManager] logMessage:@"Starting script execution with 30-second timeout"];
        
        [ScriptRunner runScript:scriptPath arguments:arguments completion:^(NSString *result, NSError *err) {
            [[LogManager sharedManager] logMessage:@"Script execution completion block called"];
            [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Completion result length: %lu", (unsigned long)(result ? result.length : 0)]];
            output = result;
            error = err;
            dispatch_semaphore_signal(semaphore);
            [[LogManager sharedManager] logMessage:@"Semaphore signaled"];
        }];
        
        [[LogManager sharedManager] logMessage:@"Waiting for script completion (30 seconds timeout)"];
        long waitResult = dispatch_semaphore_wait(semaphore, dispatch_time(DISPATCH_TIME_NOW, 30 * NSEC_PER_SEC));
        
        if (waitResult == 0) {
            [[LogManager sharedManager] logMessage:@"Script execution completed within timeout"];
        } else {
            [[LogManager sharedManager] logMessage:@"WARNING: Script execution timed out after 30 seconds"];
        }
        
        if (error) {
            NSLog(@"Script execution error: %@", error.localizedDescription);
            [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Script execution error: %@", error.localizedDescription]];
            return [self createResponse:500 body:@{@"error": error.localizedDescription}];
        } else {
            [[LogManager sharedManager] logMessage:@"=== /RUN PATH HTTP HANDLER PROCESSING ==="];
            NSLog(@"Script execution successful, processing output...");
            NSLog(@"Raw output: %@", output ?: @"(nil)");
            [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Script execution successful, output length: %lu", (unsigned long)(output ? output.length : 0)]];
            [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Script output content: '%@'", output ?: @"(nil)"]];
            
            // 检查返回值是否已经是JSON格式
            NSString *trimmedOutput = [output stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
            NSLog(@"Trimmed output: %@", trimmedOutput ?: @"(nil)");
            [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Trimmed output: '%@'", trimmedOutput ?: @"(nil)"]];
            
            if (trimmedOutput && [trimmedOutput hasPrefix:@"{"] && [trimmedOutput hasSuffix:@"}"]) {
                NSLog(@"Output appears to be JSON, validating...");
                [[LogManager sharedManager] logMessage:@"Output appears to be JSON object format"];
                // 尝试解析JSON以验证格式
                NSData *jsonData = [trimmedOutput dataUsingEncoding:NSUTF8StringEncoding];
                NSError *jsonError = nil;
                id jsonObject = [NSJSONSerialization JSONObjectWithData:jsonData options:0 error:&jsonError];
                
                if (!jsonError && jsonObject) {
                    NSLog(@"Valid JSON detected, returning raw JSON response");
                    [[LogManager sharedManager] logMessage:@"JSON validation successful - returning raw JSON"];
                    // 是有效的JSON，直接返回原始JSON
                    return [self createRawJSONResponse:200 jsonString:trimmedOutput];
                } else {
                    NSLog(@"JSON validation failed: %@", jsonError.localizedDescription);
                    [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"JSON validation failed: %@", jsonError.localizedDescription]];
                }
            } else {
                NSLog(@"Output is not JSON format, wrapping in result object");
                [[LogManager sharedManager] logMessage:@"Output is not JSON format"];
            }
            // 不是JSON格式，按原方式包装
            NSLog(@"Returning wrapped response with result: %@", output ?: @"");
            [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Creating wrapped response with result: '%@'", output ?: @""]];
            [[LogManager sharedManager] logMessage:@"=== END /RUN PATH HTTP HANDLER PROCESSING ==="];
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
        
        [[LogManager sharedManager] logMessage:@"Starting script execution with 30-second timeout"];
        
        [ScriptRunner runScript:scriptPath arguments:@[] completion:^(NSString *result, NSError *err) {
            [[LogManager sharedManager] logMessage:@"Script execution completion block called"];
            [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Completion result length: %lu", (unsigned long)(result ? result.length : 0)]];
            output = result;
            error = err;
            dispatch_semaphore_signal(semaphore);
            [[LogManager sharedManager] logMessage:@"Semaphore signaled"];
        }];
        
        [[LogManager sharedManager] logMessage:@"Waiting for script completion (30 seconds timeout)"];
        long waitResult = dispatch_semaphore_wait(semaphore, dispatch_time(DISPATCH_TIME_NOW, 30 * NSEC_PER_SEC));
        
        if (waitResult == 0) {
            [[LogManager sharedManager] logMessage:@"Script execution completed within timeout"];
        } else {
            [[LogManager sharedManager] logMessage:@"WARNING: Script execution timed out after 30 seconds"];
        }
        
        if (error) {
            [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Script execution error: %@", error.localizedDescription]];
            return [self createResponse:500 body:@{@"error": error.localizedDescription}];
        } else {
            [[LogManager sharedManager] logMessage:@"=== HTTP HANDLER PROCESSING ==="];
            [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Script execution successful, output length: %lu", (unsigned long)output.length]];
            [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Script output content: '%@'", output ?: @"(nil)"]];
            
            // 检查输出是否为空
            if (!output) {
                [[LogManager sharedManager] logMessage:@"WARNING: HTTP handler received nil output"];
            } else if (output.length == 0) {
                [[LogManager sharedManager] logMessage:@"WARNING: HTTP handler received empty output"];
            } else {
                [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"HTTP handler received valid output with %lu characters", (unsigned long)output.length]];
                
                // 检查是否为JSON格式
                NSString *trimmedOutput = [output stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
                if ([trimmedOutput hasPrefix:@"{"] && [trimmedOutput hasSuffix:@"}"]) {
                    [[LogManager sharedManager] logMessage:@"Output appears to be JSON object format"];
                    
                    // 尝试解析JSON
                    NSData *jsonData = [trimmedOutput dataUsingEncoding:NSUTF8StringEncoding];
                    NSError *jsonError = nil;
                    id jsonObject = [NSJSONSerialization JSONObjectWithData:jsonData options:0 error:&jsonError];
                    
                    if (!jsonError && jsonObject) {
                        [[LogManager sharedManager] logMessage:@"JSON validation successful - returning raw JSON"];
                        return [self createRawJSONResponse:200 jsonString:trimmedOutput];
                    } else {
                        [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"JSON validation failed: %@", jsonError.localizedDescription]];
                    }
                } else {
                    [[LogManager sharedManager] logMessage:@"Output is not JSON format"];
                }
            }
            
            // 创建包装响应
            NSDictionary *responseBody = @{@"result": output ?: @""};
            [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Creating wrapped response with result: '%@'", output ?: @""]];
            [[LogManager sharedManager] logMessage:@"=== END HTTP HANDLER PROCESSING ==="];
            
            return [self createResponse:200 body:responseBody];
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

- (NSData *)createRawJSONResponse:(int)status jsonString:(NSString *)jsonString {
    [[LogManager sharedManager] logMessage:@"=== CREATING RAW JSON RESPONSE ==="];
    [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Status: %d", status]];
    [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"JSON string length: %lu", (unsigned long)jsonString.length]];
    [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"JSON string preview (first 100 chars): %@", [jsonString substringToIndex:MIN(100, jsonString.length)]]];
    
    NSString *statusText = @"OK";
    if (status == 404) statusText = @"Not Found";
    else if (status == 400) statusText = @"Bad Request";
    else if (status == 500) statusText = @"Internal Server Error";
    
    NSData *jsonData = [jsonString dataUsingEncoding:NSUTF8StringEncoding];
    NSString *headers = [NSString stringWithFormat:@"HTTP/1.1 %d %@\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: %lu\r\nConnection: close\r\n\r\n", status, statusText, (unsigned long)jsonData.length];
    
    [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"HTTP headers: %@", headers]];
    
    NSMutableData *response = [NSMutableData data];
    [response appendData:[headers dataUsingEncoding:NSUTF8StringEncoding]];
    [response appendData:jsonData];
    
    [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Final response data length: %lu bytes", (unsigned long)response.length]];
    [[LogManager sharedManager] logMessage:@"=== END CREATING RAW JSON RESPONSE ==="];
    
    return response;
}

@end

// 日志管理器实现
@implementation LogManager

static LogManager *sharedInstance = nil;
static NSFileHandle *logFileHandle = nil;
static NSString *logFilePath = nil;

+ (instancetype)sharedManager {
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        sharedInstance = [[LogManager alloc] init];
    });
    return sharedInstance;
}

- (instancetype)init {
    self = [super init];
    if (self) {
        [self setupLogFile];
    }
    return self;
}

- (void)setupLogFile {
    // 获取应用程序的可执行文件路径
    NSString *executablePath = [[NSBundle mainBundle] executablePath];
    NSString *appPath = [executablePath stringByDeletingLastPathComponent];
    
    // 如果是在.app包内，需要获取.app包的父目录
    if ([appPath hasSuffix:@"Contents/MacOS"]) {
        // 从 /path/to/ScptRunner.app/Contents/MacOS 获取 /path/to/
        appPath = [[[appPath stringByDeletingLastPathComponent] stringByDeletingLastPathComponent] stringByDeletingLastPathComponent];
    }
    
    // 创建logs目录路径
    NSString *logsDir = [appPath stringByAppendingPathComponent:@"logs"];
    
    // 创建logs目录（如果不存在）
    NSFileManager *fileManager = [NSFileManager defaultManager];
    NSError *error = nil;
    if (![fileManager fileExistsAtPath:logsDir]) {
        [fileManager createDirectoryAtPath:logsDir withIntermediateDirectories:YES attributes:nil error:&error];
        if (error) {
            NSLog(@"Failed to create log directory: %@", error.localizedDescription);
            return;
        }
    }
    
    // 创建日志文件路径（使用时间戳作为文件名）
    NSDateFormatter *formatter = [[NSDateFormatter alloc] init];
    [formatter setDateFormat:@"yyyy-MM-dd_HH-mm-ss"];
    NSString *timestamp = [formatter stringFromDate:[NSDate date]];
    NSString *logFileName = [NSString stringWithFormat:@"%@.log", timestamp];
    logFilePath = [logsDir stringByAppendingPathComponent:logFileName];
    
    // 创建日志文件
    if (![fileManager fileExistsAtPath:logFilePath]) {
        [@"" writeToFile:logFilePath atomically:YES encoding:NSUTF8StringEncoding error:&error];
        if (error) {
            NSLog(@"Failed to create log file: %@", error.localizedDescription);
            return;
        }
    }
    
    // 打开文件句柄用于写入
    logFileHandle = [NSFileHandle fileHandleForWritingAtPath:logFilePath];
    if (logFileHandle) {
        [logFileHandle seekToEndOfFile];
        
        // 写入启动日志
        NSString *startMessage = [NSString stringWithFormat:@"[%@] ScptRunner started - Log file created at: %@\n", [self getCurrentTimestamp], logFilePath];
        [self writeToLogFile:startMessage];
        
        NSLog(@"Log file created at: %@", logFilePath);
    } else {
        NSLog(@"Failed to open log file for writing: %@", logFilePath);
    }
}

- (void)logMessage:(NSString *)message {
    if (logFileHandle && message) {
        NSString *timestampedMessage = [NSString stringWithFormat:@"[%@] %@\n", [self getCurrentTimestamp], message];
        [self writeToLogFile:timestampedMessage];
    }
}

- (void)writeToLogFile:(NSString *)message {
    if (logFileHandle && message) {
        NSData *data = [message dataUsingEncoding:NSUTF8StringEncoding];
        @try {
            [logFileHandle writeData:data];
            [logFileHandle synchronizeFile]; // 立即刷新到磁盘
        } @catch (NSException *exception) {
            NSLog(@"Failed to write to log file: %@", exception.reason);
        }
    }
}

- (NSString *)getCurrentTimestamp {
    NSDateFormatter *formatter = [[NSDateFormatter alloc] init];
    [formatter setDateFormat:@"yyyy-MM-dd HH:mm:ss.SSS"];
    return [formatter stringFromDate:[NSDate date]];
}

- (NSString *)getLogFilePath {
    return logFilePath;
}

- (void)dealloc {
    if (logFileHandle) {
        [logFileHandle closeFile];
    }
}

@end

// AppleScript运行器实现
@implementation ScriptRunner

+ (void)runScript:(NSString *)scriptPath arguments:(NSArray *)arguments completion:(void(^)(NSString *output, NSError *error))completion {
    NSFileManager *fm = [NSFileManager defaultManager];
    
    [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Attempting to run script: %@", scriptPath]];
    
    if (![fm fileExistsAtPath:scriptPath]) {
        NSError *error = [NSError errorWithDomain:@"ScriptRunner" code:1 userInfo:@{NSLocalizedDescriptionKey: @"Script file not found"}];
        [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Script file not found: %@", scriptPath]];
        completion(nil, error);
        return;
    }
    
    if (![fm isReadableFileAtPath:scriptPath]) {
        NSError *error = [NSError errorWithDomain:@"ScriptRunner" code:2 userInfo:@{NSLocalizedDescriptionKey: @"Script file not readable"}];
        [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Script file not readable: %@", scriptPath]];
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
        
        // 详细记录原始数据
        NSLog(@"=== DETAILED SCRIPT OUTPUT ANALYSIS ===");
        NSLog(@"Raw output data length: %lu bytes", (unsigned long)outData.length);
        NSLog(@"Raw error data length: %lu bytes", (unsigned long)errData.length);
        
        // 以十六进制形式记录原始数据的前100字节
        if (outData.length > 0) {
            NSUInteger logLength = MIN(outData.length, 100);
            NSData *logData = [outData subdataWithRange:NSMakeRange(0, logLength)];
            NSLog(@"Raw output data (hex): %@", logData);
        }
        
        NSString *output = [[NSString alloc] initWithData:outData encoding:NSUTF8StringEncoding];
        NSString *errorOutput = [[NSString alloc] initWithData:errData encoding:NSUTF8StringEncoding];
        
        NSLog(@"Script execution completed:");
        NSLog(@"  Termination status: %d", completedTask.terminationStatus);
        NSLog(@"  Output length: %lu", (unsigned long)output.length);
        NSLog(@"  Error output length: %lu", (unsigned long)errorOutput.length);
        NSLog(@"  Output content: %@", output ?: @"(nil)");
        NSLog(@"  Error content: %@", errorOutput ?: @"(nil)");
        
        // 记录到日志文件
        [[LogManager sharedManager] logMessage:@"=== DETAILED SCRIPT OUTPUT ANALYSIS ==="];
        [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Raw output data length: %lu bytes", (unsigned long)outData.length]];
        [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Raw error data length: %lu bytes", (unsigned long)errData.length]];
        
        [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Script execution completed - Status: %d, Output length: %lu, Error length: %lu", 
                                               completedTask.terminationStatus, (unsigned long)output.length, (unsigned long)errorOutput.length]];
        
        // 检查输出是否为空或nil
        if (!output) {
            [[LogManager sharedManager] logMessage:@"WARNING: Output is nil!"];
        } else if (output.length == 0) {
            [[LogManager sharedManager] logMessage:@"WARNING: Output is empty string!"];
        } else {
            [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Raw script output: '%@'", output]];
            
            // 逐字符分析输出内容
            NSLog(@"Character-by-character analysis:");
            for (NSUInteger i = 0; i < MIN(output.length, 50); i++) {
                unichar c = [output characterAtIndex:i];
                NSLog(@"  [%lu]: '%C' (0x%04X)", (unsigned long)i, c, c);
            }
            
            // 记录trim前后的对比
            NSString *trimmedOutput = [output stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
            [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Trimmed output length: %lu", (unsigned long)trimmedOutput.length]];
            [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Trimmed script output: '%@'", trimmedOutput]];
            
            // 检查trim是否改变了内容
            if (![output isEqualToString:trimmedOutput]) {
                [[LogManager sharedManager] logMessage:@"WARNING: Trimming changed the output content!"];
                [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Original length: %lu, Trimmed length: %lu", (unsigned long)output.length, (unsigned long)trimmedOutput.length]];
            }
            
            // 检查是否包含JSON特征
            if ([trimmedOutput hasPrefix:@"{"] || [trimmedOutput hasPrefix:@"["]) {
                [[LogManager sharedManager] logMessage:@"Output appears to start with JSON bracket"];
                if ([trimmedOutput hasSuffix:@"}"] || [trimmedOutput hasSuffix:@"]"]) {
                    [[LogManager sharedManager] logMessage:@"Output appears to end with JSON bracket - likely JSON format"];
                } else {
                    [[LogManager sharedManager] logMessage:@"Output starts with JSON bracket but doesn't end properly"];
                }
            } else {
                [[LogManager sharedManager] logMessage:@"Output does not appear to be JSON format"];
            }
        }
        
        if (errorOutput && errorOutput.length > 0) {
            [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Script error output: %@", errorOutput]];
        }
        
        if (completedTask.terminationStatus != 0 && errorOutput.length > 0) {
            NSError *error = [NSError errorWithDomain:@"ScriptRunner" code:completedTask.terminationStatus userInfo:@{NSLocalizedDescriptionKey: errorOutput}];
            [[LogManager sharedManager] logMessage:@"Returning error due to non-zero termination status"];
            completion(nil, error);
        } else {
            NSString *finalOutput = [output stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
            [[LogManager sharedManager] logMessage:[NSString stringWithFormat:@"Final output passed to completion: '%@'", finalOutput]];
            [[LogManager sharedManager] logMessage:@"=== END DETAILED ANALYSIS ==="];
            completion(finalOutput, nil);
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
    
    // 初始化日志管理器
    [[LogManager sharedManager] setupLogFile];
    [[LogManager sharedManager] logMessage:@"Application started"];
    
    // 启动HTTP服务器
    self.httpServer = [[HTTPServer alloc] initWithPort:8787];
    [self.httpServer start];
    [[LogManager sharedManager] logMessage:@"HTTP server started on port 8787"];
    
    // 设置状态栏
    [self setupStatusBar];
    
    NSLog(@"ScptRunner started successfully on macOS 10.12");
    [[LogManager sharedManager] logMessage:@"ScptRunner started successfully on macOS 10.12"];
}

- (void)applicationWillTerminate:(NSNotification *)notification {
    [[LogManager sharedManager] logMessage:@"Application terminating"];
    [self.httpServer stop];
    [[LogManager sharedManager] logMessage:@"HTTP server stopped"];
    if (self.statusItem) {
        [[NSStatusBar systemStatusBar] removeStatusItem:self.statusItem];
    }
    [[LogManager sharedManager] logMessage:@"Application terminated"];
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
    
    // 查看日志文件菜单项
    NSMenuItem *logMenuItem = [[NSMenuItem alloc] initWithTitle:@"查看日志文件" action:@selector(openLogFile) keyEquivalent:@"l"];
    [logMenuItem setTarget:self];
    [menu addItem:logMenuItem];
    
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

- (void)openLogFile {
    NSString *logFilePath = [[LogManager sharedManager] getLogFilePath];
    if (logFilePath && [[NSFileManager defaultManager] fileExistsAtPath:logFilePath]) {
        NSURL *url = [NSURL fileURLWithPath:logFilePath];
        [[NSWorkspace sharedWorkspace] openURL:url];
        [[LogManager sharedManager] logMessage:@"Log file opened by user"];
    } else {
        NSAlert *alert = [[NSAlert alloc] init];
        [alert setMessageText:@"日志文件不存在"];
        [alert setInformativeText:@"无法找到日志文件，可能尚未创建。"];
        [alert addButtonWithTitle:@"确定"];
        [alert runModal];
    }
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