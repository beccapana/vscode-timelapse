import * as assert from 'assert';
import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { TestSetup } from '../testSetup';

interface PackageJson {
    contributes: {
        configuration: {
            properties: {
                [key: string]: {
                    type: string;
                    default: string | number | boolean;
                    description: string;
                };
            };
        };
    };
}

suite('Extension Test Suite', function() {
    let testSetup: TestSetup;
    let packageJson: PackageJson;

    suiteSetup(async function() {
        console.log('Test suite setup started');
        console.log('Setting up test environment');
        testSetup = new TestSetup();
        await testSetup.setup();

        // Load package.json
        const packageJsonPath = path.join(__dirname, '../../../package.json');
        packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
        console.log('Test suite setup completed');
    });

    suiteTeardown(async function() {
        console.log('Test suite teardown started');
        console.log('Cleaning up test environment');
        await testSetup.cleanup();
        console.log('Test suite teardown completed');
    });

    test('Extension should be present', async () => {
        console.log('Testing extension presence');
        const extension = vscode.extensions.getExtension('your-name.vscode-timelapse');
        assert.ok(extension, 'Extension should be present');
        console.log('Extension presence test completed');
    });

    test('Should register commands', async () => {
        console.log('Testing command registration');
        const commands = await vscode.commands.getCommands();
        console.log('Available commands:', commands);
        assert.ok(commands.includes('extension.startTimelapse'), 'Start command should be registered');
        assert.ok(commands.includes('extension.stopTimelapse'), 'Stop command should be registered');
        console.log('Command registration test completed');
    });

    test('Should have correct default configuration', async () => {
        console.log('Testing default configuration');
        const config = vscode.workspace.getConfiguration('timelapse');

        // Clear all workspace settings
        const settings = [
            'outputDirectory',
            'frameRate',
            'videoFps',
            'quality',
            'multiMonitor'
        ];

        for (const setting of settings) {
            await config.update(setting, undefined, vscode.ConfigurationTarget.Workspace);
            await config.update(setting, undefined, vscode.ConfigurationTarget.Global);
        }

        // Wait for configuration to update
        await new Promise(resolve => setTimeout(resolve, 100));

        // Get fresh configuration
        const freshConfig = vscode.workspace.getConfiguration('timelapse');
        console.log('Current configuration:', {
            outputDirectory: freshConfig.get('outputDirectory'),
            frameRate: freshConfig.get('frameRate'),
            videoFps: freshConfig.get('videoFps'),
            quality: freshConfig.get('quality'),
            captureArea: freshConfig.get('captureArea'),
            multiMonitor: freshConfig.get('multiMonitor')
        });

        // Get default values from package.json
        const defaultValues = packageJson.contributes.configuration.properties;
        
        // Check each configuration value against package.json defaults
        assert.strictEqual(
            freshConfig.get('outputDirectory'),
            defaultValues['timelapse.outputDirectory'].default,
            'outputDirectory should match package.json default'
        );
        assert.strictEqual(
            freshConfig.get('frameRate'),
            defaultValues['timelapse.frameRate'].default,
            'frameRate should match package.json default'
        );
        assert.strictEqual(
            freshConfig.get('videoFps'),
            defaultValues['timelapse.videoFps'].default,
            'videoFps should match package.json default'
        );
        assert.strictEqual(
            freshConfig.get('quality'),
            defaultValues['timelapse.quality'].default,
            'quality should match package.json default'
        );
        assert.strictEqual(
            freshConfig.get('multiMonitor'),
            defaultValues['timelapse.multiMonitor'].default,
            'multiMonitor should match package.json default'
        );
    });

    test('Should handle configuration updates', async () => {
        console.log('Testing configuration updates');
        const config = vscode.workspace.getConfiguration('timelapse');
        
        // Store original values
        const originalOutputDir = config.get('outputDirectory');
        const originalFrameRate = config.get('frameRate');

        try {
            // Update configuration
            await config.update('outputDirectory', 'test-output', vscode.ConfigurationTarget.Workspace);
            await config.update('frameRate', 5, vscode.ConfigurationTarget.Workspace);
            
            // Wait for configuration to update
            await new Promise(resolve => setTimeout(resolve, 100));
            
            // Get updated configuration
            const updatedConfig = vscode.workspace.getConfiguration('timelapse');
            assert.strictEqual(updatedConfig.get('outputDirectory'), 'test-output', 'outputDirectory should be updated');
            assert.strictEqual(updatedConfig.get('frameRate'), 5, 'frameRate should be updated');
        } finally {
            // Restore original values
            await config.update('outputDirectory', originalOutputDir, vscode.ConfigurationTarget.Workspace);
            await config.update('frameRate', originalFrameRate, vscode.ConfigurationTarget.Workspace);
        }
    });
}); 