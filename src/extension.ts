// VS Code extension for creating timelapses of coding sessions
// Handles Python process management, UI interactions, and file system operations

import * as vscode from 'vscode';
import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';
import * as os from 'os';
import * as fs from 'fs';

/**
 * Configuration interface for timelapse settings
 * Defines all possible options that can be set in VS Code settings
 */
interface TimelapseConfig {
    outputDirectory: string;
    frameRate: number;
    videoFps: number;
    quality: number;
    captureArea?: {
        x: number;
        y: number;
        width: number;
        height: number;
    };
    multiMonitor: boolean;
}

/**
 * Main class handling timelapse recording functionality
 * Manages Python process, UI elements, and recording state
 */
class TimelapseRecorder {
    private pythonProcess: ChildProcess | null = null;
    private statusBarItem: vscode.StatusBarItem;
    private outputChannel: vscode.OutputChannel;
    private currentOutputDir: string | null = null;
    private isPaused: boolean = false;

    constructor() {
        this.statusBarItem = this.setupStatusBar();
        this.outputChannel = this.setupOutputChannel();
    }

    /**
     * Sets up the status bar item with initial state
     * Provides visual feedback and control for the recording process
     */
    private setupStatusBar(): vscode.StatusBarItem {
        const statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
        statusBarItem.command = 'extension.startTimelapse';
        statusBarItem.text = "$(camera) Start Timelapse";
        statusBarItem.tooltip = "Start Timelapse Recording";
        statusBarItem.show();
        return statusBarItem;
    }

    /**
     * Sets up output channel for logging
     * Critical for debugging and user feedback
     */
    private setupOutputChannel(): vscode.OutputChannel {
        const channel = vscode.window.createOutputChannel("Timelapse");
        channel.show();
        return channel;
    }

    /**
     * Logging utility with timestamp and type
     * Ensures consistent logging format across the extension
     */
    private log(message: string, type: 'INFO' | 'ERROR' = 'INFO'): void {
        const timestamp = new Date().toISOString();
        this.outputChannel.appendLine(`[${timestamp}] [${type}] ${message}`);
    }

    /**
     * Locates Python interpreter using multiple strategies
     * Bug fix: Added multiple fallback methods after issues with Python detection
     * First tries VS Code Python extension, then system commands
     */
    private async findPythonPath(): Promise<string> {
        this.log('Searching for Python interpreter...');
        
        // Try to find Python through VS Code Python extension
        try {
            const extension = vscode.extensions.getExtension('ms-python.python');
            if (extension) {
                this.log('Found Python extension, trying to get Python path...');
                const pythonPath = await extension.exports.settings.getExecutionDetails().pythonPath;
                if (pythonPath) {
                    this.log(`Got Python path from extension: ${pythonPath}`);
                    return pythonPath;
                }
            }
        } catch (error) {
            if (error instanceof Error) {
                this.log(`Failed to get Python path from Python extension: ${error.message}`, 'ERROR');
            } else {
                this.log('Failed to get Python path from Python extension', 'ERROR');
            }
        }

        // Try different Python commands
        const pythonCommands = process.platform === 'win32' 
            ? ['py', 'python'] 
            : ['python3', 'python'];

        for (const cmd of pythonCommands) {
            try {
                this.log(`Trying command: ${cmd}`);
                const result = await new Promise<boolean>((resolve) => {
                    const process = spawn(cmd, ['--version']);
                    
                    process.on('error', () => resolve(false));
                    
                    process.stdout.on('data', () => {
                        this.log(`Successfully found Python using command: ${cmd}`);
                        resolve(true);
                    });
                    
                    process.stderr.on('data', () => resolve(false));
                    process.on('close', (code) => resolve(code === 0));
                });

                if (result) {
                    return cmd;
                }
            } catch (err) {
                continue;
            }
        }

        throw new Error('Python interpreter not found. Please install Python and make sure it is available in your PATH.');
    }

    /**
     * Gets the active workspace folder
     * Used to determine where to save timelapse outputs
     */
    private getActiveWorkspaceFolder(): vscode.WorkspaceFolder | null {
        const activeEditor = vscode.window.activeTextEditor;
        if (activeEditor) {
            const activeFile = activeEditor.document.uri;
            if (vscode.workspace.workspaceFolders) {
                return vscode.workspace.workspaceFolders.find(folder => 
                    activeFile.fsPath.startsWith(folder.uri.fsPath)
                ) || vscode.workspace.workspaceFolders[0];
            }
        }
        return vscode.workspace.workspaceFolders?.[0] || null;
    }

    /**
     * Sets up Python process with proper arguments and environment
     * Bug fix: Added proper environment variables for UTF-8 encoding
     */
    private async setupPythonProcess(config: TimelapseConfig): Promise<void> {
        const pythonPath = await this.findPythonPath();
        const scriptPath = path.join(__dirname, 'timelapse.py');

        if (!fs.existsSync(scriptPath)) {
            throw new Error(`Python script not found at ${scriptPath}`);
        }

        const args = [
            scriptPath,
            this.currentOutputDir!,
            config.frameRate.toString(),
            config.videoFps.toString(),
            config.quality.toString()
        ];

        if (config.captureArea) {
            args.push(JSON.stringify(config.captureArea));
        }

        if (config.multiMonitor) {
            args.push('--multi-monitor');
        }

        const env = { ...process.env, pythonIoEncoding: 'utf-8' };
        this.pythonProcess = spawn(pythonPath, args, { env });
        this.setupProcessHandlers();
    }

    /**
     * Sets up event handlers for Python process
     * Handles output parsing, error logging, and process termination
     */
    private setupProcessHandlers(): void {
        if (!this.pythonProcess) {
            return;
        }

        this.pythonProcess.stdout?.on('data', (data: Buffer) => {
            const messages = data.toString().trim().split('\n');
            for (const message of messages) {
                if (message.startsWith('PROGRESS:')) {
                    const progress = message.split(':')[1];
                    this.statusBarItem.text = `$(loading) Creating video: ${progress}%`;
                } else if (message.startsWith('INFO:')) {
                    this.log(message.substring(5));
                } else {
                    this.log(`Python output: ${message}`);
                }
            }
        });

        this.pythonProcess.stderr?.on('data', (data: Buffer) => {
            const messages = data.toString().trim().split('\n');
            for (const message of messages) {
                this.log(message, 'ERROR');
                if (message.startsWith('ERROR:')) {
                    vscode.window.showErrorMessage(message.substring(6));
                }
            }
        });

        this.pythonProcess.on('error', (error: Error) => {
            this.log(`Failed to start Python process: ${error.message}`, 'ERROR');
            vscode.window.showErrorMessage(`Failed to start Python process: ${error.message}`);
            this.resetState();
        });

        this.pythonProcess.on('close', (code: number) => {
            this.log(`Python process exited with code ${code}`);
            this.handleProcessClose(code);
        });
    }

    /**
     * Handles Python process termination
     * Bug fix: Added extended wait time and file size checking
     * Previously had issues with video creation timing out too quickly
     */
    private async handleProcessClose(code: number | null): Promise<void> {
        if (code !== 0) {
            this.log(`Process exited with non-zero code: ${code}`, 'ERROR');
        }
        
        this.log('Waiting for video creation to complete...');
        
        // Give process more time to create video
        for (let i = 0; i < 60; i++) {  // Maximum 60 seconds wait
            const videoPath = await this.findVideoFile();
            if (videoPath) {
                const fileSize = fs.statSync(videoPath).size;
                this.log(`Video found: ${videoPath} (${fileSize} bytes)`);
                
                if (fileSize > 0) {
                    this.log('Video created successfully');
                    const action = await vscode.window.showInformationMessage(
                        'Timelapse video created successfully!',
                        'Open Video'
                    );
                    if (action === 'Open Video') {
                        this.openVideo(videoPath);
                    }
                    this.resetState();
                    return;
                }
            }
            await new Promise(resolve => setTimeout(resolve, 1000));  // Wait 1 second between checks
        }

        this.log('Video file not found or empty after waiting', 'ERROR');
        vscode.window.showErrorMessage('Failed to create video file');
        this.resetState();
    }

    /**
     * Searches for created video file with multiple format support
     * Bug fix: Added support for multiple video formats due to codec availability issues
     */
    private async findVideoFile(): Promise<string | null> {
        const extensions = ['.mp4', '.avi', '.wmv'];
        for (const ext of extensions) {
            const testPath = path.join(this.currentOutputDir!, 'timelapse' + ext);
            if (fs.existsSync(testPath)) {
                return testPath;
            }
        }
        return null;
    }

    /**
     * Opens video file using platform-specific commands
     * Ensures proper video playback across different operating systems
     */
    private openVideo(videoPath: string): void {
        const platform = process.platform;
        let command: string;
        
        switch (platform) {
            case 'win32':
                command = `start "${videoPath}"`;
                break;
            case 'darwin':
                command = `open "${videoPath}"`;
                break;
            default:
                command = `xdg-open "${videoPath}"`;
                break;
        }

        spawn(command, { shell: true });
    }

    /**
     * Resets extension state after recording ends
     * Ensures clean state for next recording session
     */
    private resetState(): void {
        this.pythonProcess = null;
        this.currentOutputDir = null;
        this.statusBarItem.text = "$(camera) Start Timelapse";
        this.isPaused = false;
    }

    /**
     * Starts timelapse recording
     * Sets up directories, launches Python process, and updates UI
     */
    public async startRecording(): Promise<void> {
        if (this.pythonProcess) {
            vscode.window.showInformationMessage('Timelapse recording is already in progress');
            return;
        }

        try {
            const config = this.getConfiguration();
            const workspaceFolder = this.getActiveWorkspaceFolder();
            
            this.currentOutputDir = workspaceFolder
                ? path.join(workspaceFolder.uri.fsPath, config.outputDirectory)
                : path.join(os.tmpdir(), 'vscode-timelapse', config.outputDirectory);

            fs.mkdirSync(this.currentOutputDir, { recursive: true });
            
            await this.setupPythonProcess(config);
            this.statusBarItem.text = "$(loading) Recording...";
            
            vscode.window.showInformationMessage('Started timelapse recording');
        } catch (error) {
            if (error instanceof Error) {
                this.log(`Error starting recording: ${error.message}`, 'ERROR');
                vscode.window.showErrorMessage(`Failed to start recording: ${error.message}`);
            } else {
                this.log('Error starting recording', 'ERROR');
                vscode.window.showErrorMessage('Failed to start recording');
            }
            this.resetState();
        }
    }

    /**
     * Stops timelapse recording using file-based approach
     * Bug fix: Replaced process termination with file-based stopping
     * Previous approach caused issues with video creation
     */
    public stopRecording(): void {
        if (this.pythonProcess && this.currentOutputDir) {
            this.log('Stopping timelapse recording...');
            
            // Create stop file
            const tempDir = path.join(this.currentOutputDir, 'temp');
            const stopFile = path.join(tempDir, '.stop');
            try {
                fs.writeFileSync(stopFile, '');
                this.log('Created stop file, waiting for process to finish...');
            } catch (error) {
                this.log(`Failed to create stop file: ${error}`, 'ERROR');
            }
        } else {
            vscode.window.showInformationMessage('No timelapse recording in progress');
        }
    }

    /**
     * Toggles recording pause state
     * Uses file-based approach for reliable cross-platform operation
     */
    public togglePause(): void {
        if (!this.pythonProcess || !this.currentOutputDir) {
            vscode.window.showInformationMessage('No timelapse recording in progress');
            return;
        }

        const tempDir = path.join(this.currentOutputDir, 'temp');
        const pauseFile = path.join(tempDir, '.pause');

        this.isPaused = !this.isPaused;
        if (this.isPaused) {
            fs.writeFileSync(pauseFile, '');
            this.statusBarItem.text = "$(debug-pause) Recording Paused";
            this.log('Recording paused');
        } else {
            try {
                if (fs.existsSync(pauseFile)) {
                    fs.unlinkSync(pauseFile);
                }
                this.statusBarItem.text = "$(loading) Recording...";
                this.log('Recording resumed');
            } catch (error) {
                this.log(`Failed to resume recording: ${error}`, 'ERROR');
            }
        }
    }

    /**
     * Retrieves extension configuration from VS Code settings
     * Provides defaults for all settings
     */
    private getConfiguration(): TimelapseConfig {
        const config = vscode.workspace.getConfiguration('timelapse');
        return {
            outputDirectory: config.get('outputDirectory', 'timelapse'),
            frameRate: config.get('frameRate', 2),
            videoFps: config.get('videoFps', 10),
            quality: config.get('quality', 95),
            captureArea: config.get('captureArea'),
            multiMonitor: config.get('multiMonitor', false)
        };
    }
}

let recorder: TimelapseRecorder;

/**
 * Extension activation handler
 * Sets up command registrations and creates recorder instance
 */
export function activate(context: vscode.ExtensionContext) {
    recorder = new TimelapseRecorder();

    context.subscriptions.push(
        vscode.commands.registerCommand('extension.startTimelapse', () => recorder.startRecording()),
        vscode.commands.registerCommand('extension.stopTimelapse', () => recorder.stopRecording()),
        vscode.commands.registerCommand('extension.pauseTimelapse', () => recorder.togglePause())
    );
}

/**
 * Extension deactivation handler
 * Ensures clean shutdown of recording process
 */
export function deactivate() {
    if (recorder) {
        recorder.stopRecording();
    }
} 