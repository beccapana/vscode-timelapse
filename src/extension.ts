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
    useCustomOutputDirectory: boolean;
    frameInterval: number;
    frameRate?: number;  // Deprecated
    videoFps: number;
    quality: number;
    videoCodec: string;  // Added video codec setting
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
    public statusBarItem: vscode.StatusBarItem;
    private outputChannel: vscode.OutputChannel;
    private currentOutputDir: string | null = null;
    private isPaused: boolean = false;
    private isProcessing: boolean = false;  // New flag to track video creation state

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
            (1 / config.frameInterval).toString(),  // Convert interval to rate for backward compatibility
            config.videoFps.toString(),
            config.quality.toString(),
            '--codec',
            config.videoCodec  // Pass codec to Python script
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
     * Stops timelapse recording using signals
     */
    public stopRecording(): void {
        if (!this.pythonProcess || !this.currentOutputDir) {
            vscode.window.showInformationMessage('No timelapse recording in progress');
            return;
        }

        this.log('Stopping timelapse recording...');
        
        // Update UI to show stopping state
        this.statusBarItem.text = "$(loading) Stopping...";
        
        // Store process reference
        const processToKill = this.pythonProcess;
        
        // Only reset process state, keep other state intact
        this.pythonProcess = null;
        this.isPaused = false;
        
        // Set a flag to track if the process exited normally
        let normalExit = false;
        
        // Listen for normal process exit
        processToKill?.once('close', () => {
            normalExit = true;
        });
        
        // Try graceful shutdown first, then force kill if needed
        setTimeout(async () => {
            if (!normalExit && processToKill) {
                try {
                    // Send SIGTERM first for graceful shutdown
                    processToKill.kill('SIGTERM');
                    
                    // Wait 5 seconds for SIGTERM to work
                    await new Promise(resolve => setTimeout(resolve, 5000));
                    
                    if (!normalExit) {
                        this.log('Process did not respond to SIGTERM, trying SIGINT...', 'ERROR');
                        processToKill.kill('SIGINT');
                        
                        // Wait another 5 seconds for SIGINT
                        await new Promise(resolve => setTimeout(resolve, 5000));
                        
                        if (!normalExit) {
                            this.log('Process did not respond to signals, forcing termination...', 'ERROR');
                            processToKill.kill('SIGKILL');
                        }
                    }
                } catch (error) {
                    this.log(`Error during process termination: ${error}`, 'ERROR');
                    try {
                        processToKill.kill('SIGKILL');
                    } catch (e) {
                        this.log(`Failed to force kill process: ${e}`, 'ERROR');
                    }
                }
            }
        }, 1000); // Reduced wait time since we're not waiting for file detection
    }

    /**
     * Cleans up temporary directory
     * Removes all temporary files and the directory itself
     */
    private cleanupTempDir(outputDir: string): void {
        const tempDir = path.join(outputDir, 'temp');
        if (fs.existsSync(tempDir)) {
            this.log('Cleaning up temporary directory...');
            try {
                const files = fs.readdirSync(tempDir);
                for (const file of files) {
                    const filePath = path.join(tempDir, file);
                    fs.unlinkSync(filePath);
                }
                fs.rmdirSync(tempDir);
                this.log('Temporary directory cleaned up');
            } catch (error) {
                this.log(`Error cleaning up temporary directory: ${error}`, 'ERROR');
            }
        }
    }

    /**
     * Checks if frames were captured
     * Returns true if there are any frame files in the temp directory
     */
    private hasFrames(outputDir: string): boolean {
        const tempDir = path.join(outputDir, 'temp');
        if (!fs.existsSync(tempDir)) {
            return false;
        }

        try {
            const files = fs.readdirSync(tempDir);
            return files.some(file => file.startsWith('frame_') && file.endsWith('.jpg'));
        } catch (error) {
            this.log(`Error checking frames: ${error}`, 'ERROR');
            return false;
        }
    }

    /**
     * Checks if ffmpeg is available in the system
     */
    private async checkFfmpeg(): Promise<boolean> {
        return new Promise((resolve) => {
            const ffmpeg = spawn('ffmpeg', ['-version']);
            
            ffmpeg.on('error', () => {
                this.log('ffmpeg not found in system PATH', 'ERROR');
                resolve(false);
            });

            ffmpeg.on('close', (code) => {
                resolve(code === 0);
            });
        });
    }

    /**
     * Creates video from captured frames using either ffmpeg or Python
     */
    private async createVideo(framesDir: string, outputPath: string, fps: number): Promise<boolean> {
        // First check if ffmpeg is available
        const hasFfmpeg = await this.checkFfmpeg();
        
        if (hasFfmpeg) {
            try {
                this.log('Creating video using ffmpeg...');
                
                return new Promise((resolve) => {
                    const ffmpeg = spawn('ffmpeg', [
                        '-y',
                        '-framerate', fps.toString(),
                        '-i', path.join(framesDir, 'frame_%d.jpg'),
                        '-c:v', 'libx264',
                        '-pix_fmt', 'yuv420p',
                        '-preset', 'medium',
                        '-crf', '23',
                        outputPath
                    ]);

                    ffmpeg.stdout?.on('data', (data) => {
                        this.log(`ffmpeg output: ${data}`);
                    });

                    ffmpeg.stderr?.on('data', (data) => {
                        const message = data.toString();
                        if (!message.startsWith('frame=')) {
                            this.log(`ffmpeg: ${message}`);
                        }
                    });

                    ffmpeg.on('close', (code) => {
                        if (code === 0) {
                            this.log('Video created successfully using ffmpeg');
                            resolve(true);
                        } else {
                            this.log(`ffmpeg exited with code ${code}`, 'ERROR');
                            resolve(false);
                        }
                    });

                    ffmpeg.on('error', (err) => {
                        this.log(`ffmpeg error: ${err}`, 'ERROR');
                        resolve(false);
                    });
                });
            } catch (error) {
                this.log(`Error creating video with ffmpeg: ${error}`, 'ERROR');
                return false;
            }
        } else {
            // Fallback to Python for video creation
            this.log('Falling back to Python for video creation...');
            try {
                const pythonPath = await this.findPythonPath();
                const scriptPath = path.join(__dirname, 'timelapse.py');
                
                return new Promise((resolve) => {
                    const pythonProcess = spawn(pythonPath, [
                        scriptPath,
                        '--create-video',
                        framesDir,
                        outputPath,
                        fps.toString()
                    ]);

                    pythonProcess.stdout?.on('data', (data) => {
                        this.log(`Python video creation: ${data}`);
                    });

                    pythonProcess.stderr?.on('data', (data) => {
                        this.log(`Python video creation error: ${data}`, 'ERROR');
                    });

                    pythonProcess.on('close', (code) => {
                        if (code === 0) {
                            this.log('Video created successfully using Python');
                            resolve(true);
                        } else {
                            this.log(`Python video creation failed with code ${code}`, 'ERROR');
                            resolve(false);
                        }
                    });

                    pythonProcess.on('error', (err) => {
                        this.log(`Python video creation error: ${err}`, 'ERROR');
                        resolve(false);
                    });
                });
            } catch (error) {
                this.log(`Error creating video with Python: ${error}`, 'ERROR');
                return false;
            }
        }
    }

    /**
     * Gets the name of the current project
     * Returns workspace name or folder name if available
     */
    private getProjectName(): string {
        const workspaceFolder = this.getActiveWorkspaceFolder();
        if (!workspaceFolder) {
            return 'unnamed_project';
        }

        // Try to get workspace name first
        const workspaceFile = vscode.workspace.workspaceFile;
        if (workspaceFile) {
            const workspaceName = path.basename(workspaceFile.fsPath, '.code-workspace');
            if (workspaceName && workspaceName !== '.code-workspace') {
                return workspaceName;
            }
        }

        // Fallback to folder name
        return path.basename(workspaceFolder.uri.fsPath);
    }

    /**
     * Generates a unique timelapse filename for the current project
     */
    private async generateTimelapseFilename(baseDir: string, projectName: string): Promise<string> {
        let counter = 1;
        let filename: string;
        
        do {
            filename = path.join(baseDir, `${projectName}${counter}.mp4`);
            counter++;
        } while (fs.existsSync(filename));
        
        return filename;
    }

    /**
     * Handles Python process termination
     * Bug fix: Added extended wait time and file size checking
     * Previously had issues with video creation timing out too quickly
     */
    private async handleProcessClose(code: number | null): Promise<void> {
        this.log(`Process termination handler started with code: ${code}`);
        
        // Store current directory before any resets
        const currentDir = this.currentOutputDir;
        
        // If no directory, just reset
        if (!currentDir) {
            this.log('No output directory found', 'ERROR');
            this.resetState();
            return;
        }

        // Wait a bit for Python to finish its cleanup
        await new Promise(resolve => setTimeout(resolve, 2000));

        try {
            // First check if we have any frames
            if (!this.hasFrames(currentDir)) {
                this.log('No frames were captured', 'ERROR');
                vscode.window.showErrorMessage('No frames were captured during the recording');
                this.cleanupTempDir(currentDir);
                this.resetState();
                return;
            }

            this.log('Frames found, attempting to create video...');

            // Set processing state
            this.isProcessing = true;
            this.statusBarItem.text = "$(loading) Creating video...";

            // Try to create video
            const tempDir = path.join(currentDir, 'temp');
            const projectName = this.getProjectName();
            const outputPath = await this.generateTimelapseFilename(currentDir, projectName);
            const config = this.getConfiguration();

            const success = await this.createVideo(tempDir, outputPath, config.videoFps);
            
            // Clean up temp directory immediately after video creation
            this.cleanupTempDir(currentDir);
            
            // Reset state before showing notification
            this.log('Ensuring all states are reset...');
            this.resetState();
            this.log('State reset completed');
            
            if (success) {
                const action = await vscode.window.showInformationMessage(
                    'Timelapse video created successfully!',
                    'Open Video'
                );
                if (action === 'Open Video') {
                    this.openVideo(outputPath);
                }
            } else {
                this.log('Failed to create video', 'ERROR');
                vscode.window.showErrorMessage('Failed to create video file');
            }
        } catch (error) {
            this.log(`Error during video creation: ${error}`, 'ERROR');
            vscode.window.showErrorMessage('Failed to create video file');
            // Clean up temp directory in case of error
            this.cleanupTempDir(currentDir);
            // Reset state in case of error
            this.log('Ensuring all states are reset...');
        this.resetState();
            this.log('State reset completed');
        }
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
        // Prevent multiple resets
        if (!this.pythonProcess && !this.currentOutputDir && !this.isProcessing) {
            return;
        }

        this.log('Starting state reset...');
        
        if (this.pythonProcess) {
            try {
                this.log('Killing Python process...');
                this.pythonProcess.kill();
                this.log('Python process killed');
            } catch (error) {
                this.log(`Error killing process: ${error}`, 'ERROR');
            }
        }

        // Reset all state variables
        this.pythonProcess = null;
        this.currentOutputDir = null;
        this.statusBarItem.text = "$(camera) Start Timelapse";
        this.isPaused = false;
        this.isProcessing = false;
        
        this.log('State reset completed. Ready for new recording.');
    }

    /**
     * Starts timelapse recording
     * Sets up directories, launches Python process, and updates UI
     */
    public async startRecording(): Promise<void> {
        this.log('Starting new recording...');
        this.log(`Current state - Process: ${this.pythonProcess ? 'exists' : 'null'}, Processing: ${this.isProcessing}`);
        
        if (this.pythonProcess || this.isProcessing) {
            this.log('Cannot start - recording already in progress', 'ERROR');
            vscode.window.showInformationMessage('Timelapse recording is already in progress');
            return;
        }

        try {
            const config = this.getConfiguration();
            const projectName = this.getProjectName();
            
            // Check for invalid configuration
            if (config.useCustomOutputDirectory && config.outputDirectory.toLowerCase() === 'timelapse') {
                this.log('Invalid configuration: Cannot use "timelapse" as output directory when custom directory is enabled', 'ERROR');
                vscode.window.showErrorMessage('Invalid configuration: When using a custom output directory, you cannot use "timelapse" as the directory name. Please choose a different name or disable custom directory option.');
                return;
            }
            
            // Determine output directory based on configuration
            if (config.useCustomOutputDirectory) {
                // Normalize the path to handle Windows paths correctly
                const baseDir = path.normalize(config.outputDirectory);
                
                // Validate that the path is absolute
                if (!path.isAbsolute(baseDir)) {
                    this.log('Invalid configuration: Custom output directory must be an absolute path', 'ERROR');
                    vscode.window.showErrorMessage('Custom output directory must be an absolute path (e.g., C:\\MyTimelapses or /home/user/timelapses)');
                    return;
                }
                
                // Create project-specific subdirectory
                this.currentOutputDir = path.join(baseDir, projectName);
                this.log(`Using custom output directory: ${this.currentOutputDir}`);
            } else {
                // Use relative path within workspace
                const workspaceFolder = this.getActiveWorkspaceFolder();
                const baseDir = workspaceFolder
                ? path.join(workspaceFolder.uri.fsPath, config.outputDirectory)
                : path.join(os.tmpdir(), 'vscode-timelapse', config.outputDirectory);

                this.currentOutputDir = baseDir;
                this.log(`Using workspace-relative output directory: ${this.currentOutputDir}`);
            }

            // Ensure the output directory exists
            this.log(`Setting up output directory: ${this.currentOutputDir}`);
            fs.mkdirSync(this.currentOutputDir, { recursive: true });
            
            await this.setupPythonProcess(config);
            this.statusBarItem.text = "$(loading) Recording...";
            
            this.log('Recording started successfully');
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
     * Toggles recording pause state using platform-specific methods:
     * - File-based approach on Windows
     * - Signal-based approach on Unix systems
     */
    public togglePause(): void {
        if (!this.pythonProcess || !this.currentOutputDir) {
            vscode.window.showInformationMessage('No timelapse recording in progress');
            return;
        }

        this.isPaused = !this.isPaused;
        
        try {
            if (process.platform === 'win32') {
                // Use file-based approach for Windows
                const pauseFile = path.join(this.currentOutputDir, 'temp', '.pause');
                if (this.isPaused) {
                    fs.writeFileSync(pauseFile, '');
                } else {
                    if (fs.existsSync(pauseFile)) {
                        fs.unlinkSync(pauseFile);
                    }
                }
            } else {
                // Use SIGUSR1 for Unix-like systems
                this.pythonProcess.kill('SIGUSR1');
            }
            
        if (this.isPaused) {
            this.statusBarItem.text = "$(debug-pause) Recording Paused";
                this.log('Recording paused');
        } else {
            this.statusBarItem.text = "$(loading) Recording...";
                this.log('Recording resumed');
            }
        } catch (error) {
            this.log(`Failed to toggle pause state: ${error}`, 'ERROR');
            // Reset pause state if operation failed
            this.isPaused = !this.isPaused;
            vscode.window.showErrorMessage('Failed to pause/resume recording');
        }
    }

    /**
     * Retrieves extension configuration from VS Code settings
     * Provides defaults for all settings
     */
    private getConfiguration(): TimelapseConfig {
        const config = vscode.workspace.getConfiguration('timelapse');
        
        // Get frameInterval or convert from deprecated frameRate
        let frameInterval = config.get<number>('frameInterval', 0.2);  // Default: 5 fps = 0.2 seconds interval
        const frameRate = config.get<number>('frameRate');
        
        if (typeof frameRate === 'number' && !config.get('frameInterval')) {
            // Convert frameRate to frameInterval
            frameInterval = 1 / frameRate;
            this.log('Warning: Using deprecated frameRate setting. Please use frameInterval instead (frameInterval = 1/frameRate).', 'ERROR');
        }
        
        return {
            outputDirectory: config.get<string>('outputDirectory', 'timelapse'),
            useCustomOutputDirectory: config.get<boolean>('useCustomOutputDirectory', false),
            frameInterval,
            frameRate: config.get<number>('frameRate'),  // Deprecated
            videoFps: config.get<number>('videoFps', 10),
            quality: config.get<number>('quality', 95),
            videoCodec: config.get<string>('videoCodec', 'H264'),  // Get codec from settings
            captureArea: config.get('captureArea'),
            multiMonitor: config.get<boolean>('multiMonitor', false)
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
        vscode.commands.registerCommand('extension.pauseTimelapse', () => recorder.togglePause()),
        vscode.commands.registerCommand('extension.openTimelapseSettings', () => {
            // Open VS Code settings with timelapse settings pre-filtered
            vscode.commands.executeCommand('workbench.action.openSettings', 'timelapse');
        })
    );

    // Initialize status bar
    recorder.statusBarItem.show();
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