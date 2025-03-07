const vscode = require('vscode');
const { spawn } = require('child_process');
const path = require('path');
const os = require('os');
const fs = require('fs');

let pythonProcess = null;
let statusBarItem = null;
let outputChannel = null;
let currentOutputDir = null;

function log(message, type = 'INFO') {
    if (outputChannel) {
        const timestamp = new Date().toISOString();
        outputChannel.appendLine(`[${timestamp}] [${type}] ${message}`);
    }
}

async function findPythonPath() {
    log('Searching for Python interpreter...');
    // Сначала пробуем найти Python через VS Code Python расширение
    try {
        const extension = vscode.extensions.getExtension('ms-python.python');
        if (extension) {
            log('Found Python extension, trying to get Python path...');
            const pythonPath = await extension.exports.settings.getExecutionDetails().pythonPath;
            if (pythonPath) {
                log(`Got Python path from extension: ${pythonPath}`);
                return pythonPath;
            }
        }
    } catch (err) {
        log(`Failed to get Python path from Python extension: ${err.message}`, 'ERROR');
    }

    // Пробуем разные варианты команды Python
    log('Trying different Python commands...');
    const pythonCommands = ['python3', 'python', 'py'];
    for (const cmd of pythonCommands) {
        try {
            log(`Trying command: ${cmd}`);
            const result = require('child_process').spawnSync(cmd, ['--version']);
            if (result.status === 0) {
                log(`Successfully found Python using command: ${cmd}`);
                return cmd;
            }
        } catch (err) {
            log(`Command ${cmd} failed: ${err.message}`, 'WARN');
            continue;
        }
    }

    log('Falling back to default python command', 'WARN');
    return 'python';
}

function getActiveWorkspaceFolder() {
    log('Getting active workspace folder...');
    // Получаем активный текстовый редактор
    const activeEditor = vscode.window.activeTextEditor;
    if (activeEditor) {
        const activeFile = activeEditor.document.uri;
        log(`Active file: ${activeFile.fsPath}`);
        // Находим рабочую область, содержащую активный файл
        if (vscode.workspace.workspaceFolders) {
            const activeWorkspace = vscode.workspace.workspaceFolders.find(folder => 
                activeFile.fsPath.startsWith(folder.uri.fsPath)
            );
            if (activeWorkspace) {
                log(`Found workspace containing active file: ${activeWorkspace.name}`);
                return activeWorkspace;
            }
        }
    }
    
    // Если нет активного редактора или файл вне рабочих областей,
    // возвращаем первую рабочую область или null
    const defaultWorkspace = vscode.workspace.workspaceFolders?.[0] || null;
    if (defaultWorkspace) {
        log(`Using default workspace: ${defaultWorkspace.name}`);
    } else {
        log('No workspace found', 'WARN');
    }
    return defaultWorkspace;
}

function activate(context) {
    log('Activating extension...');
    // Создаем канал вывода
    outputChannel = vscode.window.createOutputChannel("Timelapse");
    outputChannel.show();
    log('Output channel created');

    // Создаем статус-бар элемент
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBarItem.command = 'extension.startTimelapse';
    statusBarItem.text = "$(camera) Start Timelapse";
    statusBarItem.tooltip = "Start Timelapse Recording";
    statusBarItem.show();
    log('Status bar item created');

    let startCommand = vscode.commands.registerCommand('extension.startTimelapse', async function () {
        log('Start command triggered');
        try {
            const config = vscode.workspace.getConfiguration('timelapse');
            log('Reading configuration...');
            const outputDir = config.get('outputDirectory') || 'timelapse';
            const frameRate = config.get('frameRate') || 2;
            const videoFps = config.get('videoFps') || 10;
            const quality = config.get('quality') || 95;
            log(`Configuration: outputDir=${outputDir}, frameRate=${frameRate}, videoFps=${videoFps}, quality=${quality}`);

            // Определяем директорию для сохранения
            let fullOutputDir;
            const activeWorkspace = getActiveWorkspaceFolder();
            
            if (activeWorkspace) {
                fullOutputDir = path.join(activeWorkspace.uri.fsPath, outputDir);
                log(`Using workspace folder: ${activeWorkspace.name}`);
                log(`Full output directory: ${fullOutputDir}`);
                currentOutputDir = fullOutputDir; // Сохраняем текущую директорию
            } else {
                fullOutputDir = path.join(os.tmpdir(), 'vscode-timelapse', outputDir);
                log(`Using temp directory: ${fullOutputDir}`);
                currentOutputDir = fullOutputDir; // Сохраняем текущую директорию
            }
            
            if (!pythonProcess) {
                // Проверяем наличие Python-скрипта
                const scriptPath = path.join(__dirname, 'timelapse.py');
                log(`Checking Python script at: ${scriptPath}`);
                if (!fs.existsSync(scriptPath)) {
                    throw new Error(`Python script not found at ${scriptPath}`);
                }
                log('Python script found');

                // Находим путь к Python
                const pythonPath = await findPythonPath();
                log(`Using Python interpreter: ${pythonPath}`);
                
                // Создаем выходную директорию, если её нет
                if (!fs.existsSync(fullOutputDir)) {
                    log(`Creating output directory: ${fullOutputDir}`);
                    fs.mkdirSync(fullOutputDir, { recursive: true });
                }

                // Проверяем версию Python
                const versionCheck = require('child_process').spawnSync(pythonPath, ['--version']);
                const pythonVersion = versionCheck.stdout || versionCheck.stderr;
                log(`Python version: ${pythonVersion}`);

                log('Starting Python process...');
                vscode.window.showInformationMessage('Starting timelapse recording...');
                statusBarItem.text = "$(loading) Recording...";
                
                // Запускаем Python-скрипт с явным указанием кодировки
                const env = { ...process.env, PYTHONIOENCODING: 'utf-8' };
                log('Spawning Python process with arguments:');
                log(`  Script: ${scriptPath}`);
                log(`  Output: ${fullOutputDir}`);
                log(`  Frame rate: ${frameRate}`);
                log(`  Video FPS: ${videoFps}`);
                log(`  Quality: ${quality}`);

                pythonProcess = spawn(pythonPath, [
                    '-u', // Unbuffered output
                    scriptPath,
                    fullOutputDir,
                    frameRate.toString(),
                    videoFps.toString(),
                    quality.toString()
                ], { env });

                pythonProcess.stdout.on('data', (data) => {
                    const messages = data.toString().trim().split('\n');
                    for (const message of messages) {
                        if (message.startsWith('PROGRESS:')) {
                            const progress = message.split(':')[1];
                            log(`Video creation progress: ${progress}%`);
                            statusBarItem.text = `$(loading) Creating video: ${progress}%`;
                        } else if (message.startsWith('INFO:')) {
                            log(message.substring(5));
                        } else {
                            log(`Python output: ${message}`);
                        }
                    }
                });

                pythonProcess.stderr.on('data', (data) => {
                    const messages = data.toString().trim().split('\n');
                    for (const message of messages) {
                        if (message.startsWith('ERROR:')) {
                            log(message.substring(6), 'ERROR');
                            vscode.window.showErrorMessage(message.substring(6));
                        } else {
                            log(`Python error: ${message}`, 'ERROR');
                        }
                    }
                });

                pythonProcess.on('error', (error) => {
                    log(`Failed to start Python process: ${error.message}`, 'ERROR');
                    vscode.window.showErrorMessage(`Failed to start Python process: ${error.message}`);
                    pythonProcess = null;
                    statusBarItem.text = "$(camera) Start Timelapse";
                });

                pythonProcess.on('close', (code) => {
                    log(`Python process exited with code ${code}`);
                    currentOutputDir = null; // Сбрасываем текущую директорию
                    if (code === 0) {
                        // Ищем созданный видеофайл
                        const possibleExtensions = ['.mp4', '.avi', '.wmv'];
                        let videoPath = null;
                        
                        log('Searching for created video file...');
                        for (const ext of possibleExtensions) {
                            const testPath = path.join(fullOutputDir, 'timelapse' + ext);
                            log(`Checking ${testPath}`);
                            if (fs.existsSync(testPath)) {
                                videoPath = testPath;
                                log(`Found video file: ${videoPath}`);
                                break;
                            }
                        }

                        if (videoPath) {
                            log('Video created successfully');
                            vscode.window.showInformationMessage(
                                'Timelapse video created successfully!',
                                'Open Video'
                            ).then(selection => {
                                if (selection === 'Open Video') {
                                    log(`Opening video file: ${videoPath}`);
                                    require('child_process').exec(`start "${videoPath}"`);
                                }
                            });
                        } else {
                            log('Video file not found', 'ERROR');
                            vscode.window.showErrorMessage('Video file was not found');
                        }
                    } else {
                        log(`Timelapse recording failed with code ${code}`, 'ERROR');
                        vscode.window.showErrorMessage(`Timelapse recording failed with code ${code}`);
                    }
                    statusBarItem.text = "$(camera) Start Timelapse";
                    pythonProcess = null;
                });
            }
        } catch (error) {
            log(`Error in start command: ${error.message}`, 'ERROR');
            log(error.stack, 'ERROR');
            vscode.window.showErrorMessage(`Failed to start timelapse: ${error.message}`);
            if (pythonProcess) {
                log('Killing Python process due to error');
                pythonProcess.kill('SIGTERM');
                pythonProcess = null;
            }
            statusBarItem.text = "$(camera) Start Timelapse";
        }
    });

    let stopCommand = vscode.commands.registerCommand('extension.stopTimelapse', function () {
        log('Stop command triggered');
        if (pythonProcess && currentOutputDir) {
            log('Stopping timelapse recording...');
            vscode.window.showInformationMessage('Stopping timelapse recording...');
            statusBarItem.text = "$(loading) Creating video...";
            
            // Создаем файл-флаг для остановки
            const stopFlagPath = path.join(currentOutputDir, '.stop');
            try {
                log(`Creating stop flag at: ${stopFlagPath}`);
                fs.writeFileSync(stopFlagPath, 'stop');
                
                // Даем Python-скрипту время на корректное завершение
                setTimeout(() => {
                    if (pythonProcess) {
                        log('Forcing Python process to stop');
                        pythonProcess.kill('SIGTERM');
                    }
                }, 5000); // Ждем 5 секунд перед принудительным завершением
            } catch (error) {
                log(`Failed to create stop flag: ${error.message}`, 'ERROR');
                // Если не удалось создать файл-флаг, используем SIGTERM
                pythonProcess.kill('SIGTERM');
            }
        } else {
            log('No active recording to stop');
        }
    });

    context.subscriptions.push(startCommand, stopCommand, outputChannel);
    log('Extension activated successfully');
}

function deactivate() {
    log('Deactivating extension...');
    if (pythonProcess) {
        log('Killing Python process during deactivation');
        pythonProcess.kill('SIGTERM');
    }
    if (statusBarItem) {
        log('Disposing status bar item');
        statusBarItem.dispose();
    }
    if (outputChannel) {
        log('Disposing output channel');
        outputChannel.dispose();
    }
    log('Extension deactivated');
}

module.exports = { activate, deactivate };
