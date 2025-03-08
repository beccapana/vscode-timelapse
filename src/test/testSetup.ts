import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import * as os from 'os';

export class TestSetup {
    private tempWorkspace: string;

    constructor() {
        this.tempWorkspace = path.join(os.tmpdir(), `vscode-timelapse-test-${Date.now()}`);
    }

    async setup(): Promise<void> {
        console.log('Setting up test environment');
        
        // Create temporary directory
        if (fs.existsSync(this.tempWorkspace)) {
            fs.rmSync(this.tempWorkspace, { recursive: true, force: true });
        }
        fs.mkdirSync(this.tempWorkspace, { recursive: true });
        console.log(`Created temporary workspace at ${this.tempWorkspace}`);

        // Create workspace file
        const workspaceFile = path.join(this.tempWorkspace, 'test.code-workspace');
        fs.writeFileSync(workspaceFile, JSON.stringify({
            folders: [{ path: this.tempWorkspace }],
            settings: {}
        }));
        console.log('Created workspace file');

        // Wait for extension activation
        console.log('Waiting for extension activation');
        await this.waitForExtension();
        console.log('Extension activated');
    }

    async cleanup(): Promise<void> {
        console.log('Cleaning up test environment');
        if (fs.existsSync(this.tempWorkspace)) {
            fs.rmSync(this.tempWorkspace, { recursive: true, force: true });
            console.log('Removed temporary workspace');
        }
    }

    private async waitForExtension(timeout: number = 10000): Promise<void> {
        const startTime = Date.now();
        while (Date.now() - startTime < timeout) {
            const extension = vscode.extensions.getExtension('your-name.vscode-timelapse');
            if (extension) {
                if (!extension.isActive) {
                    await extension.activate();
                }
                return;
            }
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        throw new Error('Extension not found or failed to activate');
    }

    getWorkspacePath(): string {
        return this.tempWorkspace;
    }
}

// Helper function to create a temporary workspace directory
export function createTestWorkspace(): string {
    const workspaceDir = path.join(os.tmpdir(), `vscode-timelapse-test-${Date.now()}`);
    
    // Create temporary directory
    if (fs.existsSync(workspaceDir)) {
        fs.rmSync(workspaceDir, { recursive: true, force: true });
    }
    fs.mkdirSync(workspaceDir, { recursive: true });

    // Create workspace file
    const workspaceFile = path.join(workspaceDir, 'test.code-workspace');
    fs.writeFileSync(workspaceFile, JSON.stringify({
        folders: [{ path: workspaceDir }],
        settings: {}
    }));

    return workspaceDir;
}

// Export the function for use in other test files
export function setupTestWorkspace(): string {
    return createTestWorkspace();
} 